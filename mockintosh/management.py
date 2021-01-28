#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains the handlers for the management API.
"""

import os
import json
import copy
from typing import (
    Union
)

import jsonschema
import tornado.web
from tornado.util import unicode_type
from tornado.escape import utf8

import mockintosh
from mockintosh.handlers import GenericHandler
from mockintosh.methods import _decoder

POST_CONFIG_RESTRICTED_FIELDS = ('port', 'hostname', 'ssl', 'sslCertFile', 'sslKeyFile')

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
        self.write(self.http_server.definition.orig_data)

    def post(self):
        body = _decoder(self.request.body)
        try:
            orig_data = json.loads(body)
        except json.JSONDecodeError as e:
            self.set_status(400)
            self.write('JSON decode error:\n%s' % str(e))
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

        for i in range(len(self.http_server.definition.data['services'])):
            service = self.http_server.definition.data['services'][i]
            if 'endpoints' not in service or not service['endpoints']:
                continue
            data['services'].append(self.build_unhandled_requests(i))

        self.write(data)

    def build_unhandled_requests(self, service_id):
        data = {
            'hint': self.http_server.stats.services[service_id].hint,
            'unhandledRequests': []
        }

        for request in self.http_server.unhandled_data.requests[service_id].values():
            config_template = {}

            # Method
            config_template['method'] = request.method

            # Path
            config_template['path'] = request.path

            # Headers
            for key, value in request.headers._dict.items():
                if 'headers' not in config_template:
                    config_template['headers'] = {}
                config_template['headers'][key] = value

            # Query String
            for key, value in request.query_arguments.items():
                if 'queryString' not in config_template:
                    config_template['queryString'] = {}
                config_template['queryString'][key] = _decoder(value[0])
            config_template['response'] = ''
            data['unhandledRequests'].append(config_template)

        return data


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
        self.write(self.http_server.definition.orig_data['services'][self.service_id])

    def post(self):
        body = _decoder(self.request.body)
        try:
            orig_data = json.loads(body)
        except json.JSONDecodeError as e:
            self.set_status(400)
            self.write('JSON decode error:\n%s' % str(e))
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
            data = mockintosh.Definition.analyze_service(data, self.http_server.definition.template_engine)
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
        self.write(self.build_unhandled_requests(self.service_id))


class UnhandledData:
    def __init__(self):
        self.requests = []
