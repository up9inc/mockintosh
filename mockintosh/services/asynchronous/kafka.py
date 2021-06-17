#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains Kafka related classes.
"""

import time
import logging
from typing import (
    Union
)

from confluent_kafka import Producer, Consumer, Message
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka.cimpl import KafkaException

from mockintosh.services.asynchronous import (
    AsyncConsumerProducerBase,
    AsyncConsumer,
    AsyncConsumerGroup,
    AsyncProducerPayload,
    AsyncProducerPayloadList,
    AsyncProducer,
    AsyncActor,
    AsyncService
)


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


class KafkaConsumerProducerBase(AsyncConsumerProducerBase):
    pass


class KafkaConsumer(AsyncConsumer):
    pass


class KafkaConsumerGroup(AsyncConsumerGroup):

    def consume(self) -> None:
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

        self.consume_loop(consumer)

    def consume_loop(self, consumer) -> None:
        while True:
            if self.stop:  # pragma: no cover
                consumer.close()
                break

            msg = self.poll_message(consumer)
            if not self.is_consumed(msg):
                continue

            key, value, headers = _decoder(msg.key()), _decoder(msg.value()), _headers_decode(msg.headers())

            self.consume_message(
                key=key,
                value=value,
                headers=headers
            )

    def poll_message(self, consumer: Consumer) -> Union[Message, None]:
        return consumer.poll(1.0)

    def is_consumed(self, msg: Union[Message, None]) -> bool:
        if msg is None:
            return False

        if msg.error():  # pragma: no cover
            logging.warning("Consumer error: %s", msg.error())
            return False

        return True

    def _stop(self):
        self.stop = True


class KafkaProducerPayload(AsyncProducerPayload):
    pass


class KafkaProducerPayloadList(AsyncProducerPayloadList):
    pass


class KafkaProducer(AsyncProducer):

    def _produce(self, key: str, value: str, headers: dict, payload: AsyncProducerPayload) -> None:
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


class KafkaActor(AsyncActor):
    pass


class KafkaService(AsyncService):

    def __init__(
        self,
        address: str,
        name: Union[str, None] = None,
        definition=None,
        _id: Union[int, None] = None,
        ssl: bool = False
    ):
        super().__init__(
            address,
            name=name,
            definition=definition,
            _id=_id,
            ssl=ssl
        )
        self.type = 'kafka'


def build_single_payload_producer(
    topic: str,
    value: str,
    key: Union[str, None] = None,
    headers: Union[dict, None] = None,
    tag: Union[str, None] = None,
    enable_topic_creation: bool = False
) -> KafkaProducer:
    payload_list = KafkaProducerPayloadList()
    payload = KafkaProducerPayload(
        value,
        key=key,
        headers={} if headers is None else headers,
        tag=tag
    )
    payload_list.add_payload(payload)
    return KafkaProducer(topic, payload_list)
