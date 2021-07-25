#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains a class that encompasses the properties of the configuration file and maps it.
"""

import os
import sys
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
import graphql
from graphql import parse as graphql_parse
from graphql.language.printer import print_ast as graphql_print_ast

from mockintosh.constants import PROGRAM, WARN_GPUBSUB_PACKAGE, WARN_AMAZONSQS_PACKAGE
from mockintosh.builders import ConfigRootBuilder
from mockintosh.helpers import _detect_engine, _urlsplit, _graphql_escape_templating, _graphql_undo_escapes
from mockintosh.config import (
    ConfigRoot,
    ConfigHttpService,
    ConfigAsyncService,
    ConfigMultiProduce,
    ConfigGlobals,
    ConfigExternalFilePath
)
from mockintosh.recognizers import (
    PathRecognizer,
    HeadersRecognizer,
    QueryStringRecognizer,
    BodyTextRecognizer,
    BodyUrlencodedRecognizer,
    BodyMultipartRecognizer,
    BodyGraphQLVariablesRecognizer,
    AsyncProducerValueRecognizer,
    AsyncProducerKeyRecognizer,
    AsyncProducerHeadersRecognizer,
    AsyncProducerAmqpPropertiesRecognizer
)
from mockintosh.services.http import (
    HttpService,
    HttpEndpoint,
    HttpBody
)
from mockintosh.services.asynchronous.kafka import (  # noqa: F401
    KafkaService,
    KafkaActor,
    KafkaConsumer,
    KafkaProducer,
    KafkaProducerPayloadList,
    KafkaProducerPayload
)
from mockintosh.services.asynchronous.amqp import (  # noqa: F401
    AmqpService,
    AmqpActor,
    AmqpConsumer,
    AmqpProducer,
    AmqpProducerPayloadList,
    AmqpProducerPayload
)
from mockintosh.services.asynchronous.redis import (  # noqa: F401
    RedisService,
    RedisActor,
    RedisConsumer,
    RedisProducer,
    RedisProducerPayloadList,
    RedisProducerPayload
)

try:
    from mockintosh.services.asynchronous.gpubsub import (  # noqa: F401
        GpubsubService,
        GpubsubActor,
        GpubsubConsumer,
        GpubsubProducer,
        GpubsubProducerPayloadList,
        GpubsubProducerPayload
    )
except ModuleNotFoundError:
    pass

try:
    from mockintosh.services.asynchronous.amazonsqs import (  # noqa: F401
        AmazonsqsService,
        AmazonsqsActor,
        AmazonsqsConsumer,
        AmazonsqsProducer,
        AmazonsqsProducerPayloadList,
        AmazonsqsProducerPayload
    )
except ModuleNotFoundError:
    pass

from mockintosh.services.asynchronous.mqtt import (  # noqa: F401
    MqttService,
    MqttActor,
    MqttConsumer,
    MqttProducer,
    MqttProducerPayloadList,
    MqttProducerPayload
)

from mockintosh.exceptions import (
    UnrecognizedConfigFileFormat,
    AsyncProducerListQueueMismatch
)
from mockintosh.templating import RenderingQueue
from mockintosh.stats import Stats
from mockintosh.logs import Logs

graphql.language.printer.MAX_LINE_LENGTH = -1

stats = Stats()
logs = Logs()


class Definition:

    def __init__(
        self,
        source: str,
        schema: dict,
        rendering_queue: RenderingQueue,
        is_file: bool = True,
        load_override: Union[dict, None] = None
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
        if load_override is not None:
            self.data = load_override
        else:
            self.load()
            self.validate()
        self.template_engine = _detect_engine(self.data, 'config')
        self.stats = stats
        self.logs = logs
        self.services, self.config_root = self.analyze(self.data)
        self.globals = self.config_root.globals

    def load(self) -> None:
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

    def analyze(self, data: dict) -> Tuple[
        List[
            Union[
                HttpService,
                KafkaService,
                AmqpService,
                RedisService,
                MqttService
            ]
        ],
        ConfigRoot
    ]:
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

    def analyze_http_service(
        self,
        service: ConfigHttpService,
        template_engine: str,
        rendering_queue: RenderingQueue,
        performance_profiles: Union[dict, None] = None,
        global_performance_profile: Union[ConfigGlobals, None] = None,
        internal_http_service_id: Union[int, None] = None
    ):
        performance_profiles = {} if performance_profiles is None else performance_profiles
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
        service._impl = http_service

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
                graphql_query = None if endpoint.body.graphql_query is None else endpoint.body.graphql_query

                if isinstance(graphql_query, ConfigExternalFilePath):
                    external_path = self.resolve_relative_path('GraphQL', graphql_query.path)
                    with open(external_path, 'r') as file:
                        logging.debug('Reading external file from path: %s', external_path)
                        graphql_query = file.read()

                if graphql_query is not None:
                    graphql_query = _graphql_escape_templating(graphql_query)
                    logging.debug('Before GraphQL parse/unparse:\n%s', graphql_query)
                    graphql_ast = graphql_parse(graphql_query)
                    graphql_query = graphql_print_ast(graphql_ast).strip()
                    logging.debug('After GraphQL parse/unparse:\n%s', graphql_query)
                    graphql_query = _graphql_undo_escapes(graphql_query)
                    logging.debug('Rendered GraphQL:\n%s', graphql_query)

                body_text_recognizer = BodyTextRecognizer(
                    graphql_query if graphql_query is not None else endpoint.body.text,
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

                body_graphql_variables_recognizer = BodyGraphQLVariablesRecognizer(
                    endpoint.body.graphql_variables,
                    params,
                    context,
                    template_engine,
                    rendering_queue
                )
                graphql_variables = body_graphql_variables_recognizer.recognize()

                http_body = HttpBody(
                    endpoint.body.schema,
                    text,
                    urlencoded,
                    multipart,
                    graphql_variables,
                    is_grapql_query=True if graphql_query is not None else False
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
        if service.type == 'gpubsub':
            try:
                import mockintosh.services.asynchronous.gpubsub  # noqa: F401
            except ModuleNotFoundError:
                logging.error(WARN_GPUBSUB_PACKAGE)
                raise
        elif service.type == 'amazonsqs':
            try:
                import mockintosh.services.asynchronous.amazonsqs  # noqa: F401
            except ModuleNotFoundError:
                logging.error(WARN_AMAZONSQS_PACKAGE)
                raise

        class_name_prefix = service.type.capitalize()
        async_service = getattr(sys.modules[__name__], '%sService' % class_name_prefix)(
            service.address,
            name=service.name,
            definition=self,
            _id=service.internal_service_id,
            ssl=service.ssl
        )
        service._impl = async_service

        for i, actor in enumerate(service.actors):
            async_actor = getattr(sys.modules[__name__], '%sActor' % class_name_prefix)(i, actor.name)
            async_service.add_actor(async_actor)

            if actor.consume is not None:
                capture_limit = actor.consume.capture

                value = actor.consume.value
                key = actor.consume.key
                headers = actor.consume.headers
                amqp_properties = actor.consume.amqp_properties

                params = async_actor.params
                context = async_actor.context

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

                async_producer_amqp_properties_recognizer = AsyncProducerAmqpPropertiesRecognizer(
                    {} if amqp_properties is None else amqp_properties.__dict__,
                    params,
                    context,
                    self.template_engine,
                    self.rendering_queue
                )
                amqp_properties = async_producer_amqp_properties_recognizer.recognize()

                async_consumer = getattr(sys.modules[__name__], '%sConsumer' % class_name_prefix)(
                    actor.consume.queue,
                    schema=actor.consume.schema,
                    value=value,
                    key=key,
                    headers=headers,
                    amqp_properties=amqp_properties,
                    capture_limit=capture_limit
                )
                async_actor.set_consumer(async_consumer)

            async_actor.set_delay(actor.delay)

            if actor.produce is not None:
                queue = None
                payload_list = getattr(sys.modules[__name__], '%sProducerPayloadList' % class_name_prefix)()

                produce_list = []
                if isinstance(actor.produce, ConfigMultiProduce):
                    queue = actor.produce.produce_list[0].queue
                    for _produce in actor.produce.produce_list:
                        if queue != _produce.queue:
                            raise AsyncProducerListQueueMismatch(async_actor.get_hint())
                    produce_list += actor.produce.produce_list
                else:
                    queue = actor.produce.queue
                    produce_list += [actor.produce]

                for produce in produce_list:
                    payload = getattr(sys.modules[__name__], '%sProducerPayload' % class_name_prefix)(
                        produce.value,
                        key=produce.key,
                        headers={} if produce.headers is None else produce.headers.payload,
                        amqp_properties={} if produce.amqp_properties is None else produce.amqp_properties.__dict__,
                        tag=produce.tag,
                        enable_topic_creation=produce.create
                    )
                    payload_list.add_payload(payload)

                async_producer = getattr(sys.modules[__name__], '%sProducer' % class_name_prefix)(queue, payload_list)
                async_actor.set_producer(async_producer)

            async_actor.set_limit(actor.limit)

            async_actor.set_dataset(actor.dataset)

            async_actor.multi_payloads_looped = actor.multi_payloads_looped
            async_actor.dataset_looped = actor.dataset_looped

        return async_service

    def resolve_relative_path(self, document_type, source_text):
        relative_path = None
        orig_relative_path = source_text[1:]

        error_msg = 'External %s document %r couldn\'t be accessed or found!' % (document_type, orig_relative_path)
        if orig_relative_path[0] == '/':
            orig_relative_path = orig_relative_path[1:]
        relative_path = os.path.join(self.source_dir, orig_relative_path)
        if not os.path.isfile(relative_path):
            raise Exception(error_msg)
        relative_path = os.path.abspath(relative_path)
        if not relative_path.startswith(self.source_dir):
            raise Exception(error_msg)

        return relative_path
