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

from mockintosh.helpers import _delay
from mockintosh.handlers import KafkaHandler
from mockintosh.replicas import Consumed


def _kafka_delivery_report(err, msg):
    if err is not None:  # pragma: no cover
        logging.info('Message delivery failed: {}'.format(err))
    else:
        logging.info('Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))


def _create_topic(address: str, queue: str):
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


def _decoder(value):
    try:
        return value.decode()
    except (AttributeError, UnicodeDecodeError):
        return value


def _headers_decode(headers: list):
    new_headers = {}
    for el in headers if headers else []:
        new_headers[el[0]] = _decoder(el[1])
    return new_headers


def _merge_global_headers(_globals, produce_data):
    headers = {}
    global_headers = _globals['headers'] if 'headers' in _globals else {}
    headers.update(global_headers)
    produce_data_headers = produce_data.get('headers', {})
    headers.update(produce_data_headers)
    return headers


def produce(
    address: str,
    queue: str,
    key: Union[str, None],
    value: str,
    headers: dict,
    config_dir: [str, None],
    template_engine: str,
    delay: int = 0,
    consumed: Consumed = None
) -> None:
    _delay(delay)

    _create_topic(address, queue)

    # Templating
    kafka_handler = KafkaHandler(config_dir, template_engine)
    if consumed is not None:
        kafka_handler.custom_context = {
            'consumed': consumed
        }
    key, value, headers = kafka_handler.render_attributes(key, value, headers)

    # Producing
    producer = Producer({'bootstrap.servers': address})
    producer.poll(0)
    producer.produce(queue, value, key=key, headers=headers, callback=_kafka_delivery_report)
    producer.flush()

    logging.info('Produced Kafka message: addr=\'%s\' topic=\'%s\' key=\'%s\' value=\'%s\' headers=\'%s\'' % (
        address,
        queue,
        key,
        value,
        headers
    ))


def consume(
    address: str,
    queue: str,
    produce_data: dict = None,
    definition=None,
    service_id: int = None,
    actor_id: int = None,
    log: Union[None, list] = None,
    delay: int = 0,
    stop: dict = {}
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
        if stop.get('val', False):  # pragma: no cover
            break

        msg = consumer.poll(1.0)

        if msg is None:
            continue

        if msg.error():  # pragma: no cover
            logging.warning("Consumer error: {}".format(msg.error()))
            continue

        key, value, headers = _decoder(msg.key()), _decoder(msg.value()), _headers_decode(msg.headers())

        logging.info('Consumed Kafka message: addr=\'%s\' topic=\'%s\' key=\'%s\' value=\'%s\' headers=\'%s\'' % (
            address,
            queue,
            key,
            value,
            headers
        ))

        if definition is not None:
            definition.data['kafka_services'][service_id]['actors'][actor_id]['log'].append(
                (key, value, headers)
            )

        if log is not None:  # pragma: no cover
            log.append(
                (key, value, headers)
            )

        if produce_data is not None:
            consumed = Consumed()
            consumed.key = key
            consumed.value = value
            consumed.headers = headers

            produce_headers = {}
            if definition is not None:
                produce_headers = _merge_global_headers(
                    definition.data['globals'] if 'globals' in definition.data else {},
                    produce_data
                )

            t = threading.Thread(target=produce, args=(
                address,
                produce_data.get('queue'),
                produce_data.get('key', None),
                produce_data.get('value'),
                produce_headers,
                definition.source_dir,
                definition.template_engine
            ), kwargs={
                'delay': delay,
                'consumed': consumed
            })
            t.daemon = True
            t.start()


def _run_produce_loop(definition, service_id: int, service: dict, actor_id: int, actor: dict):
    if 'limit' not in actor:
        logging.info('Running a Kafka loop indefinitely...')
        actor['limit'] = -1
    else:
        logging.info('Running a Kafka loop for %d iterations...' % actor['limit'])

    while actor['limit'] == -1 or actor['limit'] > 0:
        produce_data = actor['produce']

        produce_headers = _merge_global_headers(
            definition.data['globals'] if 'globals' in definition.data else {},
            produce_data
        )

        produce(
            service.get('address'),
            produce_data.get('queue'),
            produce_data.get('key', None),
            produce_data.get('value'),
            produce_headers,
            definition.source_dir,
            definition.template_engine
        )

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
                    service.get('address'),
                    consume_data.get('queue')
                ), kwargs={
                    'produce_data': produce_data,
                    'definition': definition,
                    'service_id': service_id,
                    'actor_id': actor_id,
                    'delay': int(actor['delay']) if 'delay' in actor else 0
                })
                t.daemon = True
                t.start()
