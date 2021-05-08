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
from typing import (
    Union,
    List,
    Tuple
)

import yaml
from jsonschema import validate

from mockintosh.constants import PROGRAM, PYBARS, JINJA
from mockintosh.config import (
    # ConfigActor,
    # ConfigAsyncService,
    ConfigBody,
    # ConfigConsume,
    ConfigDataset,
    ConfigEndpoint,
    ConfigExternalFilePath,
    ConfigGlobals,
    ConfigHeaders,
    ConfigHttpService,
    ConfigManagement,
    ConfigMultiResponse,
    ConfigPerformanceProfile,
    # ConfigProduce,
    ConfigResponse,
    ConfigRoot,
    ConfigSchema
)
from mockintosh.helpers import _detect_engine, _urlsplit
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
    CommaInTagIsForbidden,
    AsyncProducerListQueueMismatch
)
from mockintosh.templating import TemplateRenderer
from mockintosh.performance import PerformanceProfile
from mockintosh.stats import Stats
from mockintosh.logs import Logs

stats = Stats()
logs = Logs()


class ConfigRootBuilder:

    def build_config_external_file_path(self, data: Union[str, list, dict, None]) -> Union[ConfigExternalFilePath, str, list, dict, None]:
        if isinstance(data, str) and len(data) > 1 and data[0] == '@':
            return ConfigExternalFilePath(data)
        else:
            return data

    def build_config_dataset(self, data: Union[dict, str, None]) -> Union[ConfigDataset, None]:
        if data is None:
            return None

        payload = None
        if isinstance(data, dict):
            payload = data
        elif isinstance(data, str):
            payload = self.build_config_external_file_path(data)

        return ConfigDataset(payload)

    def build_config_schema(self, data: Union[dict, str, None]) -> Union[ConfigSchema, None]:
        if data is None:
            return data

        schema = None
        if isinstance(data, dict):
            schema = data
        elif isinstance(data, str):
            schema = self.build_config_external_file_path(data)

        return ConfigSchema(schema)

    def build_config_headers(self, data: dict) -> Union[ConfigHeaders, None]:
        config_headers = None
        if 'headers' in data:
            payload = {}
            data_headers = data['headers']
            for key, value in data_headers.items():
                payload[key] = self.build_config_external_file_path(value)
            config_headers = ConfigHeaders(payload)
        return config_headers

    def build_config_response(self, data: dict) -> ConfigResponse:
        return ConfigResponse(
            headers=self.build_config_headers(data),
            status=data.get('status', None),
            body=self.build_config_external_file_path(data.get('body', None)),
            use_templating=data.get('useTemplating', True),
            templating_engine=data.get('templatingEngine', PYBARS),
            tag=data.get('tag', None)
        )

    def build_config_multi_response(self, data: List[Union[dict, str]]) -> ConfigMultiResponse:
        responses = []
        for response in data:
            if isinstance(response, dict):
                responses.append(self.build_config_response(response))
            elif isinstance(response, str):
                responses.append(self.build_config_external_file_path(response))

        return ConfigMultiResponse(responses)

    def build_config_body(self, data: Union[dict, None]) -> Union[ConfigBody, None]:
        if data is None:
            return data

        return ConfigBody(
            schema=self.build_config_schema(data.get('schema', None)),
            text=data.get('text', None),
            urlencoded=data.get('urlencoded', None),
            multipart=data.get('multipart', None),
        )

    def build_config_endpoint(self, endpoint: dict) -> ConfigEndpoint:
        response = None
        if 'response' in endpoint:
            response = endpoint['response']
            if isinstance(response, dict):
                response = self.build_config_response(response)
            elif isinstance(response, str):
                response = self.build_config_external_file_path(response)
            elif isinstance(response, list):
                response = self.build_config_multi_response(response)

        return ConfigEndpoint(
            endpoint['path'],
            _id=endpoint.get('id', None),
            comment=endpoint.get('comment', None),
            method=endpoint.get('method', None),
            query_string=endpoint.get('query_string', None),
            headers=endpoint.get('headers', None),
            body=self.build_config_body(endpoint.get('body', None)),
            dataset=self.build_config_dataset(endpoint.get('dataset', None)),
            response=response,
            multi_responses_looped=endpoint.get('multiResponsesLooped', True),
            dataset_looped=endpoint.get('datasetLooped', True),
            performance_profile=endpoint.get('performanceProfile', None)
        )

    def build_config_http_service(self, service: dict) -> ConfigHttpService:
        return ConfigHttpService(
            service['port'],
            name=service.get('name', None),
            hostname=service.get('hostname', None),
            ssl=service.get('ssl', False),
            ssl_cert_file=service.get('sslCertFile', None),
            ssl_key_file=service.get('sslKeyFile', None),
            management_root=service.get('managementRoot', None),
            oas=self.build_config_external_file_path(service.get('oas', None)),
            endpoints=[self.build_config_endpoint(endpoint) for endpoint in service.get('endpoints', [])],
            performance_profile=service.get('performanceProfile', None),
            fallback_to=service.get('fallbackTo', None)
        )

    def build_config_management(self, data: dict) -> Union[ConfigManagement, None]:
        config_management = None
        if 'management' in data:
            data_management = data['management']
            config_management = ConfigManagement(
                data_management['port'],
                ssl=data_management.get('ssl', False),
                ssl_cert_file=data_management.get('sslCertFile', None),
                ssl_key_file=data_management.get('sslKeyFile', None)
            )
        return config_management

    def build_config_globals(self, data: dict) -> Union[ConfigGlobals, None]:
        config_globals = None
        if 'globals' in data:
            data_globals = data['globals']
            config_globals = ConfigGlobals(
                headers=self.build_config_headers(data_globals),
                performance_profile=data_globals.get('performance_profile', None)
            )
        return config_globals

    def build_config_performance_profile(self, data: dict) -> ConfigPerformanceProfile:
        return ConfigPerformanceProfile(
            data.get('ratio', None),
            data.get('delay', None),
            data.get('faults', None)
        )

    def build_config_root(self, data: dict) -> ConfigRoot:
        config_services = [self.build_config_http_service(service) if service.get('type', 'http') == 'http' else None for service in data['services']]
        config_management = self.build_config_management(data)
        config_templating_engine = data.get('templatingEngine', PYBARS)
        config_globals = self.build_config_globals(data)

        config_performance_profiles = None
        if 'performanceProfiles' in data:
            config_performance_profiles = {}
            for key, value in data['performanceProfiles'].items():
                config_performance_profiles['key'] = self.build_config_performance_profile(value)

        return ConfigRoot(
            config_services,
            management=config_management,
            templating_engine=config_templating_engine,
            _globals=config_globals,
            performance_profiles=config_performance_profiles
        )

    def build(self, data: dict) -> ConfigRoot:
        return self.build_config_root(data)


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
        config_root_builder.build(data)  # TODO: not fully implemented yet

        if 'performanceProfiles' in data:
            for key, performance_profile in data['performanceProfiles'].items():
                ratio = performance_profile.get('ratio')
                delay = performance_profile.get('delay', 0.0)
                faults = performance_profile.get('faults', {})
                data['performanceProfiles'][key] = PerformanceProfile(ratio, delay=delay, faults=faults)
        else:
            data['performanceProfiles'] = {}

        global_performance_profile = None
        if 'globals' in data:
            global_performance_profile = data['globals'].get('performanceProfile', None)

        data['kafka_services'] = []
        data['async_producers'] = []
        data['async_consumers'] = []
        for i, service in enumerate(data['services']):
            self.forbid_comma_in_tag(service)

            data['services'][i]['internalServiceId'] = i
            self.logs.add_service(service.get('name', ''))

            hint = None
            if 'type' not in service:
                service['type'] = 'http'
            else:
                service['type'] = service['type'].lower()

            if 'type' in service and service['type'] != 'http':
                service['address'], _ = Definition.async_address_template_renderer(
                    self.template_engine,
                    self.rendering_queue,
                    service['address']
                )
                hint = 'kafka://%s' % service['address'] if 'name' not in service else service['name']
            else:
                hint = '%s://%s:%s%s' % (
                    'https' if service.get('ssl', False) else 'http',
                    service['hostname'] if 'hostname' in service else (
                        service['address'] if 'address' in service else 'localhost'
                    ),
                    service['port'],
                    ' - %s' % service['name'] if 'name' in service else ''
                )
            self.stats.add_service(hint)

            if 'type' in service:
                if service['type'] == 'kafka':
                    kafka_service = KafkaService(
                        service['address'],
                        name=service.get('name', None),
                        definition=self,
                        _id=i,
                        ssl=service.get('ssl', False)
                    )
                    data['kafka_services'].append(kafka_service)

                    for i, actor in enumerate(service['actors']):
                        kafka_actor = KafkaActor(i, actor.get('name', None))
                        kafka_service.add_actor(kafka_actor)

                        if 'consume' in actor:
                            capture_limit = 1 if 'capture' not in actor['consume'] else actor['consume']['capture']

                            value = actor['consume'].get('value', None)
                            key = actor['consume'].get('key', None)
                            headers = actor['consume'].get('headers', {})

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
                                actor['consume']['queue'],
                                schema=actor['consume'].get('schema', None),
                                value=value,
                                key=key,
                                headers=headers,
                                capture_limit=capture_limit
                            )
                            kafka_actor.set_consumer(kafka_consumer)

                            kafka_consumer.index = len(data['async_consumers'])
                            data['async_consumers'].append(kafka_consumer)

                        if 'delay' in actor:
                            kafka_actor.set_delay(actor['delay'])

                        if 'produce' in actor:
                            queue = None
                            payload_list = KafkaProducerPayloadList()

                            produce_list = []
                            if isinstance(actor['produce'], list):
                                queue = actor['produce'][0]['queue']
                                for _produce in actor['produce']:
                                    if queue != _produce['queue']:
                                        raise AsyncProducerListQueueMismatch(kafka_actor.get_hint())
                                produce_list += actor['produce']
                            else:
                                queue = actor['produce']['queue']
                                produce_list += [actor['produce']]

                            for produce in produce_list:
                                payload = KafkaProducerPayload(
                                    produce['value'],
                                    key=produce.get('key', None),
                                    headers=produce.get('headers', {}),
                                    tag=produce.get('tag', None),
                                    enable_topic_creation=produce.get('headers', {})
                                )
                                payload_list.add_payload(payload)

                            kafka_producer = KafkaProducer(queue, payload_list)
                            kafka_actor.set_producer(kafka_producer)

                            kafka_producer.index = len(data['async_producers'])
                            data['async_producers'].append(kafka_producer)

                        if 'limit' in actor:
                            kafka_actor.set_limit(actor['limit'])

                        if 'dataset' in actor:
                            kafka_actor.set_dataset(actor['dataset'])

                        kafka_actor.multi_payloads_looped = actor.get('multiPayloadsLooped', True)
                        kafka_actor.dataset_looped = actor.get('datasetLooped', True)

                    service['internalRef'] = kafka_service

                if service['type'] != 'http':
                    continue

            if 'endpoints' not in service:
                continue
            service = Definition.analyze_service(
                service,
                self.template_engine,
                self.rendering_queue,
                performance_profiles=data['performanceProfiles'],
                global_performance_profile=global_performance_profile
            )
        return data

    def forbid_comma_in_tag(self, service):
        if 'endpoints' not in service:
            return

        for endpoint in service['endpoints']:
            for key in ('response', 'dataset'):
                if key in endpoint and isinstance(endpoint[key], list):
                    for thing in endpoint[key]:
                        if 'tag' in thing and ',' in thing['tag']:
                            raise CommaInTagIsForbidden(thing['tag'])

    def add_stopper(self, stop: dict):
        self.stoppers.append(stop)

    def trigger_stoppers(self):
        while len(self.stoppers) > 0:
            stop = self.stoppers.pop()
            stop['val'] = True

    @staticmethod
    def analyze_service(
        service,
        template_engine,
        rendering_queue,
        performance_profiles={},
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

    @staticmethod
    def async_address_template_renderer(
        template_engine: str,
        rendering_queue,
        text: str
    ) -> Tuple[str, dict]:
        if template_engine == PYBARS:
            from mockintosh.hbs.methods import env
        elif template_engine == JINJA:
            from mockintosh.j2.methods import env

        renderer = TemplateRenderer()
        return renderer.render(
            template_engine,
            text,
            rendering_queue,
            inject_methods=[
                env
            ]
        )
