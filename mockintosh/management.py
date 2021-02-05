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
from typing import (
    Union
)
from collections import OrderedDict

import yaml
import jsonschema
import tornado.web
from tornado.util import unicode_type
from tornado.escape import utf8

import mockintosh
from mockintosh.handlers import GenericHandler
from mockintosh.methods import _decoder, _safe_path_split

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


def _reset_iterators(app):
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
        if self._finished:
            raise RuntimeError("Cannot write() after finish()")
        if not isinstance(chunk, (bytes, unicode_type, dict)):
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


class ManagementRootHandler(ManagementBaseHandler):

    def get(self):
        with open(os.path.join(__location__, 'res/management.html'), 'r') as file:
            html = file.read()
            self.write(html)


class ManagementConfigHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server

    def get(self):
        data = self.http_server.definition.orig_data
        _format = self.get_query_argument('format', default='json')
        if _format == 'yaml':
            self.set_header('Content-Type', 'application/x-yaml')
            self.write(yaml.dump(data, sort_keys=False))
        else:
            self.write(data)

    def post(self):
        body = _decoder(self.request.body)
        try:
            orig_data = yaml.safe_load(body)
        except json.JSONDecodeError as e:
            self.set_status(400)
            self.write('JSON/YAML decode error:\n%s' % str(e))
            return
        data = copy.deepcopy(orig_data)

        try:
            jsonschema.validate(instance=data, schema=self.http_server.definition.schema)
        except jsonschema.exceptions.ValidationError as e:
            self.set_status(400)
            self.write('JSON schema validation error:\n%s' % str(e))
            return

        try:
            data = mockintosh.Definition.analyze(data, self.http_server.definition.template_engine)
            self.http_server.stats.services = []
            for service in data['services']:
                self.http_server.stats.add_service(
                    '%s:%s%s' % (
                        service['hostname'] if 'hostname' in service else (
                            self.http_server.address if self.http_server.address else 'localhost'
                        ),
                        service['port'],
                        ' - %s' % service['name'] if 'name' in service else ''
                    )
                )
            for i, service in enumerate(data['services']):
                service['internalServiceId'] = i
                self.update_service(service, i)
        except Exception as e:
            self.set_status(400)
            self.write('Something bad happened:\n%s' % str(e))
            return

        self.http_server.stats.reset()
        self.http_server.definition.orig_data = orig_data
        self.http_server.definition.data = data

        self.set_status(204)

    def update_service(self, service, service_index):
        self.check_restricted_fields(service, service_index)
        endpoints = []
        self.http_server.stats.services[service_index].endpoints = []

        if 'endpoints' in service:
            endpoints = mockintosh.servers.HttpServer.merge_alternatives(service, self.http_server.stats)
        merged_endpoints = []
        for endpoint in endpoints:
            merged_endpoints.append((endpoint['path'], endpoint['methods']))

        endpoints_setted = False
        for rule in self.http_server._apps.apps[service_index].default_router.rules[0].target.rules:
            if rule.target == GenericHandler:
                rule.target_kwargs['endpoints'] = merged_endpoints
                endpoints_setted = True
                break
        if not endpoints_setted:
            raise Exception('Target handler couldn\'t found.')

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
                raise Exception('%s field is restricted!' % field)


class ManagementStatsHandler(ManagementBaseHandler):

    def initialize(self, stats):
        self.stats = stats

    def get(self):
        self.write(self.stats.json())

    def delete(self):
        self.stats.reset()
        self.set_status(204)


class ManagementResetIteratorsHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server

    def post(self):
        for app in self.http_server._apps.apps:
            _reset_iterators(app)
        self.set_status(204)


class ManagementUnhandledHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server

    def get(self):
        data = {
            'services': []
        }

        services = self.http_server.definition.orig_data['services']
        for i, service in enumerate(services):
            if 'endpoints' not in service or not service['endpoints']:
                continue
            endpoints = self.build_unhandled_requests(i)
            if not endpoints:
                continue
            new_service = dict((k, service[k]) for k in UNHANDLED_SERVICE_KEYS if k in service)
            new_service['endpoints'] = endpoints
            data['services'].append(new_service)

        if data['services']:
            try:
                jsonschema.validate(instance=data, schema=self.http_server.definition.schema)
            except jsonschema.exceptions.ValidationError as e:
                self.set_status(400)
                self.write('JSON schema validation error:\n%s' % str(e))
                return

        self.write(data)

    def build_unhandled_requests(self, service_id):
        endpoints = []

        for requests in self.http_server.unhandled_data.requests[service_id].values():
            if not requests:
                continue

            request = requests[-1]
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
                        (key.title() not in _request.headers._dict)
                        or  # noqa: W504, W503
                        (key.title() in _request.headers._dict and value != _request.headers._dict[key.title()])
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
                continue_parent = False
                for _request in requests:
                    if (
                        (key not in request.query_arguments)
                        or  # noqa: W504, W503
                        (key in request.query_arguments and value != request.query_arguments[key])
                    ):
                        continue_parent = True
                        break
                if continue_parent:
                    continue
                if 'queryString' not in config_template:
                    config_template['queryString'] = {}
                config_template['queryString'][key] = _decoder(value[0])

            config_template['response'] = ''
            endpoints.append(config_template)

        return endpoints


class ManagementOasHandler(ManagementBaseHandler):

    def initialize(self, http_server):
        self.http_server = http_server

    def get(self):
        data = {
            'documents': []
        }

        services = self.http_server.definition.orig_data['services']
        for i in range(len(services)):
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
            path, path_params = self.path_handlebars_to_oas(original_path)
            methods = {}
            for method, alternatives in endpoint[1].items():
                if not alternatives:
                    continue

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
                    for key in alternative['queryString'].keys():
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
                    if 'status' in response:
                        status = str(response['status'])
                    if status not in ('RST', 'FIN'):
                        try:
                            int(status)
                        except ValueError:
                            status = 'default'
                        status_data = {}
                        if 'headers' in response:
                            new_headers = {k.title(): v for k, v in response['headers'].items()}
                            if 'Content-Type' in new_headers:
                                if 'application/json' == new_headers['Content-Type']:
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

        error_msg = 'External template file \'%s\' couldn\'t be accessed or found!' % orig_relative_path
        if orig_relative_path[0] == '/':
            orig_relative_path = orig_relative_path[1:]
        relative_path = os.path.join(config_dir, orig_relative_path)
        if not os.path.isfile(relative_path):
            self.send_error(403, message=error_msg)
            return None
        relative_path = os.path.abspath(relative_path)
        if not relative_path.startswith(config_dir):
            self.send_error(403, message=error_msg)
            return None

        return relative_path


class ManagementServiceRootHandler(ManagementBaseHandler):

    def get(self):
        with open(os.path.join(__location__, 'res/management.html'), 'r') as file:
            html = file.read()
            self.write(html)


class ManagementServiceRootRedirectHandler(ManagementBaseHandler):

    def initialize(self, management_root):
        self.management_root = management_root

    def get(self):
        self.redirect('/%s/' % self.management_root)


class ManagementServiceConfigHandler(ManagementConfigHandler):

    def initialize(self, http_server, service_id):
        self.http_server = http_server
        self.service_id = service_id

    def get(self):
        data = self.http_server.definition.orig_data['services'][self.service_id]
        _format = self.get_query_argument('format', default='json')
        if _format == 'yaml':
            self.set_header('Content-Type', 'application/x-yaml')
            self.write(yaml.dump(data, sort_keys=False))
        else:
            self.write(data)

    def post(self):
        body = _decoder(self.request.body)
        try:
            orig_data = yaml.safe_load(body)
        except json.JSONDecodeError as e:
            self.set_status(400)
            self.write('JSON/YAML decode error:\n%s' % str(e))
            return
        data = copy.deepcopy(orig_data)

        try:
            jsonschema.validate(
                instance=data,
                schema=self.http_server.definition.schema['definitions']['service_ref']['properties']
            )
        except jsonschema.exceptions.ValidationError as e:
            self.set_status(400)
            self.write('JSON schema validation error:\n%s' % str(e))
            return

        try:
            global_performance_profile = None
            if 'globals' in self.http_server.definition.data:
                global_performance_profile = self.http_server.definition.data['globals'].get('performanceProfile', None)
            data = mockintosh.Definition.analyze_service(
                data,
                self.http_server.definition.template_engine,
                performance_profiles=self.http_server.definition.data['performanceProfiles'],
                global_performance_profile=global_performance_profile
            )
            data['internalServiceId'] = self.service_id
            self.update_service(data, self.service_id)
        except Exception as e:
            self.set_status(400)
            self.write('Something bad happened:\n%s' % str(e))
            return

        self.http_server.stats.reset()

        self.set_status(204)


class ManagementServiceStatsHandler(ManagementBaseHandler):

    def initialize(self, stats, service_id):
        self.stats = stats
        self.service_id = service_id

    def get(self):
        self.write(self.stats.services[self.service_id].json())

    def delete(self):
        self.stats.services[self.service_id].reset()
        self.set_status(204)


class ManagementServiceResetIteratorsHandler(ManagementBaseHandler):

    def initialize(self, http_server, service_id):
        self.http_server = http_server
        self.service_id = service_id

    def post(self):
        app = self.http_server._apps.apps[self.service_id]
        _reset_iterators(app)
        self.set_status(204)


class ManagementServiceUnhandledHandler(ManagementUnhandledHandler):

    def initialize(self, http_server, service_id):
        self.http_server = http_server
        self.service_id = service_id

    def get(self):
        data = {
            'services': []
        }

        service = self.http_server.definition.orig_data['services'][self.service_id]
        data['services'].append(dict((k, service[k]) for k in UNHANDLED_SERVICE_KEYS if k in service))
        data['services'][0]['endpoints'] = self.build_unhandled_requests(self.service_id)

        try:
            jsonschema.validate(
                instance=data,
                schema=self.http_server.definition.schema['definitions']['service_ref']['properties']
            )
        except jsonschema.exceptions.ValidationError as e:
            self.set_status(400)
            self.write('JSON schema validation error:\n%s' % str(e))
            return

        self.write(data)


class ManagementServiceOasHandler(ManagementOasHandler):

    def initialize(self, http_server, service_id):
        self.http_server = http_server
        self.service_id = service_id

    def get(self):
        self.write(self.build_oas(self.service_id))


class UnhandledData:
    def __init__(self):
        self.requests = []
