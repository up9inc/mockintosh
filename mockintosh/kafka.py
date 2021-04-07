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


class KafkaConsumer:

    def __init__(
        self,
        topic: str
    ):
        self.topic = topic
        self.log = []

    def json(self):
        return {
            'topic': self.topic
        }


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

    def __init__(self, name: str = None):
        self.name = name
        self.counters = {}
        self.consumer = None
        self.producer = None
        self.delay = None
        self.limit = None

    def set_consumer(self, consumer: KafkaConsumer):
        self.consumer = consumer

    def set_producer(self, producer: KafkaProducer):
        self.producer = producer

    def set_delay(self, value: Union[int, float]):
        self.delay = value

    def set_limit(self, value: int):
        self.limit = value

    def json(self):
        data = {}

        if self.name is not None:
            data['name'] = self.name

        if self.consumer is not None:
            data['consume'] = self.consumer.json()

        if self.producer is not None:
            data['produce'] = self.producer.json()

        if self.delay is not None:
            data['delay'] = self.delay

        if self.limit is not None:
            data['limit'] = self.limit

        return data

class KafkaService:

    def __init__(self, address: str, name: str = None):
        self.address = address
        self.name = name
        self.actors = []

    def get_actor(self, index: int):
        return actor[index]

    def add_actor(self, actor: KafkaActor):
        self.actors.append(actor)


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


def _merge_global_headers(_globals, kafka_producer: KafkaProducer):
    headers = {}
    global_headers = _globals['headers'] if 'headers' in _globals else {}
    headers.update(global_headers)
    produce_data_headers = kafka_producer.headers
    headers.update(produce_data_headers)
    return headers


def produce(
    service: KafkaService,
    kafka_producer: KafkaProducer,
    definition,
    delay: int = 0,
    consumed: Consumed = None
) -> None:
    _delay(delay)

    _create_topic(service.address, kafka_producer.topic)

    # Templating
    kafka_handler = KafkaHandler(
        definition.source_dir,
        definition.template_engine,
        definition.rendering_queue
    )
    if consumed is not None:
        kafka_handler.custom_context = {
            'consumed': consumed
        }
    key, value, headers = kafka_handler.render_attributes(
        kafka_producer.key,
        kafka_producer.value,
        kafka_producer.headers
    )

    # Producing
    producer = Producer({'bootstrap.servers': service.address})
    producer.poll(0)
    producer.produce(kafka_producer.topic, value, key=key, headers=headers, callback=_kafka_delivery_report)
    producer.flush()

    logging.info('Produced Kafka message: addr=\'%s\' topic=\'%s\' key=\'%s\' value=\'%s\' headers=\'%s\'' % (
        service.address,
        kafka_producer.topic,
        key,
        value,
        headers
    ))


def consume(
    service: KafkaService,
    actor: KafkaActor,
    definition = None,
    log: Union[None, list] = None,
    stop: dict = {}
) -> None:
    _create_topic(service.address, actor.consumer.topic)

    if actor is not None:
        actor.consumer.log = []

    consumer = Consumer({
        'bootstrap.servers': service.address,
        'group.id': '0',
        'auto.offset.reset': 'earliest'
    })
    consumer.subscribe([actor.consumer.topic])

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
            service.address,
            actor.consumer.topic,
            key,
            value,
            headers
        ))

        if definition is not None:
            actor.consumer.log.append(
                (key, value, headers)
            )

        if log is not None:  # pragma: no cover
            log.append(
                (key, value, headers)
            )

        if actor.producer is not None:
            consumed = Consumed()
            consumed.key = key
            consumed.value = value
            consumed.headers = headers

            if definition is not None:
                actor.producer.headers = _merge_global_headers(
                    definition.data['globals'] if 'globals' in definition.data else {},
                    actor.producer
                )

            t = threading.Thread(target=produce, args=(
                service,
                actor.producer,
                definition
            ), kwargs={
                'delay': actor.delay,
                'consumed': consumed
            })
            t.daemon = True
            t.start()


def _run_produce_loop(definition, service: KafkaService, actor: KafkaActor):
    if actor.limit is None:
        logging.info('Running a Kafka loop indefinitely...')
        actor.limit = -1
    else:
        logging.info('Running a Kafka loop for %d iterations...' % actor.limit)

    while actor.limit == -1 or actor.limit > 0:

        actor.producer.headers = _merge_global_headers(
            definition.data['globals'] if 'globals' in definition.data else {},
            actor.producer
        )

        produce(service, actor.producer, definition)

        _delay(actor.delay)

        if actor.limit > 1:
            actor.limit -= 1

    logging.info('Kafka loop is finished.')


def run_loops(definition):
    for service_id, service in enumerate(definition.data['kafka_services']):
        for actor_id, actor in enumerate(service.actors):
            if actor.consumer is None and actor.producer is not None and actor.delay is not None:
                t = threading.Thread(target=_run_produce_loop, args=(definition, service, actor))
                t.daemon = True
                t.start()

            if actor.consumer is not None:
                kafka_producer = actor.producer
                t = threading.Thread(target=consume, args=(
                    service,
                    actor
                ), kwargs={
                    'definition': definition,
                })
                t.daemon = True
                t.start()
