#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains asynchronous services related classes.
"""

import re
import time
import json
import copy
import logging
import threading
from abc import abstractmethod
from collections import OrderedDict
from datetime import datetime
from typing import (
    Union,
    Tuple
)

import jsonschema
from pika.exceptions import AMQPConnectionError

from mockintosh.constants import LOGGING_LENGTH_LIMIT
from mockintosh.config import (
    ConfigExternalFilePath
)
from mockintosh.helpers import _delay
from mockintosh.handlers import AsyncHandler
from mockintosh.replicas import Consumed
from mockintosh.logs import Logs
from mockintosh.exceptions import (
    AsyncProducerListHasNoPayloadsMatchingTags,
    AsyncProducerPayloadLoopEnd,
    AsyncProducerDatasetLoopEnd
)

SERVICE_TYPES = {
    'kafka': 'Kafka',
    'amqp': 'AMQP',
    'redis': 'Redis',
    'gpubsub': 'Google Cloud Pub/Sub',
    'amazonsqs': 'Amazon SQS',
    'mqtt': 'MQTT'
}


def _merge_global_headers(_globals: dict, async_payload):
    headers = {}
    global_headers = _globals['headers'] if 'headers' in _globals else {}
    headers.update(global_headers)
    produce_data_headers = async_payload.headers
    headers.update(produce_data_headers)
    return headers


class AsyncConsumerProducerBase:

    def __init__(
        self,
        index: int,
        topic: str
    ):
        self.topic = topic
        self.actor = None
        self.internal_endpoint_id = None
        self.index = index
        self.counter = 0
        self.last_timestamp = None

    def info(self):
        return {
            'type': self.actor.service.type,
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


class AsyncConsumer(AsyncConsumerProducerBase):

    consumers = []

    def __init__(
        self,
        topic: str,
        schema: Union[str, dict] = None,
        value: Union[str, None] = None,
        key: Union[str, None] = None,
        headers: Union[dict, None] = None,
        amqp_properties: Union[dict, None] = None,
        capture_limit: int = 1,
        enable_topic_creation: bool = False
    ):
        super().__init__(len(AsyncConsumer.consumers), topic)
        self.schema = schema
        self.match_value = value
        self.match_key = key
        self.match_headers = {} if headers is None else headers
        self.match_amqp_properties = {} if amqp_properties is None else {k: v for k, v in amqp_properties.items() if v is not None}
        self.capture_limit = capture_limit
        self.log = []
        self.single_log_service = None
        self.enable_topic_creation = enable_topic_creation
        self._index = len(AsyncConsumer.consumers)
        AsyncConsumer.consumers.append(self)

    def _match_str(self, x: str, y: Union[str, None]):
        if y is None:
            y = ''
        elif not isinstance(y, str):
            y = str(y)

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

    def match_schema(self, value: str, async_handler: AsyncHandler) -> bool:
        json_schema = self.schema.payload
        if isinstance(json_schema, ConfigExternalFilePath):
            json_schema_path, _ = async_handler.resolve_relative_path(json_schema.path)
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

    def match(self, key: str, value: str, headers: dict, async_handler: AsyncHandler, amqp_properties: dict = {}) -> bool:
        if (
            (not self.match_attr(self.match_value, value))
            or  # noqa: W504, W503
            (not self.match_attr(self.match_key, key))
            or  # noqa: W504, W503
            (not self.match_attr(self.match_headers, headers))
            or  # noqa: W504, W503
            (not self.match_attr(self.match_amqp_properties, amqp_properties))
        ):
            return False
        else:
            if self.schema is not None:
                return self.match_schema(value, async_handler)
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


class AsyncConsumerGroup:

    groups = []

    def __init__(self):
        self.consumers = []
        self.stop = False
        self._index = len(AsyncConsumerGroup.groups)
        AsyncConsumerGroup.groups.append(self)

    def add_consumer(self, consumer: AsyncConsumer) -> None:
        self.consumers.append(consumer)

    def after_consume_match(
        self,
        matched_consumer: AsyncConsumer,
        async_handler: AsyncHandler,
        value: Union[str, None] = None,
        key: Union[str, None] = None,
        headers: Union[dict, None] = None
    ) -> None:
        headers = {} if headers is None else headers

        matched_consumer.log.append(
            (key, value, headers)
        )

        async_handler.set_response(
            key=key, value=value, headers=headers
        )

        log_record = async_handler.finish()
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
                    'context': async_handler.custom_context
                })
                t.daemon = True
                t.start()
            except (
                AsyncProducerPayloadLoopEnd,
                AsyncProducerDatasetLoopEnd
            ) as e:  # pragma: no cover
                logging.error(str(e))

    def consume_message(
        self,
        value: Union[str, None] = None,
        key: Union[str, None] = None,
        headers: Union[dict, None] = None,
        amqp_properties: Union[dict, None] = None
    ) -> bool:
        headers = {} if headers is None else headers
        first_actor = self.consumers[0].actor

        logging.debug(
            'Analyzing a %s message from %r addr=%r key=%r value=%r headers=%r',
            SERVICE_TYPES[first_actor.service.type],
            first_actor.consumer.topic,
            first_actor.service.address,
            key,
            value,
            headers
        )

        matched_consumer = None

        amqp_properties = {} if amqp_properties is None else {k: v for k, v in amqp_properties.items() if v is not None}
        async_handler = None
        for _consumer in self.consumers:
            async_handler = AsyncHandler(
                _consumer.actor.service.type,
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
                amqp_properties=amqp_properties,
                context=_consumer.actor.context,
                params=_consumer.actor.params
            )
            if _consumer.match(key, value, headers, async_handler, amqp_properties=amqp_properties):
                matched_consumer = _consumer
                break

        if matched_consumer is None:
            logging.debug(
                'NOT MATCHED the %s message: addr=%r topic=%r key=%r value=%r headers=%r',
                SERVICE_TYPES[first_actor.service.type],
                first_actor.service.address,
                first_actor.consumer.topic,
                key,
                value,
                headers
            )
            return False

        logging.info(
            'Consumed a %s message from %r by %r',
            SERVICE_TYPES[matched_consumer.actor.service.type],
            matched_consumer.actor.consumer.topic,
            '%s' % (matched_consumer.actor.name if matched_consumer.actor.name is not None else '#%s' % matched_consumer.actor.id),
        )
        logging.debug(
            '[%s] MATCHED the %s message: addr=%r topic=%r key=%r value=%r headers=%r',
            '%s' % (matched_consumer.actor.name if matched_consumer.actor.name is not None else '#%s' % matched_consumer.actor.id),
            SERVICE_TYPES[matched_consumer.actor.service.type],
            matched_consumer.actor.service.address,
            matched_consumer.actor.consumer.topic,
            key,
            '%s...' % value[:LOGGING_LENGTH_LIMIT] if len(value) > LOGGING_LENGTH_LIMIT else value,
            headers
        )

        self.after_consume_match(
            matched_consumer,
            async_handler,
            value,
            key,
            headers
        )

        return True

    @abstractmethod
    def consume(self) -> None:
        raise NotImplementedError


class AsyncProducerPayload:

    def __init__(
        self,
        value: str,
        key: Union[str, None] = None,
        headers: Union[dict, None] = None,
        amqp_properties: Union[dict, None] = None,
        tag: Union[str, None] = None,
        enable_topic_creation: bool = False
    ):
        self.value = value
        self.key = key
        self.headers = {} if headers is None else headers
        self.amqp_properties = amqp_properties
        self.tag = tag
        self.enable_topic_creation = enable_topic_creation


class AsyncProducerPayloadList:

    def __init__(self):
        self.list = []

    def add_payload(self, payload: AsyncProducerPayload) -> None:
        self.list.append(payload)


class AsyncProducer(AsyncConsumerProducerBase):

    producers = []

    def __init__(
        self,
        topic: str,
        payload_list: AsyncProducerPayloadList
    ):
        self._index = len(AsyncProducer.producers)
        super().__init__(self._index, topic)
        self.payload_list = payload_list
        self.payload_iteration = 0
        self.dataset_iteration = 0
        self.lock_payload = False
        self.lock_dataset = False
        AsyncProducer.producers.append(self)

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

    def get_current_payload(self) -> AsyncProducerPayload:
        return self.payload_list.list[self.payload_iteration]

    def is_payload_locked(self) -> bool:
        return self.lock_payload

    def check_dataset_lock(self) -> None:
        if self.is_dataset_locked():
            raise AsyncProducerDatasetLoopEnd(self.actor.get_hint())

    def check_dataset(self) -> bool:
        if all('tag' in row and row['tag'] not in self.actor.service.tags for row in self.actor._dataset.payload):
            return False
        return True

    def increment_dataset_iteration(self) -> None:
        self.dataset_iteration += 1
        if self.dataset_iteration > len(self.actor._dataset.payload) - 1:
            if not self.actor.dataset_looped:
                self.lock_dataset = True
            self.dataset_iteration = 0

    def get_current_dataset_row(self) -> dict:
        return self.actor._dataset.payload[self.dataset_iteration]

    def is_dataset_locked(self) -> bool:
        if self.actor.dataset is None:
            return False
        return self.lock_dataset

    def get_payload(self) -> Union[AsyncProducerPayload, None]:
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
                return None
        return payload

    def delay(self, ignore_delay: bool) -> None:
        if not ignore_delay and self.actor.delay is not None:
            _delay(self.actor.delay)

    def get_dataset_row(self, async_handler: AsyncHandler) -> Tuple[dict, bool]:
        row = None
        set_row = False
        if self.actor.dataset is not None:
            self.actor._dataset = async_handler.load_dataset(self.actor.dataset)
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
        return row, set_row

    def interract_with_async_handler(
        self,
        consumed: Union[Consumed, None],
        payload: AsyncProducerPayload,
        async_handler: AsyncHandler
    ) -> None:
        definition = self.actor.service.definition
        if definition is not None:
            async_handler.headers = _merge_global_headers(
                definition.data['globals'] if 'globals' in definition.data else {},
                payload
            )

        if consumed is not None:
            async_handler.custom_context.update({
                'consumed': consumed
            })

        row, set_row = self.get_dataset_row(async_handler)

        if set_row:
            for key, value in row.items():
                async_handler.custom_context[key] = value

    @abstractmethod
    def _produce(self, key: str, value: str, headers: dict, payload: AsyncProducerPayload) -> None:
        raise NotImplementedError

    def produce(
        self,
        consumed: Consumed = None,
        context: Union[dict, None] = None,
        ignore_delay: bool = False
    ) -> None:
        context = {} if context is None else context
        payload = self.get_payload()
        if payload is None:
            return

        context = copy.deepcopy(context)

        async_handler = AsyncHandler(
            self.actor.service.type,
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
            amqp_properties={} if payload.amqp_properties is None else {k: v for k, v in payload.amqp_properties.items() if v is not None},
            context=context,
            params=self.actor.params
        )

        self.delay(ignore_delay)
        self.interract_with_async_handler(
            consumed,
            payload,
            async_handler
        )

        # Templating
        key, value, headers, amqp_properties = async_handler.render_attributes()

        if self.actor.service.type == 'amqp':
            try:
                self._produce(key, value, headers, payload, amqp_properties=amqp_properties)
            except AMQPConnectionError:
                return
        else:
            self._produce(key, value, headers, payload)

        logging.info(
            'Produced a %s message into %r from %r',
            SERVICE_TYPES[self.actor.service.type],
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

        log_record = async_handler.finish()
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


class AsyncActor:

    actors = []

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
        self.stop = False
        self._index = len(AsyncActor.actors)
        AsyncActor.actors.append(self)

    def get_hint(self) -> str:
        return self.name if self.name is not None else '#%d' % self.id

    def set_consumer(self, consumer: AsyncConsumer) -> None:
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

    def set_producer(self, producer: AsyncProducer) -> None:
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

    def set_delay(self, value: Union[int, float, None]) -> None:
        if value is None:
            return

        self.delay = value

    def set_limit(self, value: int) -> None:
        self.limit = value

    def set_dataset(self, dataset: Union[list, str]) -> None:
        self.dataset = dataset

    def run_produce_loop(self) -> None:
        if self.consumer is not None or self.producer is None or self.delay is None:
            return

        if self.limit is None:
            logging.debug('Running a %s loop (%s) indefinitely...', SERVICE_TYPES[self.service.type], self.get_hint())
        else:
            logging.debug('Running a %s loop (%s) for %d iterations...', SERVICE_TYPES[self.service.type], self.get_hint(), self.limit)

        while self.limit is None or self.limit > 0:
            if self.stop:  # pragma: no cover
                break

            try:
                self.producer.check_payload_lock()
                self.producer.check_dataset_lock()
                self.producer.produce()
            except (
                AsyncProducerPayloadLoopEnd,
                AsyncProducerDatasetLoopEnd
            ):
                break

            if self.delay is not None:
                _delay(self.delay)

            if self.limit is not None and self.limit > 0:
                self.limit -= 1

        logging.debug('%s loop (%s) is finished.', SERVICE_TYPES[self.service.type], self.get_hint())


class AsyncService:

    services = []

    def __init__(
        self,
        address: str,
        name: Union[str, None] = None,
        definition=None,
        _id: Union[int, None] = None,
        ssl: bool = False
    ):
        self.address = address
        self.name = name
        self.definition = definition
        self.type = None
        self.actors = []
        self.id = _id
        self.ssl = ssl
        self.tags = []
        self._index = len(AsyncService.services)
        AsyncService.services.append(self)

    def add_actor(self, actor: AsyncActor) -> None:
        actor.service = self
        self.actors.append(actor)
