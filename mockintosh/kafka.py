#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains Kafka related methods.
"""

import re
import time
import json
import copy
import logging
import threading
from collections import OrderedDict
from datetime import datetime
from typing import (
    Union
)

import jsonschema
from confluent_kafka import Producer, Consumer
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka.cimpl import KafkaException

from mockintosh.constants import LOGGING_LENGTH_LIMIT
from mockintosh.helpers import _delay
from mockintosh.handlers import KafkaHandler
from mockintosh.replicas import Consumed
from mockintosh.logs import Logs
from mockintosh.exceptions import (
    AsyncProducerListHasNoPayloadsMatchingTags,
    AsyncProducerPayloadLoopEnd,
    AsyncProducerDatasetLoopEnd
)


def _kafka_delivery_report(err, msg):
    if err is not None:  # pragma: no cover
        logging.debug('Message delivery failed: %s', err)
    else:
        logging.debug('Message delivered to %s [%s]', msg.topic(), msg.partition())


def _create_topic(address: str, topic: str, ssl: bool = False):
    config = {'bootstrap.servers': address}
    if ssl:  # pragma: no cover
        config['security.protocol'] = 'SSL'
    admin_client = AdminClient(config)
    new_topics = [NewTopic(topic, num_partitions=1, replication_factor=1)]
    futures = admin_client.create_topics(new_topics)

    for topic, future in futures.items():
        try:
            future.result()
            logging.info('Topic %s created', topic)
        except KafkaException as e:
            logging.info('Failed to create topic %s: %s', topic, e)


def _decoder(value):
    try:
        return value.decode()
    except (AttributeError, UnicodeDecodeError):
        return value


def _headers_decode(headers: list):
    new_headers = {}
    for el in headers if headers else []:
        new_headers[el[0]] = _decoder(el[1])
    return new_headers


def _merge_global_headers(_globals: dict, kafka_payload):
    headers = {}
    global_headers = _globals['headers'] if 'headers' in _globals else {}
    headers.update(global_headers)
    produce_data_headers = kafka_payload.headers
    headers.update(produce_data_headers)
    return headers


def _wait_for_topic_to_exist(obj, topic: str):
    is_logged = False
    while True:
        topics = obj.list_topics(topic)  # promises to create topic
        logging.debug("Topic state: %s", topics.topics)
        if topics.topics[topic].error is None:
            break
        else:
            if not is_logged:
                logging.warning("Topic '%s' is not available: %s", topic, topics.topics[topic].error)
                is_logged = True
            time.sleep(1)


class KafkaConsumerProducerBase:

    def __init__(
        self,
        topic: str
    ):
        self.topic = topic
        self.actor = None
        self.internal_endpoint_id = None
        self.index = None
        self.counter = 0
        self.last_timestamp = None

    def info(self):
        return {
            'type': 'kafka',
            'name': self.actor.name,
            'index': self.index,
            'queue': self.topic
        }

    def set_last_timestamp_and_inc_counter(self, request_start_datetime: datetime):
        self.counter += 1
        if request_start_datetime is None:
            self.last_timestamp = time.time()
            return
        self.last_timestamp = datetime.timestamp(request_start_datetime)


class KafkaConsumer(KafkaConsumerProducerBase):

    def __init__(
        self,
        topic: str,
        schema: Union[str, dict] = None,
        value: Union[str, None] = None,
        key: Union[str, None] = None,
        headers: dict = {},
        capture_limit: int = 1,
        enable_topic_creation: bool = False
    ):
        super().__init__(topic)
        self.schema = schema
        self.match_value = value
        self.match_key = key
        self.match_headers = headers
        self.capture_limit = capture_limit
        self.log = []
        self.single_log_service = None
        self.enable_topic_creation = enable_topic_creation

    def _match_str(self, x: str, y: Union[str, None]):
        if y is None:
            y = ''

        x = '^%s$' % x
        match = re.search(x, y)
        if match is None:
            return False
        else:
            return True

    def match_attr(self, x: Union[str, dict, None], y: Union[str, dict, None]) -> bool:
        if x is None:
            return True

        if isinstance(x, dict):
            for k, v in x.items():
                if k not in y and k.title() not in y:
                    return False
                elif not self._match_str(v, y[k]):
                    return False
            return True
        elif isinstance(x, str):
            return self._match_str(x, y)

    def match_schema(self, value: str, kafka_handler: KafkaHandler) -> bool:
        json_schema = self.schema
        if isinstance(json_schema, str) and len(json_schema) > 1 and json_schema[0] == '@':
            json_schema_path, _ = kafka_handler.resolve_relative_path(json_schema)
            with open(json_schema_path, 'r') as file:
                logging.info('Reading JSON schema file from path: %s', json_schema_path)
                try:
                    json_schema = json.load(file)
                except json.decoder.JSONDecodeError:
                    logging.warning('JSON decode error of the JSON schema file: %s', json_schema)
                    return False
                logging.debug('JSON schema: %s', json_schema)

        try:
            json_data = json.loads(value)
        except json.decoder.JSONDecodeError:
            logging.warning('JSON decode error of the async value:\n\n%s', value)
            return False

        try:
            jsonschema.validate(instance=json_data, schema=json_schema)
            return True
        except jsonschema.exceptions.ValidationError:
            logging.debug(
                'Async value:\n\n%s\nDoes not match to JSON schema:\n\n%s',
                json_data,
                json_schema
            )
            return False

    def match(self, key: str, value: str, headers: dict, kafka_handler: KafkaHandler) -> bool:
        if (
            (not self.match_attr(self.match_value, value))
            or  # noqa: W504, W503
            (not self.match_attr(self.match_key, key))
            or  # noqa: W504, W503
            (not self.match_attr(self.match_headers, headers))
        ):
            return False
        else:
            if self.schema is not None:
                return self.match_schema(value, kafka_handler)
            else:
                return True

    def info(self) -> dict:
        data = super().info()
        data.update(
            {
                'captured': len(self.single_log_service.records),
                'consumedMessages': self.counter,
                'lastConsumed': self.last_timestamp
            }
        )
        return data

    def init_single_log_service(self) -> None:
        logs = Logs()
        logs.add_service(self.actor.service.name if self.actor.service.name is not None else '')
        self.single_log_service = logs.services[0]
        self.single_log_service.enabled = True


class KafkaConsumerGroup:

    def __init__(self):
        self.consumers = []

    def add_consumer(self, consumer: KafkaConsumer):
        self.consumers.append(consumer)

    def consume(self, stop: dict = {}) -> None:
        first_actor = self.consumers[0].actor

        if any(consumer.enable_topic_creation for consumer in self.consumers):
            _create_topic(
                first_actor.service.address,
                first_actor.consumer.topic,
                ssl=first_actor.service.ssl
            )

        config = {
            'bootstrap.servers': first_actor.service.address,
            'group.id': '0',
            'auto.offset.reset': 'earliest'
        }
        if first_actor.service.ssl:
            config['security.protocol'] = 'SSL'
        consumer = Consumer(config)
        _wait_for_topic_to_exist(consumer, first_actor.consumer.topic)
        consumer.subscribe([first_actor.consumer.topic])

        while True:
            if stop.get('val', False):  # pragma: no cover
                break

            msg = consumer.poll(1.0)

            if msg is None:
                continue

            if msg.error():  # pragma: no cover
                logging.warning("Consumer error: %s", msg.error())
                continue

            key, value, headers = _decoder(msg.key()), _decoder(msg.value()), _headers_decode(msg.headers())

            logging.debug(
                'Analyzing a Kafka message from %r addr=%r key=%r value=%r headers=%r',
                first_actor.consumer.topic,
                first_actor.service.address,
                key,
                value,
                headers
            )

            matched_consumer = None

            kafka_handler = None
            for _consumer in self.consumers:
                kafka_handler = KafkaHandler(
                    _consumer.actor.id,
                    _consumer.internal_endpoint_id,
                    _consumer.actor.service.definition.source_dir,
                    _consumer.actor.service.definition.template_engine,
                    _consumer.actor.service.definition.rendering_queue,
                    _consumer.actor.service.definition.logs,
                    _consumer.actor.service.definition.stats,
                    _consumer.actor.service.address,
                    _consumer.topic,
                    False,
                    service_id=_consumer.actor.service.id,
                    value=value,
                    key=key,
                    headers=headers,
                    context=_consumer.actor.context,
                    params=_consumer.actor.params
                )
                if _consumer.match(key, value, headers, kafka_handler):
                    matched_consumer = _consumer
                    break

            if matched_consumer is None:
                logging.debug(
                    'NOT MATCHED the Kafka message: addr=%r topic=%r key=%r value=%r headers=%r',
                    first_actor.service.address,
                    first_actor.consumer.topic,
                    key,
                    value,
                    headers
                )
                continue

            logging.info(
                'Consumed a Kafka message from %r by %r',
                matched_consumer.actor.consumer.topic,
                '%s' % (matched_consumer.actor.name if matched_consumer.actor.name is not None else '#%s' % matched_consumer.actor.id),
            )
            logging.debug(
                '[%s] MATCHED the Kafka message: addr=%r topic=%r key=%r value=%r headers=%r',
                '%s' % (matched_consumer.actor.name if matched_consumer.actor.name is not None else '#%s' % matched_consumer.actor.id),
                matched_consumer.actor.service.address,
                matched_consumer.actor.consumer.topic,
                key,
                '%s...' % value[:LOGGING_LENGTH_LIMIT] if len(value) > LOGGING_LENGTH_LIMIT else value,
                headers
            )

            matched_consumer.log.append(
                (key, value, headers)
            )

            kafka_handler.set_response(
                key=key, value=value, headers=headers
            )

            log_record = kafka_handler.finish()
            matched_consumer.set_last_timestamp_and_inc_counter(None if log_record is None else log_record.request_start_datetime)
            if matched_consumer.single_log_service is not None:
                matched_consumer.single_log_service.add_record(log_record)

            if len(matched_consumer.log) > matched_consumer.capture_limit:
                matched_consumer.log.pop(0)

            if len(matched_consumer.single_log_service.records) > matched_consumer.capture_limit:
                matched_consumer.single_log_service.records.pop(0)

            if matched_consumer.actor.producer is not None:
                consumed = Consumed()
                consumed.key = key
                consumed.value = value
                consumed.headers = headers

                try:
                    matched_consumer.actor.producer.check_payload_lock()
                    matched_consumer.actor.producer.check_dataset_lock()
                    t = threading.Thread(target=matched_consumer.actor.producer.produce, args=(), kwargs={
                        'consumed': consumed,
                        'context': kafka_handler.custom_context
                    })
                    t.daemon = True
                    t.start()
                except (
                    AsyncProducerPayloadLoopEnd,
                    AsyncProducerDatasetLoopEnd
                ) as e:
                    logging.error(str(e))


class KafkaProducerPayload:

    def __init__(
        self,
        value: str,
        key: Union[str, None] = None,
        headers: dict = {},
        tag: Union[str, None] = None,
        enable_topic_creation: bool = False
    ):
        self.value = value
        self.key = key
        self.headers = headers
        self.tag = tag
        self.enable_topic_creation = enable_topic_creation


class KafkaProducerPayloadList:

    def __init__(self):
        self.list = []

    def add_payload(self, payload: KafkaProducerPayload):
        self.list.append(payload)


class KafkaProducer(KafkaConsumerProducerBase):

    def __init__(
        self,
        topic: str,
        payload_list: KafkaProducerPayloadList
    ):
        super().__init__(topic)
        self.payload_list = payload_list
        self.payload_iteration = 0
        self.dataset_iteration = 0
        self.lock_payload = False
        self.lock_dataset = False

    def check_tags(self) -> None:
        if all(_payload.tag is not None and _payload.tag not in self.actor.service.tags for _payload in self.payload_list.list):
            raise AsyncProducerListHasNoPayloadsMatchingTags(self.actor.get_hint(), self.actor.service.tags)

    def check_payload_lock(self) -> None:
        if self.is_payload_locked():
            raise AsyncProducerPayloadLoopEnd(self.actor.get_hint())

    def increment_payload_iteration(self) -> None:
        self.payload_iteration += 1
        if self.payload_iteration > len(self.payload_list.list) - 1:
            if not self.actor.multi_payloads_looped:
                self.lock_payload = True
            self.payload_iteration = 0

    def get_current_payload(self) -> KafkaProducerPayload:
        return self.payload_list.list[self.payload_iteration]

    def is_payload_locked(self) -> bool:
        return self.lock_payload

    def check_dataset_lock(self) -> None:
        if self.is_dataset_locked():
            raise AsyncProducerDatasetLoopEnd(self.actor.get_hint())

    def check_dataset(self) -> bool:
        if all('tag' in row and row['tag'] not in self.actor.service.tags for row in self.actor._dataset):
            return False
        return True

    def increment_dataset_iteration(self) -> None:
        self.dataset_iteration += 1
        if self.dataset_iteration > len(self.actor._dataset) - 1:
            if not self.actor.dataset_looped:
                self.lock_dataset = True
            self.dataset_iteration = 0

    def get_current_dataset_row(self) -> dict:
        return self.actor._dataset[self.dataset_iteration]

    def is_dataset_locked(self) -> bool:
        if self.actor.dataset is None:
            return False
        return self.lock_dataset

    def produce(self, consumed: Consumed = None, context: dict = {}, ignore_delay: bool = False) -> None:
        payload = self.get_current_payload()
        self.increment_payload_iteration()
        if payload.tag is not None and payload.tag not in self.actor.service.tags:
            try:
                self.check_tags()
                while payload.tag is not None and payload.tag not in self.actor.service.tags:
                    payload = self.get_current_payload()
                    self.increment_payload_iteration()
            except AsyncProducerListHasNoPayloadsMatchingTags as e:
                logging.error(str(e))
                return

        context = copy.deepcopy(context)

        kafka_handler = KafkaHandler(
            self.actor.id,
            self.internal_endpoint_id,
            self.actor.service.definition.source_dir,
            self.actor.service.definition.template_engine,
            self.actor.service.definition.rendering_queue,
            self.actor.service.definition.logs,
            self.actor.service.definition.stats,
            self.actor.service.address,
            self.topic,
            True,
            service_id=self.actor.service.id,
            value=payload.value,
            key=payload.key,
            headers=payload.headers,
            context=context,
            params=self.actor.params
        )

        if not ignore_delay and self.actor.delay is not None:
            _delay(self.actor.delay)

        definition = self.actor.service.definition
        if definition is not None:
            kafka_handler.headers = _merge_global_headers(
                definition.data['globals'] if 'globals' in definition.data else {},
                payload
            )

        if consumed is not None:
            kafka_handler.custom_context.update({
                'consumed': consumed
            })

        row = None
        set_row = False
        if self.actor.dataset is not None:
            self.actor._dataset = kafka_handler.load_dataset(self.actor.dataset)
            row = self.get_current_dataset_row()
            self.increment_dataset_iteration()
            if 'tag' in row and row['tag'] not in self.actor.service.tags:
                if self.check_dataset():
                    while 'tag' in row and row['tag'] not in self.actor.service.tags:
                        row = self.get_current_dataset_row()
                        self.increment_dataset_iteration()
                    set_row = True
            else:
                set_row = True

        if set_row:
            for key, value in row.items():
                kafka_handler.custom_context[key] = value

        # Templating
        key, value, headers = kafka_handler.render_attributes()

        # Producing
        config = {'bootstrap.servers': self.actor.service.address}
        if self.actor.service.ssl:
            config['security.protocol'] = 'SSL'
        producer = Producer(config)

        if payload.enable_topic_creation:
            topics = producer.list_topics(self.topic)
            if topics.topics[self.topic].error is not None:
                _create_topic(
                    self.actor.service.address,
                    self.topic,
                    ssl=self.actor.service.ssl
                )

        producer.poll(0)
        producer.produce(self.topic, value, key=key, headers=headers, callback=_kafka_delivery_report)
        producer.flush()

        logging.info(
            'Produced a Kafka message into %r from %r',
            self.topic,
            '%s' % (self.actor.name if self.actor.name is not None else '#%s' % self.actor.id)
        )
        logging.debug(
            '[%s] addr=%r key=%r value=%r headers=%r',
            '%s' % (self.actor.name if self.actor.name is not None else '#%s' % self.actor.id),
            self.actor.service.address,
            key,
            '%s...' % value[:LOGGING_LENGTH_LIMIT] if len(value) > LOGGING_LENGTH_LIMIT else value,
            headers
        )

        log_record = kafka_handler.finish()
        self.set_last_timestamp_and_inc_counter(None if log_record is None else log_record.request_start_datetime)

    def info(self):
        data = super().info()
        data.update(
            {
                'producedMessages': self.counter,
                'lastProduced': self.last_timestamp
            }
        )
        return data


class KafkaActor:

    def __init__(self, _id, name: str = None):
        self.id = _id
        self.name = name
        self.counters = {}
        self.context = OrderedDict()
        self.params = {}
        self.consumer = None
        self.producer = None
        self.delay = None
        self.limit = None
        self.service = None
        self.dataset = None
        self._dataset = None
        self.multi_payloads_looped = True
        self.dataset_looped = True

    def get_hint(self) -> str:
        return self.name if self.name is not None else '#%d' % self.id

    def set_consumer(self, consumer: KafkaConsumer):
        self.consumer = consumer
        self.consumer.actor = self
        self.consumer.init_single_log_service()
        if self.service.definition.stats is None:
            return

        hint = '%s %s%s' % (
            'GET',
            self.consumer.topic,
            ' - %d' % self.id
        )
        if self.name is not None:
            hint = '%s (actor: %s)' % (hint, self.name)
        self.service.definition.stats.services[self.service.id].add_endpoint(hint)
        self.consumer.internal_endpoint_id = len(self.service.definition.stats.services[self.service.id].endpoints) - 1

    def set_producer(self, producer: KafkaProducer):
        self.producer = producer
        self.producer.actor = self
        if self.service.definition.stats is None:
            return

        hint = '%s %s%s' % (
            'PUT',
            self.producer.topic,
            ' - %d' % self.id
        )
        if self.name is not None:
            hint = '%s (actor: %s)' % (hint, self.name)
        self.service.definition.stats.services[self.service.id].add_endpoint(hint)
        self.producer.internal_endpoint_id = len(self.service.definition.stats.services[self.service.id].endpoints) - 1

    def set_delay(self, value: Union[int, float]):
        self.delay = value

    def set_limit(self, value: int):
        self.limit = value

    def set_dataset(self, dataset: Union[list, str]):
        self.dataset = dataset


class KafkaService:

    def __init__(self, address: str, name: str = None, definition=None, _id: int = None, ssl: bool = False):
        self.address = address
        self.name = name
        self.definition = definition
        self.actors = []
        self.id = _id
        self.ssl = ssl
        self.tags = []

    def add_actor(self, actor: KafkaActor):
        actor.service = self
        self.actors.append(actor)


def _run_produce_loop(definition, service: KafkaService, actor: KafkaActor, stop: dict):
    if actor.limit is None:
        logging.debug('Running a Kafka loop (%s) indefinitely...', actor.get_hint())
    else:
        logging.debug('Running a Kafka loop (%s) for %d iterations...', actor.get_hint(), actor.limit)

    while actor.limit is None or actor.limit > 0:
        if stop.get('val', False):  # pragma: no cover
            break

        try:
            actor.producer.check_payload_lock()
            actor.producer.check_dataset_lock()
            actor.producer.produce()
        except (
            AsyncProducerPayloadLoopEnd,
            AsyncProducerDatasetLoopEnd
        ):
            break

        if actor.delay is not None:
            _delay(actor.delay)

        if actor.limit is not None and actor.limit > 0:
            actor.limit -= 1

    logging.debug('Kafka loop (%s) is finished.', actor.get_hint())


def run_loops(definition, stop: dict):
    for service_id, service in enumerate(definition.data['kafka_services']):

        consumer_groups = {}

        for actor_id, actor in enumerate(service.actors):
            if actor.consumer is None and actor.producer is not None and actor.delay is not None:
                t = threading.Thread(target=_run_produce_loop, args=(definition, service, actor, stop), kwargs={})
                t.daemon = True
                t.start()

            if actor.consumer is not None:
                if actor.consumer.topic not in consumer_groups.keys():
                    consumer_group = KafkaConsumerGroup()
                    consumer_group.add_consumer(actor.consumer)
                    consumer_groups[actor.consumer.topic] = consumer_group
                else:
                    consumer_groups[actor.consumer.topic].add_consumer(actor.consumer)

        for _, consumer_group in consumer_groups.items():
            t = threading.Thread(target=consumer_group.consume, args=(), kwargs={'stop': stop})
            t.daemon = True
            t.start()


def build_single_payload_producer(
    topic: str,
    value: str,
    key: Union[str, None] = None,
    headers: dict = {},
    tag: Union[str, None] = None,
    enable_topic_creation: bool = False
):
    payload_list = KafkaProducerPayloadList()
    payload = KafkaProducerPayload(
        value,
        key=key,
        headers=headers,
        tag=tag
    )
    payload_list.add_payload(payload)
    return KafkaProducer(topic, payload_list)
