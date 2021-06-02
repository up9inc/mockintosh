#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains STOMP related classes.
"""

from typing import (
    Union
)

from stomp import Connection

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


class StompConsumerProducerBase(AsyncConsumerProducerBase):
    pass


class StompConsumer(AsyncConsumer):
    pass


class StompConsumerGroup(AsyncConsumerGroup):
    pass


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
