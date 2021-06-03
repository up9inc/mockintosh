#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains STOMP related classes.
"""

from typing import (
    Union
)

from pika import BlockingConnection, ConnectionParameters

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


class AmqpConsumerProducerBase(AsyncConsumerProducerBase):
    pass


class AmqpConsumer(AsyncConsumer):
    pass


class AmqpConsumerGroup(AsyncConsumerGroup):

    def callback(self, ch, method, properties, body):
        self.consume_message(
            key=None,
            value=body,
            headers={}
        )

    def consume(self) -> None:
        host, port = self.consumers[0].actor.service.address.split(':')
        connection = BlockingConnection(
            ConnectionParameters(host=host, port=port)
        )
        channel = connection.channel()

        queue = self.consumers[0].topic

        if any(consumer.enable_topic_creation for consumer in self.consumers):
            channel.queue_declare(queue=queue)
        else:
            channel.queue_declare(queue=queue, passive=True)

        channel.basic_consume(queue=queue, on_message_callback=self.callback, auto_ack=True)
        channel.start_consuming()


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

        if payload.enable_topic_creation:
            channel.queue_declare(queue=queue)
        else:
            channel.queue_declare(queue=queue, passive=True)

        channel.basic_publish(
            exchange='',
            routing_key=key,
            body=value
        )
        connection.close()


class AmqpActor(AsyncActor):
    pass


class AmqpService(AsyncService):
    pass


def run_loops():
    pass


def build_single_payload_producer(
    topic: str,
    value: str,
    key: Union[str, None] = None,
    headers: dict = {},
    tag: Union[str, None] = None,
    enable_topic_creation: bool = False
):
    pass
