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
from mockintosh.hbs.methods import Random as hbs_Random, Date as hbs_Date
from mockintosh.j2.methods import Random as j2_Random, Date as j2_Date
from mockintosh.handlers import BaseHandler

hbs_random = hbs_Random()
j2_random = j2_Random()

hbs_date = hbs_Date()
j2_date = j2_Date()

counters = {}


def _kafka_delivery_report(err, msg):
    if err is not None:  # pragma: no cover
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


def _headers_decode(headers: list):
    new_headers = {}
    for el in headers if headers else []:
        new_headers[el[0]] = el[1].decode()
    return new_headers


class KafkaHandler(BaseHandler):
    """Class to handle mocked Kafka data."""

    def __init__(self, config_dir: [str, None], template_engine: str):
        super().__init__()
        self.config_dir = config_dir
        self.definition_engine = template_engine
        self.custom_context = {}

        self.analyze_counters()

    def _render_value(self, value):
        if len(value) > 1 and value[0] == '@':
            template_path, context = self.resolve_relative_path(value)
            with open(template_path, 'r') as file:
                logging.debug('Reading external file from path: %s', template_path)
                value = file.read()
        compiled, context = self.common_template_renderer(self.definition_engine, value)
        self.populate_counters(context)
        return compiled

    def render_attributes(self, *args):
        rendered = []
        for arg in args:
            if arg is None:
                rendered.append(arg)

            if isinstance(arg, dict):
                new_arg = {}
                for key, value in arg.items():
                    new_arg[key] = self._render_value(value)
                rendered.append(new_arg)
            elif isinstance(arg, str):
                if len(arg) > 1 and arg[0] == '@':
                    template_path, context = self.resolve_relative_path(arg)
                    self.populate_counters(context)
                    with open(template_path, 'r') as file:
                        logging.debug('Reading external file from path: %s', template_path)
                        arg = file.read()
                rendered.append(self._render_value(arg))

        return rendered

    def add_params(self, context):
        return context


def produce(
    address: str,
    queue: str,
    key: Union[str, None],
    value: str,
    headers: dict,
    config_dir: [str, None],
    template_engine: str
) -> None:
    _create_topic(address, queue)

    kafka_handler = KafkaHandler(config_dir, template_engine)
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
        if stop.get('val', False):  # pragma: no cover
            break

        msg = consumer.poll(1.0)

        if msg is None:
            continue

        if msg.error():  # pragma: no cover
            logging.warning("Consumer error: {}".format(msg.error()))
            continue

        key, value, headers = msg.key().decode(), msg.value().decode(), _headers_decode(msg.headers())

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

        if produce_data is not None:  # pragma: no cover
            produce(
                address,
                produce_data.get('queue'),
                produce_data.get('key', None),
                produce_data.get('value'),
                produce_data.get('headers', {}),
                definition.source_dir,
                definition.template_engine
            )


def _run_produce_loop(definition, service_id, service, actor_id, actor):
    if 'limit' not in actor:
        logging.info('Running a Kafka loop indefinitely...')
        actor['limit'] = -1
    else:
        logging.info('Running a Kafka loop for %d iterations...' % actor['limit'])

    while actor['limit'] == -1 or actor['limit'] > 0:
        produce_data = actor['produce']
        produce(
            service.get('address'),
            produce_data.get('queue'),
            produce_data.get('key', None),
            produce_data.get('value'),
            produce_data.get('headers', {}),
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
                    'actor_id': actor_id
                })
                t.daemon = True
                t.start()
