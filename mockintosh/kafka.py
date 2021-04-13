#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains Kafka related methods.
"""

import logging
import threading
from typing import (
    Union
)

from confluent_kafka import Producer, Consumer
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka.cimpl import KafkaException

from mockintosh.helpers import _delay
from mockintosh.handlers import KafkaHandler
from mockintosh.replicas import Consumed


def _kafka_delivery_report(err, msg):
    if err is not None:  # pragma: no cover
        logging.info('Message delivery failed: {}'.format(err))
    else:
        logging.info('Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))


def _create_topic(address: str, topic: str):
    # Topic creation
    admin_client = AdminClient({'bootstrap.servers': address})
    new_topics = [NewTopic(topic, num_partitions=1, replication_factor=1)]
    futures = admin_client.create_topics(new_topics)

    for topic, future in futures.items():
        try:
            future.result()
            logging.info('Topic {} created'.format(topic))
        except KafkaException as e:
            logging.info('Failed to create topic {}: {}'.format(topic, e))


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


def _merge_global_headers(_globals, kafka_producer):
    headers = {}
    global_headers = _globals['headers'] if 'headers' in _globals else {}
    headers.update(global_headers)
    produce_data_headers = kafka_producer.headers
    headers.update(produce_data_headers)
    return headers


class KafkaConsumer:

    def __init__(
        self,
        topic: str
    ):
        self.topic = topic
        self.actor = None
        self.log = []
        self.internal_endpoint_id = None

    def consume(self, stop: dict = {}) -> None:
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
            False,
            service_id=self.actor.service.id
        )

        _create_topic(self.actor.service.address, self.topic)

        if self.actor is not None:
            self.log = []

        consumer = Consumer({
            'bootstrap.servers': self.actor.service.address,
            'group.id': '0',
            'auto.offset.reset': 'earliest'
        })
        consumer.subscribe([self.actor.consumer.topic])

        while True:
            if stop.get('val', False):  # pragma: no cover
                break

            msg = consumer.poll(1.0)

            if msg is None:
                continue

            if msg.error():  # pragma: no cover
                logging.warning("Consumer error: {}".format(msg.error()))
                continue

            key, value, headers = _decoder(msg.key()), _decoder(msg.value()), _headers_decode(msg.headers())

            logging.info('Consumed Kafka message: addr=\'%s\' topic=\'%s\' key=\'%s\' value=\'%s\' headers=\'%s\'' % (
                self.actor.service.address,
                self.actor.consumer.topic,
                key,
                value,
                headers
            ))

            self.log.append(
                (key, value, headers)
            )

            kafka_handler.set_response(
                key=key, value=value, headers=headers
            )

            kafka_handler.finish()

            if self.actor.producer is not None:
                consumed = Consumed()
                consumed.key = key
                consumed.value = value
                consumed.headers = headers

                t = threading.Thread(target=self.actor.producer.produce, args=(), kwargs={
                    'consumed': consumed
                })
                t.daemon = True
                t.start()


class KafkaProducer:
    def __init__(
        self,
        topic: str,
        value: str,
        key: Union[str, None] = None,
        headers: dict = {}
    ):
        self.topic = topic
        self.value = value
        self.key = key
        self.headers = headers
        self.actor = None
        self.internal_endpoint_id = None

    def produce(self, consumed: Consumed = None) -> None:
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
            value=self.value,
            key=self.key,
            headers=self.headers
        )

        if self.actor.delay is not None:
            _delay(self.actor.delay)

        _create_topic(self.actor.service.address, self.topic)

        definition = self.actor.service.definition
        if definition is not None:
            kafka_handler.headers = _merge_global_headers(
                definition.data['globals'] if 'globals' in definition.data else {},
                self
            )

        if consumed is not None:
            kafka_handler.custom_context = {
                'consumed': consumed
            }

        # Templating
        key, value, headers = kafka_handler.render_attributes()

        # Producing
        producer = Producer({'bootstrap.servers': self.actor.service.address})
        producer.poll(0)
        producer.produce(self.topic, value, key=key, headers=headers, callback=_kafka_delivery_report)
        producer.flush()

        logging.info('Produced Kafka message: addr=\'%s\' topic=\'%s\' key=\'%s\' value=\'%s\' headers=\'%s\'' % (
            self.actor.service.address,
            self.topic,
            key,
            value,
            headers
        ))

        kafka_handler.finish()

    def json(self):
        data = {
            'queue': self.topic,
            'value': self.value,
        }

        if self.key is not None:
            data['key'] = self.key

        if self.headers:
            data['headers'] = self.headers

        return data


class KafkaActor:

    def __init__(self, _id, name: str = None):
        self.id = _id
        self.name = name
        self.counters = {}
        self.consumer = None
        self.producer = None
        self.delay = None
        self.limit = None
        self.service = None

    def set_consumer(self, consumer: KafkaConsumer):
        self.consumer = consumer
        self.consumer.actor = self
        if self.service.definition.stats is None:
            return

        hint = '%s %s%s' % (
            'GET',
            self.consumer.topic,
            ' - %d' % self.id
        )
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
        self.service.definition.stats.services[self.service.id].add_endpoint(hint)
        self.producer.internal_endpoint_id = len(self.service.definition.stats.services[self.service.id].endpoints) - 1

    def set_delay(self, value: Union[int, float]):
        self.delay = value

    def set_limit(self, value: int):
        self.limit = value

    def json(self):
        data = {}

        if self.name is not None:
            data['name'] = self.name

        if self.producer is not None:
            data['produce'] = self.producer.json()

        if self.delay is not None:
            data['delay'] = self.delay

        if self.limit is not None:
            data['limit'] = self.limit

        return data


class KafkaService:

    def __init__(self, address: str, name: str = None, definition=None, _id: int = None):
        self.address = address
        self.name = name
        self.definition = definition
        self.actors = []
        self.id = _id

    def add_actor(self, actor: KafkaActor):
        actor.service = self
        self.actors.append(actor)


def _run_produce_loop(definition, service: KafkaService, actor: KafkaActor):
    if actor.limit is None:
        logging.info('Running a Kafka loop indefinitely...')
    else:
        logging.info('Running a Kafka loop for %d iterations...' % actor.limit)

    while actor.limit is None or actor.limit > 0:

        actor.producer.headers = _merge_global_headers(
            definition.data['globals'] if 'globals' in definition.data else {},
            actor.producer
        )

        actor.producer.produce()

        if actor.delay is not None:
            _delay(actor.delay)

        if actor.limit is not None and actor.limit > 0:
            actor.limit -= 1

    logging.info('Kafka loop is finished.')


def run_loops(definition):
    for service_id, service in enumerate(definition.data['kafka_services']):
        for actor_id, actor in enumerate(service.actors):
            if actor.consumer is None and actor.producer is not None and actor.delay is not None:
                t = threading.Thread(target=_run_produce_loop, args=(definition, service, actor), kwargs={})
                t.daemon = True
                t.start()

            if actor.consumer is not None:
                t = threading.Thread(target=actor.consumer.consume, args=(), kwargs={})
                t.daemon = True
                t.start()
