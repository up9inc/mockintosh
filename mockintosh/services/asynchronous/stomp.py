#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains STOMP related classes.
"""

from typing import (
    Union
)

from stomp import Connection, ConnectionListener

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


def connect_and_subscribe(conn, topic: str):
    conn.connect(wait=True)
    conn.subscribe(destination='/queue/%s' % topic, id=1, ack='auto')


class StompConsumerProducerBase(AsyncConsumerProducerBase):
    pass


class StompConsumer(AsyncConsumer):
    pass


class StompConsumerGroup(AsyncConsumerGroup):

    def consume(self) -> None:
        host, port = self.actor.service.address.split(':')
        conn = Connection([(host, int(port))], heartbeats=(4000, 4000))
        conn.set_listener('', StompListener(conn, self))
        connect_and_subscribe(conn)


class StompListener(ConnectionListener):

    def __init__(self, conn, consumer_group: StompConsumerGroup):
        self.conn = conn
        self.consumer_group = consumer_group

    def on_error(self, frame):
        print('received an error "%s"' % frame.body)

    def on_message(self, frame):
        print('received a message "%s"' % frame.body)

        self.consumer_group.consume_message(
            key=frame.key,
            value=frame.value,
            headers=frame.headers
        )

    def on_disconnected(self):
        print('disconnected')
        connect_and_subscribe(self.conn, self.consumers[0].topic)


class StompProducerPayload(AsyncProducerPayload):
    pass


class StompProducerPayloadList(AsyncProducerPayloadList):
    pass


class StompProducer(AsyncProducer):

    def _produce(self, key: str, value: str, headers: dict, payload: AsyncProducerPayload) -> None:
        host, port = self.actor.service.address.split(':')
        conn = Connection([(host, int(port))])

        conn.connect(wait=True)
        conn.send('/queue/%s' % self.topic, value)

        conn.close()


class StompActor(AsyncActor):
    pass


class StompService(AsyncService):
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
