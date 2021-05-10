#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains a class that encompasses the properties of the configuration file and maps it.
"""

import copy
import logging
from collections import OrderedDict
from os import path, environ
from urllib.parse import parse_qs

import yaml
from jsonschema import validate

from mockintosh.constants import PROGRAM
from mockintosh.builders import ConfigRootBuilder
from mockintosh.helpers import _detect_engine, _urlsplit
from mockintosh.config import (
    ConfigHttpService,
    ConfigAsyncService,
    ConfigMultiProduce
)
from mockintosh.recognizers import (
    PathRecognizer,
    HeadersRecognizer,
    QueryStringRecognizer,
    BodyTextRecognizer,
    BodyUrlencodedRecognizer,
    BodyMultipartRecognizer,
    AsyncProducerValueRecognizer,
    AsyncProducerKeyRecognizer,
    AsyncProducerHeadersRecognizer
)
from mockintosh.kafka import (
    KafkaService,
    KafkaActor,
    KafkaConsumer,
    KafkaProducer,
    KafkaProducerPayloadList,
    KafkaProducerPayload
)
from mockintosh.exceptions import (
    UnrecognizedConfigFileFormat,
    AsyncProducerListQueueMismatch
)
from mockintosh.stats import Stats
from mockintosh.logs import Logs

stats = Stats()
logs = Logs()


class Definition:

    def __init__(self, source, schema, rendering_queue, is_file=True):
        self.source = source
        self.source_text = None if is_file else source
        data_dir_override = environ.get('%s_DATA_DIR' % PROGRAM.upper(), None)
        if data_dir_override is not None:
            self.source_dir = path.abspath(data_dir_override)
        else:
            self.source_dir = path.dirname(path.abspath(source)) if source is not None and is_file else None
        self.data = None
        self.schema = schema
        self.rendering_queue = rendering_queue
        self.load()
        self.orig_data = copy.deepcopy(self.data)
        self.validate()
        for service in self.data['services']:
            service['orig_data'] = copy.deepcopy(service)
        self.template_engine = _detect_engine(self.data, 'config')
        self.stats = stats
        self.logs = logs
        self.data = self.analyze(self.data)
        self.stoppers = []

    def load(self):
        if self.source_text is None:
            with open(self.source, 'r') as file:
                logging.info('Reading configuration file from path: %s', self.source)
                self.source_text = file.read()
                logging.debug('Configuration text: %s', self.source_text)

        try:
            self.data = yaml.safe_load(self.source_text)
            logging.info('Configuration file is a valid YAML file.')
        except (yaml.scanner.ScannerError, yaml.parser.ParserError) as e:
            raise UnrecognizedConfigFileFormat(
                'Configuration file is neither a JSON file nor a YAML file!',
                self.source,
                str(e)
            )

    def validate(self):
        validate(instance=self.data, schema=self.schema)
        logging.info('Configuration file is valid according to the JSON schema.')

    def analyze(self, data):
        config_root_builder = ConfigRootBuilder()
        config_root = config_root_builder.build(data)  # TODO: not fully implemented yet

        for service in ConfigAsyncService.services:
            service.address_template_renderer(
                self.template_engine,
                self.rendering_queue
            )

        for service in config_root.services:
            self.logs.add_service(service.get_name())
            self.stats.add_service(service.get_hint())

            if isinstance(service, ConfigAsyncService):
                self.analyze_async_service(service)
            elif isinstance(service, ConfigHttpService):
                if service.endpoints:
                    continue
                service = Definition.analyze_http_service(
                    service,
                    self.template_engine,
                    self.rendering_queue,
                    performance_profiles=data['performanceProfiles'],
                    global_performance_profile=config_root.globals.performance_profile
                )

        return data

    def add_stopper(self, stop: dict):
        self.stoppers.append(stop)

    def trigger_stoppers(self):
        while len(self.stoppers) > 0:
            stop = self.stoppers.pop()
            stop['val'] = True

    @staticmethod
    def analyze_http_service(
        service: ConfigHttpService,
        template_engine: str,
        rendering_queue,
        performance_profiles: dict = {},
        global_performance_profile=None
    ):
        service_perfomance_profile = service.get('performanceProfile', global_performance_profile)
        for endpoint in service['endpoints']:
            endpoint['internalOrigPath'] = endpoint['path']
            endpoint['params'] = {}
            endpoint['context'] = OrderedDict()
            endpoint['performanceProfile'] = performance_profiles.get(
                endpoint.get('performanceProfile', service_perfomance_profile),
                None
            )

            scheme, netloc, path, query, fragment = _urlsplit(endpoint['path'])
            if 'queryString' not in endpoint:
                endpoint['queryString'] = {}
            parsed_query = parse_qs(query, keep_blank_values=True)
            endpoint['queryString'].update({k: parsed_query[k] for k, v in parsed_query.items()})

            path_recognizer = PathRecognizer(
                path,
                endpoint['params'],
                endpoint['context'],
                template_engine,
                rendering_queue
            )
            endpoint['path'], endpoint['priority'] = path_recognizer.recognize()

            if 'headers' in endpoint and endpoint['headers']:
                headers_recognizer = HeadersRecognizer(
                    endpoint['headers'],
                    endpoint['params'],
                    endpoint['context'],
                    template_engine,
                    rendering_queue
                )
                endpoint['headers'] = headers_recognizer.recognize()

            if 'queryString' in endpoint and endpoint['queryString']:
                query_string_recognizer = QueryStringRecognizer(
                    endpoint['queryString'],
                    endpoint['params'],
                    endpoint['context'],
                    template_engine,
                    rendering_queue
                )
                endpoint['queryString'] = query_string_recognizer.recognize()

            if 'body' in endpoint:
                if 'text' in endpoint['body'] and endpoint['body']['text']:
                    body_text_recognizer = BodyTextRecognizer(
                        endpoint['body']['text'],
                        endpoint['params'],
                        endpoint['context'],
                        template_engine,
                        rendering_queue
                    )
                    endpoint['body']['text'] = body_text_recognizer.recognize()

                if 'urlencoded' in endpoint['body'] and endpoint['body']['urlencoded']:
                    body_urlencoded_recognizer = BodyUrlencodedRecognizer(
                        endpoint['body']['urlencoded'],
                        endpoint['params'],
                        endpoint['context'],
                        template_engine,
                        rendering_queue
                    )
                    endpoint['body']['urlencoded'] = body_urlencoded_recognizer.recognize()

                if 'multipart' in endpoint['body'] and endpoint['body']['multipart']:
                    body_multipart_recognizer = BodyMultipartRecognizer(
                        endpoint['body']['multipart'],
                        endpoint['params'],
                        endpoint['context'],
                        template_engine,
                        rendering_queue
                    )
                    endpoint['body']['multipart'] = body_multipart_recognizer.recognize()

        return service

    def analyze_async_service(
        self,
        service: ConfigAsyncService
    ):
        kafka_service = KafkaService(
            service.address,
            name=service.name,
            definition=self,
            _id=service.internal_service_id,
            ssl=service.ssl
        )

        for i, actor in enumerate(service.actors):
            kafka_actor = KafkaActor(i, actor.name)
            kafka_service.add_actor(kafka_actor)

            if actor.consume is not None:
                capture_limit = actor.consume.capture

                value = actor.consume.value
                key = actor.consume.key
                headers = actor.consume.headers

                params = kafka_actor.params
                context = kafka_actor.context

                async_producer_value_recognizer = AsyncProducerValueRecognizer(
                    value,
                    params,
                    context,
                    self.template_engine,
                    self.rendering_queue
                )
                value = async_producer_value_recognizer.recognize()

                async_producer_key_recognizer = AsyncProducerKeyRecognizer(
                    key,
                    params,
                    context,
                    self.template_engine,
                    self.rendering_queue
                )
                key = async_producer_key_recognizer.recognize()

                async_producer_headers_recognizer = AsyncProducerHeadersRecognizer(
                    headers,
                    params,
                    context,
                    self.template_engine,
                    self.rendering_queue
                )
                headers = async_producer_headers_recognizer.recognize()

                kafka_consumer = KafkaConsumer(
                    actor.consume.queue,
                    schema=actor.consume.schema,
                    value=value,
                    key=key,
                    headers=headers,
                    capture_limit=capture_limit
                )
                kafka_actor.set_consumer(kafka_consumer)
                kafka_actor.set_delay(actor.delay)

            if actor.produce is not None:
                queue = None
                payload_list = KafkaProducerPayloadList()

                produce_list = []
                if isinstance(actor.produce, ConfigMultiProduce):
                    queue = actor.produce.produce_list[0].queue
                    for _produce in actor.produce.produce_list:
                        if queue != _produce.queue:
                            raise AsyncProducerListQueueMismatch(kafka_actor.get_hint())
                    produce_list += actor.produce.produce_list[0]
                else:
                    queue = actor.produce.queue
                    produce_list += [actor.produce]

                for produce in produce_list:
                    payload = KafkaProducerPayload(
                        produce.value,
                        key=produce.key,
                        headers=produce.headers,
                        tag=produce.tag,
                        enable_topic_creation=produce.enable_topic_creation
                    )
                    payload_list.add_payload(payload)

                kafka_producer = KafkaProducer(queue, payload_list)
                kafka_actor.set_producer(kafka_producer)

            kafka_actor.set_limit(actor.limit)

            kafka_actor.set_dataset(actor.dataset)

            kafka_actor.multi_payloads_looped = actor.multi_payloads_looped
            kafka_actor.dataset_looped = actor.dataset_looped
