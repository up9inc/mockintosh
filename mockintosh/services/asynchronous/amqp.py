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
from pika.exceptions import ChannelClosedByBroker, StreamLostError, AMQPConnectionError

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

EXCHANGE = 'topic_logs'
EXCHANGE_TYPE = 'topic'


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
    logging.info('Queue %s created', topic)
    connection.close()


class AmqpConsumerProducerBase(AsyncConsumerProducerBase):
    pass


class AmqpConsumer(AsyncConsumer):
    pass


class AmqpConsumerGroup(AsyncConsumerGroup):

    def callback(self, ch, method, properties: BasicProperties, body: bytes):
        self.consume_message(
            key=None if not method.routing_key else method.routing_key,
            value=_decoder(body),
            headers=properties.headers,
            amqp_properties={x: getattr(properties, x) for x in properties.__dict__ if x != 'headers'}
        )

    def consume(self) -> None:
        host, port = self.consumers[0].actor.service.address.split(':')
        connection_error_logged = False
        queue_error_logged = False
        while True:
            try:
                connection = BlockingConnection(
                    ConnectionParameters(host=host, port=port)
                )
                try:
                    self.channel = connection.channel()

                    queue = self.consumers[0].topic

                    if any(consumer.enable_topic_creation for consumer in self.consumers):
                        self.channel.queue_declare(queue=queue)
                        logging.info('Queue %s created', queue)
                    else:
                        self.channel.queue_declare(queue=queue, passive=True)

                    exchange = '%s_%s' % (EXCHANGE, queue)

                    self.channel.exchange_declare(exchange=exchange, exchange_type=EXCHANGE_TYPE)

                    self.channel.queue_bind(
                        exchange=exchange,
                        queue=queue,
                        routing_key='#'
                    )

                    self.channel.basic_consume(queue=queue, on_message_callback=self.callback, auto_ack=True)

                    try:
                        self.channel.start_consuming()
                    except StreamLostError:
                        pass
                    except AttributeError:
                        pass

                    break
                except ChannelClosedByBroker as e:
                    connection.close()
                    if not queue_error_logged:
                        logging.info('Queue %s does not exist: %s', queue, e)
                        queue_error_logged = True
                    time.sleep(1)
            except AMQPConnectionError:
                if not connection_error_logged:
                    logging.warning('Couldn\'t establish a connection to AMQP instance at %s:%s', host, port)
                    connection_error_logged = True
                time.sleep(1)
                continue

    def _stop(self):
        try:
            self.channel.stop_consuming()
        except StreamLostError:
            pass


class AmqpProducerPayload(AsyncProducerPayload):
    pass


class AmqpProducerPayloadList(AsyncProducerPayloadList):
    pass


class AmqpProducer(AsyncProducer):

    def _produce(self, key: str, value: str, headers: dict, payload: AsyncProducerPayload, amqp_properties: Union[dict, None] = None) -> None:
        host, port = self.actor.service.address.split(':')
        connection = BlockingConnection(
            ConnectionParameters(host=host, port=port)
        )
        channel = connection.channel()

        queue = self.topic

        try:
            try:
                if payload.enable_topic_creation:
                    channel.queue_declare(queue=queue)
                    logging.info('Queue %s created', queue)
                else:
                    channel.queue_declare(queue=queue, passive=True)

                exchange = '%s_%s' % (EXCHANGE, queue)

                channel.exchange_declare(exchange=exchange, exchange_type=EXCHANGE_TYPE)

                channel.basic_publish(
                    exchange=exchange,
                    routing_key=key if key is not None else '',
                    body=value,
                    properties=BasicProperties(
                        headers=headers,
                        **amqp_properties
                    )
                )
            except ChannelClosedByBroker as e:
                logging.info('Queue %s does not exist: %s', queue, e)
        except AMQPConnectionError:
            logging.warning('Couldn\'t establish a connection to AMQP instance at %s:%s', host, port)
            raise

        connection.close()


class AmqpActor(AsyncActor):
    pass


class AmqpService(AsyncService):

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
        self.type = 'amqp'


def build_single_payload_producer(
    topic: str,
    value: str,
    key: Union[str, None] = None,
    headers: Union[dict, None] = None,
    tag: Union[str, None] = None,
    enable_topic_creation: bool = False
) -> AmqpProducer:
    payload_list = AmqpProducerPayloadList()
    payload = AmqpProducerPayload(
        value,
        key=key,
        headers={} if headers is None else headers,
        tag=tag
    )
    payload_list.add_payload(payload)
    return AmqpProducer(topic, payload_list)
