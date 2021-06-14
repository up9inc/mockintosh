#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains Google Cloud Pub/Sub related classes.
"""

import os
import json
import time
import logging
from typing import (
    Union
)

from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient
from google.cloud.pubsub_v1.types import PublisherOptions
from google.auth.jwt import Credentials
from google.api_core.exceptions import NotFound, AlreadyExists
from google.auth.exceptions import DefaultCredentialsError
from grpc._channel import _InactiveRpcError

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


def _decoder(value):
    try:
        return value.decode()
    except (AttributeError, UnicodeDecodeError):
        return value


def _credentials(service_account_json: Union[str, None], _type: str) -> Credentials:
    service_account_info = None
    service_acount_json_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', service_account_json)
    if service_acount_json_path is None:
        logging.error('`GOOGLE_APPLICATION_CREDENTIALS` environment variable or `serviceAccountJson` field are not set!')
        return
    service_account_info = json.load(open(service_acount_json_path))
    audience = 'https://pubsub.googleapis.com/google.pubsub.v1.%s' % _type

    return Credentials.from_service_account_info(
        service_account_info, audience=audience
    )


def _publisher(service_account_json: Union[str, None]) -> PublisherClient:
    try:
        return PublisherClient(
            credentials=_credentials(service_account_json, 'Publisher'),
            publisher_options = PublisherOptions(enable_message_ordering=True)
        )
    except DefaultCredentialsError:
        logging.error('`GOOGLE_APPLICATION_CREDENTIALS` environment variable or `serviceAccountJson` field are not set!')


def _subscriber(service_account_json: Union[str, None]) -> SubscriberClient:
    try:
        return SubscriberClient(credentials=_credentials(service_account_json, 'Subscriber'))
    except DefaultCredentialsError:
        logging.error('`GOOGLE_APPLICATION_CREDENTIALS` environment variable or `serviceAccountJson` field are not set!')


def _get_topic_path(project_id: Union[str, None], topic: str) -> str:
    return 'projects/{project_id}/topics/{topic}'.format(
        project_id=os.environ.get('GOOGLE_CLOUD_PROJECT', project_id),
        topic=topic
    )


def _create_topic(service_account_json: str, project_id: str, topic: str) -> None:
    publisher = _publisher(service_account_json)
    if publisher is None:
        return
    topic_path = _get_topic_path(project_id, topic)

    try:
        publisher.create_topic(name=topic_path)
    except AlreadyExists:
        pass
    except NotFound:
        logging.error('`GOOGLE_CLOUD_PROJECT` environment variable or `projectId` field are not set!')
        return


class PubsubConsumerProducerBase(AsyncConsumerProducerBase):
    pass


class PubsubConsumer(AsyncConsumer):
    pass


class PubsubConsumerGroup(AsyncConsumerGroup):

    def callback(self, message):
        self.consume_message(
            key=message.ordering_key,
            value=_decoder(message.data),
            headers=dict(message.attributes)
        )
        message.ack()

    def consume(self) -> None:
        subscriber = _subscriber(self.consumers[0].actor.service.service_account_json)
        if subscriber is None:
            return
        topic_path = _get_topic_path(self.consumers[0].actor.service.project_id, self.consumers[0].topic)

        subscription_path = 'projects/{project_id}/subscriptions/{sub}'.format(
            project_id=os.environ.get('GOOGLE_CLOUD_PROJECT', self.consumers[0].actor.service.project_id),
            sub='%s_%s' % (PROGRAM, str(int(time.time())))
        )

        try:
            subscriber.create_subscription(name=subscription_path, topic=topic_path)
            self.future = subscriber.subscribe(subscription_path, self.callback)

            try:
                self.future.result()
            except KeyboardInterrupt:
                self.future.cancel()
        except (NotFound, _InactiveRpcError) as e:
            logging.info('Topic %s does not exist: %s', self.consumers[0].topic, e)

    def _stop(self):
        self.future.cancel()


class PubsubProducerPayload(AsyncProducerPayload):
    pass


class PubsubProducerPayloadList(AsyncProducerPayloadList):
    pass


class PubsubProducer(AsyncProducer):

    def _produce(self, key: str, value: str, headers: dict, payload: AsyncProducerPayload) -> None:
        publisher = _publisher(self.actor.service.service_account_json)
        if publisher is None:
            return
        topic_path = _get_topic_path(self.actor.service.project_id, self.topic)

        if payload.enable_topic_creation:
            try:
                publisher.create_topic(name=topic_path)
            except AlreadyExists:
                pass
            except NotFound:
                logging.error('`GOOGLE_CLOUD_PROJECT` environment variable or `projectId` field are not set!')
                return

        try:
            future = publisher.publish(topic_path, value.encode(), ordering_key=key, **headers)
            future.result()
        except (NotFound, _InactiveRpcError) as e:
            logging.info('Topic %s does not exist: %s', self.topic, e)
            raise


class PubsubActor(AsyncActor):
    pass


class PubsubService(AsyncService):

    def __init__(
        self,
        address: str,
        name: Union[str, None] = None,
        definition=None,
        _id: Union[int, None] = None,
        ssl: bool = False,
        project_id: Union[str, None] = None,
        service_account_json: Union[str, None] = None
    ):
        address = 'gcp:pubsub'
        super().__init__(
            address,
            name=name,
            definition=definition,
            _id=_id,
            ssl=ssl,
            project_id=project_id,
            service_account_json=service_account_json
        )
        self.type = 'pubsub'


def build_single_payload_producer(
    topic: str,
    value: str,
    key: Union[str, None] = None,
    headers: Union[dict, None] = None,
    tag: Union[str, None] = None,
    enable_topic_creation: bool = False
) -> PubsubProducer:
    payload_list = PubsubProducerPayloadList()
    payload = PubsubProducerPayload(
        value,
        key=key,
        headers={} if headers is None else headers,
        tag=tag
    )
    payload_list.add_payload(payload)
    return PubsubProducer(topic, payload_list)
