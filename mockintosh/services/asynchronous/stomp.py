#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains STOMP related classes.
"""

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
    pass


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
