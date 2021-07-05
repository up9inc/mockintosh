#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains MQTT related classes.
"""

import time
import logging
from typing import (
    Union
)

import paho.mqtt.client as mqtt
from paho.mqtt.publish import single

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
    pass


class MqttConsumerProducerBase(AsyncConsumerProducerBase):
    pass


class MqttConsumer(AsyncConsumer):
    pass


class MqttConsumerGroup(AsyncConsumerGroup):

    def on_connect(self, client, userdata, flags, rc):
        client.subscribe(self.consumers[0].topic)

    def on_message(self, client, userdata, msg):
        self.consume_message(
            key=None,
            value=_decoder(msg.payload),
            headers={}
        )

    def consume(self) -> None:
        host, port = self.consumers[0].actor.service.address.split(':')
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        connection_error_logged = False
        while True:
            try:
                self.client.connect(host, int(port), 60)
                self.client.loop_start()
                break
            except ConnectionRefusedError:
                if not connection_error_logged:
                    logging.warning('Couldn\'t establish a connection to MQTT instance at %s:%s', host, port)
                    connection_error_logged = True
                time.sleep(1)
                continue

    def _stop(self):
        self.client.loop_stop(force=False)


class MqttProducerPayload(AsyncProducerPayload):
    pass


class MqttProducerPayloadList(AsyncProducerPayloadList):
    pass


class MqttProducer(AsyncProducer):

    def _produce(self, key: str, value: str, headers: dict, payload: AsyncProducerPayload) -> None:
        host, port = self.actor.service.address.split(':')
        try:
            single(self.topic, payload=value, hostname=host, port=int(port))
        except ConnectionRefusedError:
            logging.warning('Couldn\'t establish a connection to MQTT instance at %s:%s', host, port)
            raise


class MqttActor(AsyncActor):
    pass


class MqttService(AsyncService):

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
        self.type = 'mqtt'


def build_single_payload_producer(
    topic: str,
    value: str,
    key: Union[str, None] = None,
    headers: Union[dict, None] = None,
    tag: Union[str, None] = None,
    enable_topic_creation: bool = False
) -> MqttProducer:
    payload_list = MqttProducerPayloadList()
    payload = MqttProducerPayload(
        value,
        key=key,
        headers={} if headers is None else headers,
        tag=tag
    )
    payload_list.add_payload(payload)
    return MqttProducer(topic, payload_list)
