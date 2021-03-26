#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains Kafka related methods.
"""

import logging
import threading
from typing import (
    Union
)

from confluent_kafka import Producer, Consumer
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka.cimpl import KafkaException

from mockintosh.methods import _delay


def _kafka_delivery_report(err, msg):
    if err is not None:
        logging.info('Message delivery failed: {}'.format(err))
    else:
        logging.info('Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))


def _create_topic(address, queue):
    # Topic creation
    admin_client = AdminClient({'bootstrap.servers': address})
    new_topics = [NewTopic(topic, num_partitions=1, replication_factor=1) for topic in [queue]]
    futures = admin_client.create_topics(new_topics)

    for topic, future in futures.items():
        try:
            future.result()
            logging.info('Topic {} created'.format(topic))
        except KafkaException as e:
            logging.info('Failed to create topic {}: {}'.format(topic, e))


def produce(address: str, queue: str, key: Union[str, None], value: str) -> None:
    _create_topic(address, queue)

    # Producing
    producer = Producer({'bootstrap.servers': address})
    producer.poll(0)
    producer.produce(queue, value, key=key, callback=_kafka_delivery_report)
    producer.flush()

    logging.info('Produced Kafka message: addr=\'%s\' topic=\'%s\' key=\'%s\' value=\'%s\'' % (address, queue, key, value))


def consume(
    address: str,
    queue: str,
    key: Union[str, None],
    value: str,
    produce_data=None,
    definition=None,
    service_id=None,
    actor_id=None,
    log=None,
    stop={}
) -> None:
    _create_topic(address, queue)

    if definition is not None:
        definition.data['kafka_services'][service_id]['actors'][actor_id]['log'] = []

    consumer = Consumer({
        'bootstrap.servers': address,
        'group.id': '0',
        'auto.offset.reset': 'earliest'
    })
    consumer.subscribe([queue])

    while True:
        if stop.get('val', False):
            break

        msg = consumer.poll(1.0)

        if msg is None:
            continue

        if msg.error():
            logging.warning("Consumer error: {}".format(msg.error()))
            continue

        logging.info('Consumed Kafka message: addr=\'%s\' topic=\'%s\' key=\'%s\' value=\'%s\'' % (address, queue, key, value))

        if definition is not None:
            definition.data['kafka_services'][service_id]['actors'][actor_id]['log'].append(
                (msg.key().decode(), msg.value().decode())
            )

        if log is not None:
            log.append(
                (msg.key().decode(), msg.value().decode())
            )

        if produce_data is not None:
            produce(address, produce_data['queue'], produce_data['key'], produce_data['value'])

    consumer.close()


def _run_produce_loop(definition, service_id, service, actor_id, actor):
    if 'limit' not in actor:
        logging.info('Running a Kafka loop indefinitely...')
        actor['limit'] == -1
    else:
        logging.info('Running a Kafka loop for %d iterations...' % actor['limit'])

    while actor['limit'] == -1 or actor['limit'] > 0:
        produce_data = actor['produce']
        produce(service['address'], produce_data['queue'], produce_data['key'], produce_data['value'])

        _delay(int(actor['delay']))

        if actor['limit'] > 1:
            actor['limit'] -= 1
            definition.data['kafka_services'][service_id]['actors'][actor_id]['limit'] -= 1

    logging.info('Kafka loop is finished.')


def run_loops(definition):
    for service_id, service in enumerate(definition.data['kafka_services']):
        for actor_id, actor in enumerate(service['actors']):
            if 'consume' not in actor and 'produce' in actor and 'delay' in actor:
                t = threading.Thread(target=_run_produce_loop, args=(definition, service_id, service, actor_id, actor))
                t.daemon = True
                t.start()

            if 'consume' in actor:
                consume_data = actor['consume']
                produce_data = None if 'produce' not in actor else actor['produce']
                t = threading.Thread(target=consume, args=(
                    service['address'],
                    consume_data['queue'],
                    consume_data['key'],
                    consume_data['value']
                ), kwargs={
                    'produce_data': produce_data,
                    'definition': definition,
                    'service_id': service_id,
                    'actor_id': actor_id
                })
                t.daemon = True
                t.start()
