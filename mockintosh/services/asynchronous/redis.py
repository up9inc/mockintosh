#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains AMQP related classes.
"""

# import sys
import time
import logging
from typing import (
    Union
)

from rsmq import RedisSMQ
from rsmq.cmd.exceptions import QueueAlreadyExists
from redis.exceptions import ConnectionError as RedisConnectionError

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

INFINITE_QUEUE_VISIBILITY = 30  # TODO: How do we make it infinite? `sys.maxsize`?


def _create_topic(address: str, topic: str, ssl: bool = False):
    host, port = address.split(':')
    queue = RedisSMQ(host=host, port=port, qname=topic)

    try:
        queue.createQueue(delay=0).vt(INFINITE_QUEUE_VISIBILITY).execute()
    except QueueAlreadyExists:
        pass
    logging.info('Queue %s created', topic)
    queue.quit()


class RedisConsumerProducerBase(AsyncConsumerProducerBase):
    pass


class RedisConsumer(AsyncConsumer):

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
        super().__init__(
            topic,
            schema=schema,
            value=value,
            key=key,
            headers=headers,
            amqp_properties=amqp_properties,
            capture_limit=capture_limit,
            enable_topic_creation=enable_topic_creation
        )
        self.match_key = None
        self.match_headers = {}


class RedisConsumerGroup(AsyncConsumerGroup):

    def consume(self) -> None:
        host, port = self.consumers[0].actor.service.address.split(':')
        while True:
            if self.stop:
                break

            try:
                queue = RedisSMQ(host=host, port=port, qname=self.consumers[0].topic)

                if any(consumer.enable_topic_creation for consumer in self.consumers):
                    try:
                        queue.createQueue(delay=0).vt(INFINITE_QUEUE_VISIBILITY).execute()
                    except QueueAlreadyExists:
                        pass

                try:
                    msg = queue.receiveMessage().exceptions(False).execute()

                    if msg:
                        self.consume_message(
                            key=None,
                            value=msg['message'],
                            headers={}
                        )
                except AttributeError:
                    pass

                queue.quit()
            except RedisConnectionError:
                logging.warning('Couldn\'t establish a connection to Redis instance at %s:%s', host, port)

            time.sleep(1)

    def _stop(self):
        self.stop = True


class RedisProducerPayload(AsyncProducerPayload):
    pass


class RedisProducerPayloadList(AsyncProducerPayloadList):
    pass


class RedisProducer(AsyncProducer):

    def _produce(self, key: str, value: str, headers: dict, payload: AsyncProducerPayload) -> None:
        host, port = self.actor.service.address.split(':')
        try:
            queue = RedisSMQ(host=host, port=port, qname=self.topic)

            if payload.enable_topic_creation:
                try:
                    queue.createQueue(delay=0).vt(INFINITE_QUEUE_VISIBILITY).execute()
                except QueueAlreadyExists:
                    pass

            try:
                queue.sendMessage(delay=0).message(value).execute()
            except AttributeError:
                pass

            queue.quit()
        except RedisConnectionError:
            logging.warning('Couldn\'t establish a connection to Redis instance at %s:%s', host, port)
            raise


class RedisActor(AsyncActor):
    pass


class RedisService(AsyncService):

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
        self.type = 'redis'


def build_single_payload_producer(
    topic: str,
    value: str,
    key: Union[str, None] = None,
    headers: Union[dict, None] = None,
    tag: Union[str, None] = None,
    enable_topic_creation: bool = False
) -> RedisProducer:
    payload_list = RedisProducerPayloadList()
    payload = RedisProducerPayload(
        value,
        key=key,
        headers={} if headers is None else headers,
        tag=tag
    )
    payload_list.add_payload(payload)
    return RedisProducer(topic, payload_list)
