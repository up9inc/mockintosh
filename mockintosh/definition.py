#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains a class that encompasses the properties of the configuration file and maps it.
"""

import logging
from collections import OrderedDict
from os import path, environ
from urllib.parse import parse_qs
from typing import (
    List,
    Union,
    Tuple
)

import yaml
from jsonschema import validate

from mockintosh.constants import PROGRAM
from mockintosh.builders import ConfigRootBuilder
from mockintosh.helpers import _detect_engine, _urlsplit
from mockintosh.config import (
    ConfigRoot,
    ConfigHttpService,
    ConfigAsyncService,
    ConfigMultiProduce,
    ConfigGlobals
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
from mockintosh.http import (
    HttpService,
    HttpEndpoint,
    HttpBody
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
from mockintosh.templating import RenderingQueue
from mockintosh.stats import Stats
from mockintosh.logs import Logs

stats = Stats()
logs = Logs()


class Definition:

    def __init__(
        self,
        source: str,
        schema: dict,
        rendering_queue: RenderingQueue,
        is_file: bool = True
    ):
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
        self.validate()
        self.template_engine = _detect_engine(self.data, 'config')
        self.stats = stats
        self.logs = logs
        self.services, self.config_root = self.analyze(self.data)
        self.globals = self.config_root.globals
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

    def analyze(self, data: dict) -> Tuple[List[Union[HttpService, KafkaService]], ConfigRoot]:
        config_root_builder = ConfigRootBuilder()
        config_root = config_root_builder.build(data)

        for service in ConfigAsyncService.services:
            service.address_template_renderer(
                self.template_engine,
                self.rendering_queue
            )

        new_services = []
        for service in config_root.services:
            self.logs.add_service(service.get_name())
            self.stats.add_service(service.get_hint())

            if isinstance(service, ConfigAsyncService):
                new_services.append(self.analyze_async_service(service))
            elif isinstance(service, ConfigHttpService):
                new_services.append(
                    self.analyze_http_service(
                        service,
                        self.template_engine,
                        self.rendering_queue,
                        performance_profiles=config_root.performance_profiles,
                        global_performance_profile=None if config_root.globals is None else config_root.globals.performance_profile
                    )
                )

        return new_services, config_root

    def add_stopper(self, stop: dict):
        self.stoppers.append(stop)

    def trigger_stoppers(self):
        while len(self.stoppers) > 0:
            stop = self.stoppers.pop()
            stop['val'] = True

    def analyze_http_service(
        self,
        service: ConfigHttpService,
        template_engine: str,
        rendering_queue: RenderingQueue,
        performance_profiles: dict = {},
        global_performance_profile: Union[ConfigGlobals, None] = None,
        internal_http_service_id: Union[int, None] = None
    ):
        http_service = HttpService(
            service.port,
            service.name,
            service.hostname,
            service.ssl,
            service.ssl_cert_file,
            service.ssl_key_file,
            service.management_root,
            service.oas,
            service.performance_profile,
            service.fallback_to,
            service.internal_service_id,
            internal_http_service_id=internal_http_service_id
        )

        service_perfomance_profile = service.performance_profile if service.performance_profile is not None else global_performance_profile
        for endpoint in service.endpoints:
            orig_path = endpoint.path
            params = {}
            context = OrderedDict()
            performance_profile = performance_profiles.get(
                endpoint.performance_profile if endpoint.performance_profile is not None else service_perfomance_profile,
                None
            )
            if performance_profile is not None:
                performance_profile = performance_profile.actuator

            scheme, netloc, path, query, fragment = _urlsplit(endpoint.path)
            query_string = {}
            parsed_query = parse_qs(query, keep_blank_values=True)
            query_string.update(endpoint.query_string)
            query_string.update({k: parsed_query[k] for k, v in parsed_query.items()})

            path_recognizer = PathRecognizer(
                path,
                params,
                context,
                template_engine,
                rendering_queue
            )
            path, priority = path_recognizer.recognize()

            headers_recognizer = HeadersRecognizer(
                endpoint.headers,
                params,
                context,
                template_engine,
                rendering_queue
            )
            headers = headers_recognizer.recognize()

            query_string_recognizer = QueryStringRecognizer(
                query_string,
                params,
                context,
                template_engine,
                rendering_queue
            )
            query_string = query_string_recognizer.recognize()

            http_body = None
            if endpoint.body is not None:
                body_text_recognizer = BodyTextRecognizer(
                    endpoint.body.text,
                    params,
                    context,
                    template_engine,
                    rendering_queue
                )
                text = body_text_recognizer.recognize()

                body_urlencoded_recognizer = BodyUrlencodedRecognizer(
                    endpoint.body.urlencoded,
                    params,
                    context,
                    template_engine,
                    rendering_queue
                )
                urlencoded = body_urlencoded_recognizer.recognize()

                body_multipart_recognizer = BodyMultipartRecognizer(
                    endpoint.body.multipart,
                    params,
                    context,
                    template_engine,
                    rendering_queue
                )
                multipart = body_multipart_recognizer.recognize()

                http_body = HttpBody(
                    endpoint.body.schema,
                    text,
                    urlencoded,
                    multipart
                )

            http_service.add_endpoint(
                HttpEndpoint(
                    endpoint.id,
                    orig_path,
                    params,
                    context,
                    performance_profile,
                    priority,
                    path,
                    endpoint.comment,
                    endpoint.method,
                    query_string,
                    headers,
                    http_body,
                    endpoint.dataset,
                    endpoint.response,
                    endpoint.multi_responses_looped,
                    endpoint.dataset_looped
                )
            )

        return http_service

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
                    {} if headers is None else headers.payload,
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
                    produce_list += actor.produce.produce_list
                else:
                    queue = actor.produce.queue
                    produce_list += [actor.produce]

                for produce in produce_list:
                    payload = KafkaProducerPayload(
                        produce.value,
                        key=produce.key,
                        headers={} if produce.headers is None else produce.headers.payload,
                        tag=produce.tag,
                        enable_topic_creation=produce.create
                    )
                    payload_list.add_payload(payload)

                kafka_producer = KafkaProducer(queue, payload_list)
                kafka_actor.set_producer(kafka_producer)

            kafka_actor.set_limit(actor.limit)

            kafka_actor.set_dataset(actor.dataset)

            kafka_actor.multi_payloads_looped = actor.multi_payloads_looped
            kafka_actor.dataset_looped = actor.dataset_looped

        return kafka_service
