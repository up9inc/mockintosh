#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains asynchronous looping related methods.
"""

import sys
import threading

from mockintosh.services.asynchronous import AsyncService, AsyncConsumerGroup, AsyncActor, AsyncProducer, AsyncConsumer
from mockintosh.services.asynchronous.kafka import KafkaConsumerGroup  # noqa: F401
from mockintosh.services.asynchronous.amqp import AmqpConsumerGroup  # noqa: F401
from mockintosh.services.asynchronous.redis import RedisConsumerGroup  # noqa: F401

try:
    from mockintosh.services.asynchronous.gpubsub import GpubsubConsumerGroup  # noqa: F401
except ModuleNotFoundError:
    pass

try:
    from mockintosh.services.asynchronous.amazonsqs import AmazonsqsConsumerGroup  # noqa: F401
except ModuleNotFoundError:
    pass

from mockintosh.services.asynchronous.mqtt import MqttConsumerGroup  # noqa: F401


def run_loops():
    for service in AsyncService.services:
        class_name_prefix = service.type.capitalize()
        consumer_groups = {}

        for actor in service.actors:
            t = threading.Thread(target=actor.run_produce_loop, args=(), kwargs={})
            t.daemon = True
            t.start()

            if actor.consumer is not None:
                if actor.consumer.topic not in consumer_groups.keys():
                    consumer_group = getattr(sys.modules[__name__], '%sConsumerGroup' % class_name_prefix)()
                    consumer_group.add_consumer(actor.consumer)
                    consumer_groups[actor.consumer.topic] = consumer_group
                else:
                    consumer_groups[actor.consumer.topic].add_consumer(actor.consumer)

        for consumer_group in AsyncConsumerGroup.groups:
            t = threading.Thread(target=consumer_group.consume, args=(), kwargs={})
            t.daemon = True
            t.start()


def stop_loops():
    for actor in AsyncActor.actors:
        actor.stop = True

    for consumer_group in AsyncConsumerGroup.groups:
        consumer_group.stop = True

    AsyncService.services = []
    AsyncActor.actors = []
    AsyncProducer.producers = []
    AsyncConsumer.consumers = []
    AsyncConsumerGroup.groups = []
