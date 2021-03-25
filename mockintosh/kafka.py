#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains Kafka related methods.
"""

import logging
import threading

from confluent_kafka import Producer, Consumer
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka.cimpl import KafkaException

from mockintosh.methods import _delay


def _kafka_delivery_report(err, msg):
    if err is not None:
        logging.info('Message delivery failed: {}'.format(err))
    else:
        logging.info('Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))


def produce(address: str, queue: str, key: str, value: str) -> None:
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

    # Producing
    producer = Producer({'bootstrap.servers': address})
    producer.poll(0)
    producer.produce(queue, value, key=key, callback=_kafka_delivery_report)
    producer.flush()

    logging.info('Produced Kafka message: \'%s\' \'%s\' \'%s\' \'%s\'' % (address, queue, key, value))


def consume(address: str, queue: str, key: str, value: str) -> bool:
    log = []
    consumer = Consumer({
        'bootstrap.servers': address,
        'group.id': '0',
        'auto.offset.reset': 'earliest'
    })
    consumer.subscribe([queue])

    while True:
        msg = consumer.poll(1.0)

        if msg is None:
            break

        if msg.error():
            logging.warning("Consumer error: {}".format(msg.error()))
            continue

        log.append((msg.key().decode(), msg.value().decode()))

    consumer.close()

    logging.info('Consumed Kafka message: \'%s\' \'%s\' \'%s\' \'%s\'' % (address, queue, key, value))

    return any(msg[0] == key and msg[1] == value for msg in log)


def _run_loop(definition, service_id, service, actor_id, actor):
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
                t = threading.Thread(target=_run_loop, args=(definition, service_id, service, actor_id, actor))
                t.daemon = True
                t.start()
