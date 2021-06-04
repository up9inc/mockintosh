#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains AMQP related classes.
"""

import time
import logging
from typing import (
    Union
)

from pika import BlockingConnection, ConnectionParameters
from pika.spec import BasicProperties
from pika.exceptions import ChannelClosedByBroker

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

def _create_topic(address: str, topic: str, ssl: bool = False):
    host, port = address.split(':')
    connection = BlockingConnection(
        ConnectionParameters(host=host, port=port)
    )
    channel = connection.channel()

    channel.queue_declare(queue=topic)
    connection.close()


class AmqpConsumerProducerBase(AsyncConsumerProducerBase):
    pass


class AmqpConsumer(AsyncConsumer):
    pass


class AmqpConsumerGroup(AsyncConsumerGroup):

    def callback(self, ch, method, properties: BasicProperties, body: bytes):
        self.consume_message(
            key=None,
            value=_decoder(body),
            headers=properties.headers
        )

    def consume(self) -> None:
        host, port = self.consumers[0].actor.service.address.split(':')
        while True:
            connection = BlockingConnection(
                ConnectionParameters(host=host, port=port)
            )
            try:
                channel = connection.channel()

                queue = self.consumers[0].topic

                if any(consumer.enable_topic_creation for consumer in self.consumers):
                    channel.queue_declare(queue=queue)
                else:
                    channel.queue_declare(queue=queue, passive=True)

                channel.basic_consume(queue=queue, on_message_callback=self.callback, auto_ack=True)
                channel.start_consuming()
                break
            except ChannelClosedByBroker as e:
                connection.close()
                logging.info('Queue %s does not exists: %s', queue, e)
                time.sleep(1)


class AmqpProducerPayload(AsyncProducerPayload):
    pass


class AmqpProducerPayloadList(AsyncProducerPayloadList):
    pass


class AmqpProducer(AsyncProducer):

    def _produce(self, key: str, value: str, headers: dict, payload: AsyncProducerPayload) -> None:
        host, port = self.actor.service.address.split(':')
        connection = BlockingConnection(
            ConnectionParameters(host=host, port=port)
        )
        channel = connection.channel()

        queue = self.topic

        try:
            if payload.enable_topic_creation:
                channel.queue_declare(queue=queue)
            else:
                channel.queue_declare(queue=queue, passive=True)

            channel.basic_publish(
                exchange='',
                routing_key=key,
                body=value,
                properties=BasicProperties(
                    headers=headers
                )
            )
        except ChannelClosedByBroker as e:
            logging.info('Queue %s does not exists: %s', queue, e)

        connection.close()


class AmqpActor(AsyncActor):
    pass


class AmqpService(AsyncService):

    def __init__(
        self,
        address: str,
        name: str = None,
        definition=None,
        _id: int = None,
        ssl: bool = False
    ):
        super().__init__(
            address,
            name=name,
            definition=definition,
            _id=_id,
            ssl=ssl
        )
        self.type = 'amqp'


def build_single_payload_producer(
    topic: str,
    value: str,
    key: Union[str, None] = None,
    headers: dict = {},
    tag: Union[str, None] = None,
    enable_topic_creation: bool = False
) -> AmqpProducer:
    payload_list = AmqpProducerPayloadList()
    payload = AmqpProducerPayload(
        value,
        key=key,
        headers=headers,
        tag=tag
    )
    payload_list.add_payload(payload)
    return AmqpProducer(topic, payload_list)
