#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains the handlers for the management API.
"""

import os
import re
import json
import copy
import shutil
import logging
import threading
from typing import (
    Union
)
from collections import OrderedDict
from urllib.parse import parse_qs, unquote

import yaml
from yaml.representer import Representer
import jsonschema
import tornado.web
from tornado.util import unicode_type
from tornado.escape import utf8

import mockintosh
from mockintosh.handlers import GenericHandler
from mockintosh.helpers import _safe_path_split, _b64encode, _urlsplit
from mockintosh.exceptions import (
    RestrictedFieldError,
    AsyncProducerListHasNoPayloadsMatchingTags,
    AsyncProducerPayloadLoopEnd,
    AsyncProducerDatasetLoopEnd
)
from mockintosh.kafka import KafkaService, run_loops as kafka_run_loops

POST_CONFIG_RESTRICTED_FIELDS = ('port', 'hostname', 'ssl', 'sslCertFile', 'sslKeyFile')
UNHANDLED_SERVICE_KEYS = ('name', 'port', 'hostname')
UNHANDLED_IGNORED_HEADERS = (
    'a-im',
    'accept', 'accept-charset', 'accept-datetime', 'accept-encoding', 'accept-language',
    'access-control-allow-credentials', 'access-control-allow-origin', 'access-control-request-headers',
    'access-control-request-method',
    'cache-control', 'connection', 'content-encoding', 'content-length', 'cookie',
    'date', 'dnt', 'expect', 'forwarded', 'from', 'front-end-https', 'host', 'http2-settings',
    'if-match', 'if-modified-since', 'if-none-match', 'if-range', 'if-unmodified-since',
    'max-forwards', 'origin', 'pragma', 'proxy-authorization', 'proxy-connection', 'range', 'referer',
    'save-data', 'sec-fetch-user', 'te', 'trailer', 'transfer-encoding', 'upgrade', 'upgrade-insecure-requests',
    'user-agent', 'via', 'warning',
    'x-att-deviceid', 'x-correlation-id',
    'x-forwarded-for', 'x-forwarded-host', 'x-forwarded-port', 'x-forwarded-proto',
    'x-http-method-override', 'x-real-ip', 'x-request-id', 'x-request-start', 'x-requested-with', 'x-uidh',
    'x-wap-profile',
    'x-envoy-expected-rq-timeout-ms', 'x-envoy-external-address'
)

__location__ = os.path.abspath(os.path.dirname(__file__))


def str_representer(dumper, data):
    if "\n" in data.strip():  # pragma: no cover
        # Check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


yaml.add_representer(str, str_representer)
yaml.add_representer(OrderedDict, Representer.represent_dict)


def _reset_iterators(app):
    if isinstance(app, KafkaService):
        for actor in app.actors:
            if actor.producer is not None:
                actor.producer.iteration = 0
        return

    for rule in app.default_router.rules[0].target.rules:
        if rule.target == GenericHandler:
            endpoints = rule.target_kwargs['endpoints']
            for _, methods in endpoints:
                for _, alternatives in methods.items():
                    for alternative in alternatives:
                        alternative.pop('multiResponsesIndex', None)
                        alternative.pop('datasetIndex', None)
            break


class ManagementBaseHandler(tornado.web.RequestHandler):

    def write(self, chunk: Union[str, bytes, dict]) -> None:
        if self._finished:  # pragma: no cover
            raise RuntimeError("Cannot write() after finish()")
        if not isinstance(chunk, (bytes, unicode_type, dict)):  # pragma: no cover
            message = "write() only accepts bytes, unicode, and dict objects"
            if isinstance(chunk, list):
                message += (
                    ". Lists not accepted for security reasons; see "
                    + "http://www.tornadoweb.org/en/stable/web.html#tornado.web.RequestHandler.write"  # noqa: E501, W503
                )
            raise TypeError(message)
        if isinstance(chunk, dict):
            chunk = json.dumps(chunk, sort_keys=False, indent=2)
            self.set_header("Content-Type", "application/json; charset=UTF-8")
        chunk = utf8(chunk)
        self._write_buffer.append(chunk)

    def _log(self) -> None:
        if logging.DEBUG >= logging.root.level:
            self.application.log_request(self)


class ManagementRootHandler(ManagementBaseHandler):

    async def get(self):
        with open(os.path.join(__location__, 'res/management.html'), 'r') as file:
            html = file.read()
            self.write(html)


class ManagementConfigHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server

    async def get(self):
        data = self.http_server.definition.orig_data
        self.dump(data)

    async def post(self):
        orig_data = self.decode()
        if orig_data is None:
            return

        data = copy.deepcopy(orig_data)

        if not self.validate(data):
            return

        self.http_server.definition.stats.services = []
        data = self.http_server.definition.analyze(data)
        for service in data['services']:
            hint = None
            if 'type' in service and service['type'] != 'http':
                service['address'], _ = mockintosh.Definition.async_address_template_renderer(
                    self.http_server.definition.template_engine,
                    self.http_server.definition.rendering_queue,
                    service['address']
                )
                hint = 'kafka://%s' % service['address'] if 'name' not in service else service['name']
            else:
                hint = '%s://%s:%s%s' % (
                    'https' if service.get('ssl', False) else 'http',
                    service['hostname'] if 'hostname' in service else (
                        self.http_server.address if self.http_server.address else 'localhost'
                    ),
                    service['port'],
                    ' - %s' % service['name'] if 'name' in service else ''
                )
            self.http_server.definition.stats.add_service(hint)

        for kafka_service in data['kafka_services']:
            self.http_server._apps.apps[kafka_service.id] = kafka_service

        for i, service in enumerate(data['services']):
            if 'type' in service and service['type'] != 'http':  # pragma: no cover
                continue

            service['internalServiceId'] = i
            if not self.update_service(service, i):
                return

        self.http_server.definition.stats.reset()
        self.http_server.definition.orig_data = orig_data
        self.http_server.definition.data = data

        self.update_globals()

        self.http_server.definition.trigger_stoppers()
        stop = {'val': False}
        self.http_server.definition.add_stopper(stop)
        kafka_run_loops(self.http_server.definition, stop)

        self.set_status(204)

    def update_service(self, service, service_index) -> bool:
        try:
            self._update_service(service, service_index)
            return True
        except RestrictedFieldError as e:
            self.set_status(500)
            self.write(str(e))
            return False

    def _update_service(self, service, service_index):
        self.check_restricted_fields(service, service_index)
        endpoints = []
        self.http_server.definition.stats.services[service_index].endpoints = []
        self.http_server.definition.logs.services[service_index].name = service['name'] if 'name' in service else ''

        if 'endpoints' in service:
            endpoints = mockintosh.servers.HttpServer.merge_alternatives(
                service,
                self.http_server.definition.stats
            )
        merged_endpoints = []
        for endpoint in endpoints:
            merged_endpoints.append((endpoint['path'], endpoint['methods']))

        for rule in self.http_server._apps.apps[service_index].default_router.rules[0].target.rules:
            if rule.target == GenericHandler:
                rule.target_kwargs['endpoints'] = merged_endpoints
                break

        mockintosh.servers.HttpServer.log_merged_endpoints(merged_endpoints)

    def check_restricted_fields(self, service, service_index):
        for field in POST_CONFIG_RESTRICTED_FIELDS:
            if (
                (field in service and field not in self.http_server.definition.orig_data['services'][service_index])
                or  # noqa: W504, W503
                (field not in service and field in self.http_server.definition.orig_data['services'][service_index])
                or  # noqa: W504, W503
                field in service and field in self.http_server.definition.orig_data['services'][service_index] and (
                    service[field] != self.http_server.definition.orig_data['services'][service_index][field]
                )
            ):
                raise RestrictedFieldError(field)

    def update_globals(self):
        for i, service in enumerate(self.http_server.definition.data['services']):
            if 'type' in service and service['type'] != 'http':  # pragma: no cover
                continue

            self.http_server.globals = self.http_server.definition.data['globals'] if (
                'globals' in self.http_server.definition.data
            ) else {}
            for rule in self.http_server._apps.apps[i].default_router.rules[0].target.rules:
                if rule.target == GenericHandler:
                    rule.target_kwargs['_globals'] = self.http_server.globals

    def decode(self) -> Union[dict, None]:
        body = self.request.body.decode()
        try:
            return yaml.safe_load(body)
        except (yaml.scanner.ScannerError, yaml.parser.ParserError) as e:
            self.set_status(400)
            self.write('JSON/YAML decode error:\n%s' % str(e))
            return None

    def validate(self, data) -> bool:
        try:
            jsonschema.validate(instance=data, schema=self.http_server.definition.schema)
            return True
        except jsonschema.exceptions.ValidationError as e:
            self.set_status(400)
            self.write('JSON schema validation error:\n%s' % str(e))
            return False

    def dump(self, data) -> None:
        _format = self.get_query_argument('format', default='json')
        if _format == 'yaml':
            self.set_header('Content-Type', 'application/x-yaml')
            self.write(yaml.dump(data, sort_keys=False))
        else:
            self.write(data)


class ManagementStatsHandler(ManagementBaseHandler):

    def initialize(self, stats):
        self.stats = stats

    async def get(self):
        self.write(self.stats.json())

    async def delete(self):
        self.stats.reset()
        self.set_status(204)


class ManagementLogsHandler(ManagementBaseHandler):

    def initialize(self, logs):
        self.logs = logs

    async def get(self):
        self.write(self.logs.json())

    async def post(self):
        enabled = not self.get_body_argument('enable', default=True) in ('false', 'False', '0')
        for service in self.logs.services:
            service.enabled = enabled
        self.set_status(204)

    async def delete(self):
        self.write(self.logs.json())
        self.logs.reset()


class ManagementResetIteratorsHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server

    async def post(self):
        for app in self.http_server._apps.apps:
            _reset_iterators(app)
        self.set_status(204)


class ManagementUnhandledHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server

    async def get(self):
        data = {
            'services': []
        }

        services = self.http_server.definition.orig_data['services']
        for i, service in enumerate(services):
            if 'type' in service and service['type'] != 'http':
                continue

            endpoints = self.build_unhandled_requests(i)
            if not endpoints:
                continue
            new_service = dict((k, service[k]) for k in UNHANDLED_SERVICE_KEYS if k in service)
            new_service['endpoints'] = endpoints
            data['services'].append(new_service)

        if data['services'] and not self.validate(data):  # pragma: no cover
            return

        self.dump(data)

    async def delete(self):
        for i, _ in enumerate(self.http_server.unhandled_data.requests):
            for key, _ in self.http_server.unhandled_data.requests[i].items():
                self.http_server.unhandled_data.requests[i][key] = []
        self.set_status(204)

    def build_unhandled_requests(self, service_id):
        endpoints = []

        for requests in self.http_server.unhandled_data.requests[service_id].values():
            if not requests:
                continue

            request = requests[-1][0]
            response = requests[-1][1]

            config_template = {}

            # Path
            config_template['path'] = request.path

            # Method
            config_template['method'] = request.method

            # Headers
            for key, value in request.headers._dict.items():
                continue_parent = False
                for _request in requests:
                    if (
                        (key.title() not in _request[0].headers._dict)
                        or  # noqa: W504, W503
                        (key.title() in _request[0].headers._dict and value != _request[0].headers._dict[key.title()])
                    ):
                        continue_parent = True
                        break
                if continue_parent:
                    continue
                if key.lower() not in UNHANDLED_IGNORED_HEADERS:
                    if 'headers' not in config_template:
                        config_template['headers'] = {}
                    config_template['headers'][key] = value

            # Query String
            for key, value in request.query_arguments.items():
                if 'queryString' not in config_template:
                    config_template['queryString'] = {}
                config_template['queryString'][key] = value[0].decode()

            if response is None:
                config_template['response'] = ''
            else:
                response.headers.pop('Content-Length', None)

                config_template['response'] = {
                    'status': response.status,
                    'headers': {},
                    'body': ''
                }
                for key, value in response.headers.items():
                    try:
                        config_template['response']['headers'][key] = value.decode()
                    except (AttributeError, UnicodeDecodeError):
                        config_template['response']['headers'][key] = _b64encode(value) if isinstance(value, (bytes, bytearray)) else value
                if response.body is not None:
                    try:
                        config_template['response']['body'] = response.body.decode()
                    except (AttributeError, UnicodeDecodeError):
                        config_template['response']['body'] = _b64encode(response.body) if isinstance(response.body, (bytes, bytearray)) else response.body
            endpoints.append(config_template)

        return endpoints

    def validate(self, data) -> bool:
        try:
            jsonschema.validate(instance=data, schema=self.http_server.definition.schema)
            return True
        except jsonschema.exceptions.ValidationError as e:  # pragma: no cover
            self.set_status(400)
            self.write('JSON schema validation error:\n%s' % str(e))
            return False

    def dump(self, data) -> None:
        _format = self.get_query_argument('format', default='json')
        if _format == 'yaml':
            self.set_header('Content-Type', 'application/x-yaml')
            self.write(yaml.dump(data, sort_keys=False))
        else:
            self.write(data)


class ManagementOasHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server

    async def get(self):
        data = {
            'documents': []
        }

        services = self.http_server.definition.orig_data['services']
        for i, service in enumerate(services):
            if 'type' in service and service['type'] != 'http':
                continue

            data['documents'].append(self.build_oas(i))

        self.write(data)

    def build_oas(self, service_id):
        service = self.http_server.definition.orig_data['services'][service_id]
        ssl = service.get('ssl', False)
        protocol = 'https' if ssl else 'http'
        hostname = self.http_server.address if self.http_server.address else (
            'localhost' if 'hostname' not in service else service['hostname']
        )

        if 'oas' in service:
            custom_oas = service['oas']
            if isinstance(custom_oas, str) and len(custom_oas) > 1 and custom_oas[0] == '@':
                custom_oas_path = self.resolve_relative_path(self.http_server.definition.source_dir, custom_oas)
                with open(custom_oas_path, 'r') as file:
                    custom_oas = json.load(file)
            if 'servers' not in custom_oas:
                custom_oas['servers'] = []
            custom_oas['servers'].insert(
                0,
                {
                    'url': '%s://%s:%s' % (protocol, hostname, service['port']),
                    'description': service['name'] if 'name' in service else ''
                }
            )
            return custom_oas

        document = {
            'openapi': '3.0.0',
            'info': {
                'title': service['name'] if 'name' in service else '%s://%s:%s' % (protocol, hostname, service['port']),
                'description': 'Automatically generated Open API Specification.',
                'version': '0.1.9'
            },
            'servers': [
                {
                    'url': '%s://%s:%s' % (protocol, hostname, service['port']),
                    'description': service['name'] if 'name' in service else ''
                }
            ],
            'paths': {}
        }

        endpoints = []
        for rule in self.http_server._apps.apps[service_id].default_router.rules[0].target.rules:
            if rule.target == GenericHandler:
                endpoints = rule.target_kwargs['endpoints']

        for endpoint in endpoints:
            original_path = list(endpoint[1].values())[0][0]['internalOrigPath']
            scheme, netloc, original_path, query, fragment = _urlsplit(original_path)
            query_string = parse_qs(query, keep_blank_values=True)
            path, path_params = self.path_handlebars_to_oas(original_path)
            methods = {}
            for method, alternatives in endpoint[1].items():
                if not alternatives:  # pragma: no cover
                    continue  # https://github.com/nedbat/coveragepy/issues/198

                method_data = {'responses': {}}
                alternative = alternatives[0]

                # requestBody
                if 'body' in alternative:

                    # schema
                    if 'schema' in alternative['body']:
                        json_schema = alternative['body']['schema']
                        if isinstance(json_schema, str) and len(json_schema) > 1 and json_schema[0] == '@':
                            json_schema_path = self.resolve_relative_path(rule.target_kwargs['config_dir'], json_schema)
                            with open(json_schema_path, 'r') as file:
                                json_schema = json.load(file)
                        method_data['requestBody'] = {
                            'required': True,
                            'content': {
                                'application/json': {
                                    'schema': json_schema
                                }
                            }
                        }

                    # text
                    if 'text' in alternative['body']:
                        method_data['requestBody'] = {
                            'required': True,
                            'content': {
                                '*/*': {
                                    'schema': {
                                        'type': 'string'
                                    }
                                }
                            }
                        }

                # path parameters
                if path_params:
                    if 'parameters' not in method_data:
                        method_data['parameters'] = []
                    for param in path_params:
                        data = {
                            'in': 'path',
                            'name': param,
                            'required': True,
                            'schema': {
                                'type': 'string'
                            }
                        }
                        method_data['parameters'].append(data)

                # header parameters
                if 'headers' in alternative:
                    if 'parameters' not in method_data:
                        method_data['parameters'] = []
                    for key in alternative['headers'].keys():
                        data = {
                            'in': 'header',
                            'name': key,
                            'required': True,
                            'schema': {
                                'type': 'string'
                            }
                        }
                        method_data['parameters'].append(data)

                # query string parameters
                if 'queryString' in alternative:
                    if 'parameters' not in method_data:
                        method_data['parameters'] = []
                    query_string.update(alternative['queryString'])
                    for key in query_string.keys():
                        data = {
                            'in': 'query',
                            'name': key,
                            'required': True,
                            'schema': {
                                'type': 'string'
                            }
                        }
                        method_data['parameters'].append(data)

                # responses
                if 'response' in alternative:
                    response = alternative['response']
                    status = 200
                    if isinstance(response, dict) and 'status' in response:
                        status = str(response['status'])
                    if status not in ('RST', 'FIN'):
                        try:
                            int(status)
                        except ValueError:
                            status = 'default'
                        status_data = {}
                        if isinstance(response, dict) and 'headers' in response:
                            new_headers = {k.title(): v for k, v in response['headers'].items()}
                            if 'Content-Type' in new_headers:
                                if new_headers['Content-Type'].startswith('application/json'):
                                    status_data = {
                                        'content': {
                                            'application/json': {
                                                'schema': {}
                                            }
                                        }
                                    }
                            status_data['headers'] = {}
                            for key in new_headers.keys():
                                status_data['headers'][key] = {
                                    'schema': {
                                        'type': 'string'
                                    }
                                }
                        status_data['description'] = ''
                        method_data['responses'][status] = status_data

                if not method_data['responses']:
                    method_data['responses']['default'] = {
                        'description': ''
                    }
                methods[method.lower()] = method_data
            document['paths']['%s' % path] = methods

        document['paths'] = OrderedDict(sorted(document['paths'].items(), key=lambda t: t[0]))

        return document

    def path_handlebars_to_oas(self, path):
        segments = _safe_path_split(path)
        params = []
        new_segments = []
        for segment in segments:
            match = re.search(r'{{(.*)}}', segment)
            if match is not None:
                name = match.group(1).strip()
                param = None
                if ' ' not in name:
                    param = name
                else:
                    param = 'param%d' % (len(params) + 1)
                new_segments.append('{%s}' % param)
                params.append(param)
            else:
                new_segments.append(segment)
        return '/'.join(new_segments), params

    def resolve_relative_path(self, config_dir, source_text):
        relative_path = None
        orig_relative_path = source_text[1:]

        error_msg = 'External OAS document %r couldn\'t be accessed or found!' % orig_relative_path
        if orig_relative_path[0] == '/':
            orig_relative_path = orig_relative_path[1:]
        relative_path = os.path.join(config_dir, orig_relative_path)
        if not os.path.isfile(relative_path):
            self.send_error(500, message=error_msg)
            return None
        relative_path = os.path.abspath(relative_path)
        if not relative_path.startswith(config_dir):
            self.send_error(500, message=error_msg)
            return None

        return relative_path


class ManagementTagHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server

    async def get(self):
        data = {
            'tags': []
        }

        for app in self.http_server._apps.apps:
            if isinstance(app, KafkaService):
                data['tags'] += app.tags
                continue

            for rule in app.default_router.rules[0].target.rules:
                if rule.target == GenericHandler:
                    data['tags'] += rule.target_kwargs['tags']

        data['tags'] = list(set(data['tags']))

        self.write(data)

    async def post(self):
        data = self.get_query_argument('current', default=None)
        if data is None:
            data = self.request.body.decode()
        data = data.split(',')
        for app in self.http_server._apps.apps:
            if isinstance(app, KafkaService):
                app.tags = data
                continue

            for rule in app.default_router.rules[0].target.rules:
                if rule.target == GenericHandler:
                    rule.target_kwargs['tags'] = data

        self.set_status(204)


class ManagementResourcesHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server
        files = []
        cwd = self.http_server.definition.source_dir
        for service in self.http_server.definition.orig_data['services']:
            if 'type' in service and service['type'] == 'kafka':
                for actor in service['actors']:
                    if 'consume' in actor and 'schema' in actor['consume'] and (
                        isinstance(actor['consume']['schema'], str) and actor['consume']['schema'].startswith('@')
                    ):
                        files.append(actor['consume']['schema'][1:])
                    if 'produce' in actor:
                        if 'headers' in actor['produce']:
                            for key, value in actor['produce']['headers'].items():
                                if value.startswith('@'):
                                    files.append(value[1:])
                        if 'value' in actor['produce'] and (
                            isinstance(actor['produce']['value'], str) and actor['produce']['value'].startswith('@')
                        ):
                            files.append(actor['produce']['value'][1:])
                    if 'dataset' in actor and (
                        isinstance(actor['dataset'], str) and actor['dataset'].startswith('@')
                    ):
                        files.append(actor['dataset'][1:])
            else:
                if 'oas' in service:
                    if service['oas'].startswith('@'):
                        files.append(service['oas'][1:])
                if 'endpoints' not in service:
                    continue
                for endpoint in service['endpoints']:
                    if 'body' in endpoint and 'schema' in endpoint['body'] and (
                        isinstance(endpoint['body']['schema'], str) and endpoint['body']['schema'].startswith('@')
                    ):
                        files.append(endpoint['body']['schema'][1:])
                    if 'dataset' in endpoint and isinstance(endpoint['dataset'], str) and (
                        endpoint['dataset'].startswith('@')
                    ):
                        files.append(endpoint['dataset'][1:])
                    if 'response' not in endpoint:
                        continue
                    response = endpoint['response']
                    if isinstance(response, str):
                        if response.startswith('@'):
                            files.append(response[1:])
                    elif isinstance(response, dict) and 'body' in response:
                        if response['body'].startswith('@'):
                            files.append(response['body'][1:])
                    elif isinstance(response, list):
                        for el in response:
                            if isinstance(el, str):
                                if el.startswith('@'):
                                    files.append(el[1:])
                            elif isinstance(el, dict) and 'body' in el:
                                if el['body'].startswith('@'):
                                    files.append(el['body'][1:])
        files = list(set(files))
        files = list(filter(lambda x: (os.path.abspath(os.path.join(cwd, x)).startswith(cwd)), files))
        new_files = []
        for path in files:
            fail = False
            for segment in os.path.split(path):
                match = re.search(r'{{(.*)}}', segment)
                if match is not None:
                    fail = True
                    break
            if not fail:
                new_files.append(path)
        files = new_files
        self.files = sorted(files)
        self.files_abs = [os.path.abspath(os.path.join(cwd, x)) for x in self.files]

    async def get(self):
        data = None
        cwd = self.http_server.definition.source_dir
        path = self.get_query_argument('path', default=None)
        orig_path = path
        if path is None:
            data = {
                'files': self.files
            }
            self.write(data)
            return
        else:
            if not path:
                self.set_status(400)
                self.write('\'path\' cannot be empty!')
                return
            path = os.path.abspath(os.path.join(cwd, path.lstrip('/')))
            if not path.startswith(cwd):
                self.set_status(403)
                self.write('The path %s couldn\'t be accessed!' % orig_path)
                return
            # path is SAFE
            if not os.path.exists(path):
                self.set_status(400)
                self.write('The path %s does not exist!' % orig_path)
                return
            # path is OK
            if os.path.isdir(path):
                self.set_status(400)
                self.write('The path %s is a directory!' % orig_path)
                return
            if path not in self.files_abs:
                self.set_status(400)
                self.write('The path %s is not defined in the configuration file!' % orig_path)
                return
            else:
                _format = self.get_query_argument('format', default='text')
                if _format == 'text':
                    with open(path, 'rb') as file:
                        data = file.read()
                elif _format == 'stream':
                    buf_size = 4096
                    self.set_header('Content-Type', 'application/octet-stream')
                    self.set_header('Content-Disposition', 'attachment; filename=' + os.path.basename(path))
                    with open(path, 'rb') as f:
                        while True:
                            data = f.read(buf_size)
                            if not data:
                                break
                            self.write(data)
                    return
        self.write(data)

    async def post(self):
        cwd = self.http_server.definition.source_dir
        path = self.get_body_argument('path', default=None)
        orig_path = path
        if path is not None:
            if not path:
                self.set_status(400)
                self.write('\'path\' cannot be empty!')
                return
            path = os.path.abspath(os.path.join(cwd, path.lstrip('/')))
            if not path.startswith(cwd):
                self.set_status(403)
                self.write('The path %s couldn\'t be accessed!' % orig_path)
                return
            # path is SAFE

        if self.request.files:
            for key, files in self.request.files.items():
                for file in files:
                    if path is None:
                        file_path = os.path.join(cwd, key if key else file['filename'])
                    else:
                        file_path = os.path.join(path, key if key else file['filename'])
                    file_path = os.path.abspath(file_path)
                    if not file_path.startswith(cwd):
                        self.set_status(403)
                        self.write('The path %s couldn\'t be accessed!' % orig_path)
                        return
                    # file_path is SAFE
                    if os.path.exists(file_path) and os.path.isdir(file_path):
                        self.set_status(400)
                        self.write('The path %s is a directory!' % file_path[len(cwd) + 1:])
                        return
                    if file_path not in self.files_abs:
                        self.set_status(400)
                        self.write('The path %s is not defined in the configuration file!' % file_path[len(cwd) + 1:])
                        return
                    # file_path is OK
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, 'wb') as _file:
                        _file.write(file['body'])
        else:
            file = self.get_body_argument('file', default=None)
            if file is None:
                self.set_status(400)
                self.write('\'file\' parameter is required!')
                return
            if path is None:
                self.set_status(400)
                self.write('\'path\' parameter is required!')
                return
            if os.path.exists(path) and os.path.isdir(path):
                self.set_status(400)
                self.write('The path %s is a directory!' % orig_path)
                return
            if path not in self.files_abs:
                self.set_status(400)
                self.write('The path %s is not defined in the configuration file!' % orig_path)
                return
            # path is OK
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as _file:
                _file.write(file)
        self.set_status(204)

    async def delete(self):
        cwd = self.http_server.definition.source_dir
        path = self.get_query_argument('path', default=None)
        keep = self.get_query_argument('keep', default=False)
        orig_path = path
        if path is None:
            self.set_status(400)
            self.write('\'path\' parameter is required!')
            return
        if not path:
            self.set_status(400)
            self.write('\'path\' cannot be empty!')
            return
        path = os.path.abspath(os.path.join(cwd, path.lstrip('/')))
        if not path.startswith(cwd):
            self.set_status(403)
            self.write('The path %s couldn\'t be accessed!' % orig_path)
            return
        # path is SAFE
        if not os.path.exists(path):
            self.set_status(400)
            self.write('The path %s does not exist!' % orig_path)
            return
        if path not in self.files_abs:
            self.set_status(400)
            self.write('The path %s is not defined in the configuration file!' % orig_path)
            return
        # path is OK
        if os.path.isfile(path):
            os.remove(path)
            if not keep:
                ref = os.path.dirname(path)
                while ref:
                    if os.listdir(ref) or ref == cwd:  # pragma: no cover
                        break
                    shutil.rmtree(ref)
                    ref = os.path.dirname(ref)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        self.set_status(204)


class ManagementServiceRootHandler(ManagementBaseHandler):

    async def get(self):
        with open(os.path.join(__location__, 'res/management.html'), 'r') as file:
            html = file.read()
            self.write(html)


class ManagementServiceRootRedirectHandler(ManagementBaseHandler):

    def initialize(self, management_root):
        self.management_root = management_root

    async def get(self):
        self.redirect('/%s/' % self.management_root)


class ManagementServiceConfigHandler(ManagementConfigHandler):

    def initialize(self, http_server, service_id):
        self.http_server = http_server
        self.service_id = service_id

    async def get(self):
        data = self.http_server.definition.orig_data['services'][self.service_id]
        self.dump(data)

    async def post(self):
        orig_data = self.decode()
        if orig_data is None:
            return

        data = copy.deepcopy(orig_data)

        imaginary_config = copy.deepcopy(self.http_server.definition.orig_data)
        imaginary_config['services'][self.service_id] = data

        if not self.validate(imaginary_config):
            return

        global_performance_profile = None
        if 'globals' in self.http_server.definition.orig_data:
            global_performance_profile = self.http_server.definition.orig_data['globals'].get('performanceProfile', None)
        data = mockintosh.Definition.analyze_service(
            data,
            self.http_server.definition.template_engine,
            self.http_server.definition.rendering_queue,
            performance_profiles=self.http_server.definition.data['performanceProfiles'],
            global_performance_profile=global_performance_profile
        )
        data['internalServiceId'] = self.service_id
        if not self.update_service(data, self.service_id):
            return

        self.http_server.definition.stats.reset()
        self.http_server.definition.orig_data['services'][self.service_id] = orig_data
        self.http_server.definition.data['services'][self.service_id] = data

        self.set_status(204)


class ManagementServiceStatsHandler(ManagementBaseHandler):

    def initialize(self, stats, service_id):
        self.stats = stats
        self.service_id = service_id

    async def get(self):
        self.write(self.stats.services[self.service_id].json())

    async def delete(self):
        self.stats.services[self.service_id].reset()
        self.set_status(204)


class ManagementServiceLogsHandler(ManagementBaseHandler):

    def initialize(self, logs, service_id):
        self.logs = logs
        self.service_id = service_id

    async def get(self):
        self.write(self.logs.services[self.service_id].json())

    async def post(self):
        self.logs.services[self.service_id].enabled = not (
            self.get_body_argument('enable', default=True) in ('false', 'False', '0')
        )
        self.set_status(204)

    async def delete(self):
        self.write(self.logs.services[self.service_id].json())
        self.logs.services[self.service_id].reset()


class ManagementServiceResetIteratorsHandler(ManagementBaseHandler):

    def initialize(self, http_server, service_id):
        self.http_server = http_server
        self.service_id = service_id

    async def post(self):
        app = self.http_server._apps.apps[self.service_id]
        _reset_iterators(app)
        self.set_status(204)


class ManagementServiceUnhandledHandler(ManagementUnhandledHandler):

    def initialize(self, http_server, service_id):
        self.http_server = http_server
        self.service_id = service_id

    async def get(self):
        data = {
            'services': []
        }

        service = self.http_server.definition.orig_data['services'][self.service_id]
        data['services'].append(dict((k, service[k]) for k in UNHANDLED_SERVICE_KEYS if k in service))
        data['services'][0]['endpoints'] = self.build_unhandled_requests(self.service_id)

        imaginary_config = copy.deepcopy(self.http_server.definition.orig_data)
        imaginary_config['services'] = data['services']

        if not self.validate(imaginary_config):  # pragma: no cover
            return

        self.dump(data)

    async def delete(self):
        for key, _ in self.http_server.unhandled_data.requests[self.service_id].items():
            self.http_server.unhandled_data.requests[self.service_id][key] = []
        self.set_status(204)


class ManagementServiceOasHandler(ManagementOasHandler):

    def initialize(self, http_server, service_id):
        self.http_server = http_server
        self.service_id = service_id

    async def get(self):
        self.write(self.build_oas(self.service_id))


class ManagementServiceTagHandler(ManagementBaseHandler):

    def initialize(self, http_server, service_id):
        self.http_server = http_server
        self.service_id = service_id

    async def get(self):
        for rule in self.http_server._apps.apps[self.service_id].default_router.rules[0].target.rules:
            if rule.target == GenericHandler:
                tags = rule.target_kwargs['tags']
                if not tags:
                    self.set_status(204)
                else:
                    data = {
                        'tags': tags
                    }
                    self.write(data)

    async def post(self):
        data = self.get_query_argument('current', default=None)
        if data is None:
            data = self.request.body.decode()
        data = data.split(',')
        for rule in self.http_server._apps.apps[self.service_id].default_router.rules[0].target.rules:
            if rule.target == GenericHandler:
                rule.target_kwargs['tags'] = data

        self.set_status(204)


class UnhandledData:
    def __init__(self):
        self.requests = []


class ManagementAsyncHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server

    async def get(self):
        data = {
            'producers': [],
            'consumers': []
        }

        for producer in self.http_server.definition.data['async_producers']:
            data['producers'].append(producer.info())

        for consumer in self.http_server.definition.data['async_consumers']:
            data['consumers'].append(consumer.info())

        self.dump(data)

    def dump(self, data) -> None:
        _format = self.get_query_argument('format', default='json')
        if _format == 'yaml':
            self.set_header('Content-Type', 'application/x-yaml')
            self.write(yaml.dump(data, sort_keys=False))
        else:
            self.write(data)


class ManagementAsyncProducersHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server

    async def post(self, value):
        if value.isnumeric():
            try:
                index = int(value)
                producer = self.http_server.definition.data['async_producers'][index]
                try:
                    producer.check_tags()
                    producer.check_payload_lock()
                    producer.check_dataset_lock()
                    t = threading.Thread(target=producer.produce, args=(), kwargs={
                        'ignore_delay': True
                    })
                    t.daemon = True
                    t.start()
                    self.set_status(202)
                    self.write(producer.info())
                except (
                    AsyncProducerListHasNoPayloadsMatchingTags,
                    AsyncProducerPayloadLoopEnd,
                    AsyncProducerDatasetLoopEnd
                ) as e:
                    self.set_status(410)
                    self.write(str(e))
                    return
            except IndexError:
                self.set_status(400)
                self.write('Invalid producer index!')
                return
        else:
            producer = None
            actor_name = unquote(value)
            services = self.http_server.definition.data['kafka_services']
            for service_id, service in enumerate(services):
                for actor_id, actor in enumerate(service.actors):
                    if actor.name == actor_name:
                        if actor.producer is None:  # pragma: no cover
                            continue
                        producer = actor.producer
                        try:
                            producer.check_tags()
                            producer.check_payload_lock()
                            producer.check_dataset_lock()
                            t = threading.Thread(target=actor.producer.produce, args=(), kwargs={
                                'ignore_delay': True
                            })
                            t.daemon = True
                            t.start()
                        except (
                            AsyncProducerListHasNoPayloadsMatchingTags,
                            AsyncProducerPayloadLoopEnd,
                            AsyncProducerDatasetLoopEnd
                        ) as e:
                            self.set_status(410)
                            self.write(str(e))
                            return

            if producer is None:
                self.set_status(400)
                self.write('No producer actor is found for: %r' % actor_name)
                return
            else:
                self.set_status(202)
                self.write(producer.info())


class ManagementAsyncConsumersHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server

    async def get(self, value):
        if value.isnumeric():
            try:
                index = int(value)
                consumer = self.http_server.definition.data['async_consumers'][index]
                self.write(consumer.single_log_service.json())
            except IndexError:
                self.set_status(400)
                self.write('Invalid consumer index!')
                return
        else:
            consumer = None
            actor_name = unquote(value)
            services = self.http_server.definition.data['kafka_services']
            for service_id, service in enumerate(services):
                for actor_id, actor in enumerate(service.actors):
                    if actor.name == actor_name:
                        if actor.consumer is None:  # pragma: no cover
                            continue
                        consumer = actor.consumer

            if consumer is None:
                self.set_status(400)
                self.write('No consumer actor is found for: %r' % actor_name)
                return
            else:
                self.write(consumer.single_log_service.json())

    async def delete(self, value):
        if value.isnumeric():
            try:
                index = int(value)
                consumer = self.http_server.definition.data['async_consumers'][index]
                consumer.single_log_service.reset()
                self.set_status(204)
            except IndexError:
                self.set_status(400)
                self.write('Invalid consumer index!')
                return
        else:
            consumer = None
            actor_name = unquote(value)
            services = self.http_server.definition.data['kafka_services']
            for service_id, service in enumerate(services):
                for actor_id, actor in enumerate(service.actors):
                    if actor.name == actor_name:
                        if actor.consumer is None:  # pragma: no cover
                            continue
                        consumer = actor.consumer

            if consumer is None:
                self.set_status(400)
                self.write('No consumer actor is found for: %r' % actor_name)
                return
            else:
                consumer.single_log_service.reset()
                self.set_status(204)
