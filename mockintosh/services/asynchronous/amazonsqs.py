#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains Amazon SQS related classes.
"""

import time
import logging
from os import environ
from urllib.parse import urlparse
from uuid import uuid4
from typing import (
    Union
)

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError
from boto3.resources.base import ServiceResource

from mockintosh.constants import PROGRAM
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


def _netloc_to_host(netloc: str, username: Union[str, None], password: Union[str, None], port: str) -> str:
    last = len(str(port)) + 1
    if username is None or password is None:
        return netloc[:-last]
    else:
        first = len(username) + len(password) + 2
        return netloc[first:-last]


def _create_topic_base(sqs: ServiceResource, topic: str) -> None:
    try:
        try:
            sqs.get_queue_by_name(QueueName='%s.fifo' % topic)
        except sqs.meta.client.exceptions.QueueDoesNotExist:
            sqs.create_queue(
                QueueName='%s.fifo' % topic,
                Attributes={
                    'DelaySeconds': '0',
                    'MessageRetentionPeriod': '86400',
                    'FifoQueue': 'true'
                }
            )
            logging.info('Queue %s created', topic)
    except ClientError:
        pass


def _get_resouce(host, parsed):
    return boto3.resource(
        'sqs',
        endpoint_url='%s://%s:%s' % (parsed.scheme, host, parsed.port),
        region_name=parsed.fragment,
        aws_secret_access_key=environ.get('AWS_SECRET_ACCESS_KEY', '' if parsed.password is None else parsed.password),
        aws_access_key_id=environ.get('AWS_ACCESS_KEY_ID', '' if parsed.username is None else parsed.username),
        use_ssl=True if parsed.scheme == 'https' else False
    )


def _create_topic(address: str, topic: str, ssl: bool = False) -> None:
    parsed = urlparse(address)
    host = _netloc_to_host(parsed.netloc, parsed.username, parsed.password, parsed.port)

    sqs = _get_resouce(host, parsed)

    _create_topic_base(sqs, topic)


def _map_attr(headers: dict) -> dict:
    data = {}
    for key, value in headers.items():
        data[key] = {}
        if isinstance(value, (int, float)):
            data[key]['DataType'] = 'Number'
        elif isinstance(value, (int, str)):
            data[key]['DataType'] = 'String'
        else:
            raise Exception
        data[key]['StringValue'] = str(value)

    return data


def _map_attr_inverse(headers: dict) -> dict:
    data = {}
    for key, value in headers.items():
        val = value['StringValue']
        if value['DataType'] == 'Number':
            val = int(val)  # TODO: What about float?
        data[key] = val

    return data


class AmazonsqsConsumerProducerBase(AsyncConsumerProducerBase):
    pass


class AmazonsqsConsumer(AsyncConsumer):
    pass


class AmazonsqsConsumerGroup(AsyncConsumerGroup):

    def consume(self) -> None:
        connection_error_logged = False
        parsed = urlparse(self.consumers[0].actor.service.address)
        host = _netloc_to_host(parsed.netloc, parsed.username, parsed.password, parsed.port)
        while True:
            try:
                sqs = _get_resouce(host, parsed)

                if any(consumer.enable_topic_creation for consumer in self.consumers):
                    _create_topic_base(sqs, self.consumers[0].topic)

                queue_error_logged = False
                while True:
                    if self.stop:
                        break

                    try:
                        queue = sqs.get_queue_by_name(QueueName='%s.fifo' % self.consumers[0].topic)

                        for message in queue.receive_messages(
                            AttributeNames=['MessageGroupId'],
                            MessageAttributeNames=['All']
                        ):
                            key = message.attributes['MessageGroupId']
                            key = None if key == '%s_special_none' % PROGRAM else key
                            self.consume_message(
                                key=key,
                                value=message.body,
                                headers={} if message.message_attributes is None else _map_attr_inverse(message.message_attributes)
                            )
                            message.delete()
                    except sqs.meta.client.exceptions.QueueDoesNotExist as e:
                        if not queue_error_logged:
                            logging.info('Queue %s does not exist: %s', self.consumers[0].topic, e)
                            queue_error_logged = True

                    time.sleep(1)
                break
            except (KeyError, EndpointConnectionError):
                if not connection_error_logged:
                    logging.warning('Couldn\'t establish a connection to SQS')
                    connection_error_logged = True

    def _stop(self):
        self.stop = True


class AmazonsqsProducerPayload(AsyncProducerPayload):
    pass


class AmazonsqsProducerPayloadList(AsyncProducerPayloadList):
    pass


class AmazonsqsProducer(AsyncProducer):

    def _produce(self, key: str, value: str, headers: dict, payload: AsyncProducerPayload) -> None:
        key = '%s_special_none' % PROGRAM if key is None else key
        parsed = urlparse(self.actor.service.address)
        host = _netloc_to_host(parsed.netloc, parsed.username, parsed.password, parsed.port)

        try:
            sqs = _get_resouce(host, parsed)

            if payload.enable_topic_creation:
                _create_topic_base(sqs, self.topic)

            try:
                queue = sqs.get_queue_by_name(QueueName='%s.fifo' % self.topic)

                # `ContentBasedDeduplication` requires different `MessageBody` each time
                # so instead we set a unique `MessageDeduplicationId`.
                queue.send_message(
                    MessageGroupId=key,
                    MessageBody=value,
                    MessageAttributes=_map_attr(headers),
                    MessageDeduplicationId=str(uuid4())
                )
            except sqs.meta.client.exceptions.QueueDoesNotExist as e:
                logging.info('Queue %s does not exist: %s', self.topic, e)
        except (KeyError, EndpointConnectionError):
            logging.warning('Couldn\'t establish a connection to SQS')
            raise


class AmazonsqsActor(AsyncActor):
    pass


class AmazonsqsService(AsyncService):

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
        self.type = 'amazonsqs'


def build_single_payload_producer(
    topic: str,
    value: str,
    key: Union[str, None] = None,
    headers: Union[dict, None] = None,
    tag: Union[str, None] = None,
    enable_topic_creation: bool = False
) -> AmazonsqsProducer:
    payload_list = AmazonsqsProducerPayloadList()
    payload = AmazonsqsProducerPayload(
        value,
        key=key,
        headers={} if headers is None else headers,
        tag=tag
    )
    payload_list.add_payload(payload)
    return AmazonsqsProducer(topic, payload_list)
