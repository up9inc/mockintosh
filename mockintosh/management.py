#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains the handlers for the management API.
"""

import os
import json
import copy

import jsonschema
import tornado.web

import mockintosh
from mockintosh.handlers import GenericHandler
from mockintosh.methods import _decoder

POST_CONFIG_RESTRICTED_FIELDS = ('port', 'hostname', 'ssl', 'sslCertFile', 'sslKeyFile')

__location__ = os.path.abspath(os.path.dirname(__file__))


class ManagementRootHandler(tornado.web.RequestHandler):

    def get(self):
        with open(os.path.join(__location__, 'res/management.html'), 'r') as file:
            html = file.read()
            self.write(html)


class ManagementConfigHandler(tornado.web.RequestHandler):

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

        self.write('OK')
        self.finish()

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


class ManagementStatsHandler(tornado.web.RequestHandler):

    def initialize(self, stats):
        self.stats = stats

    def get(self):
        self.write(self.stats.json())

    def delete(self):
        self.stats.reset()
        self.write('OK')


class ManagementServiceRootHandler(tornado.web.RequestHandler):

    def get(self):
        with open(os.path.join(__location__, 'res/management.html'), 'r') as file:
            html = file.read()
            self.write(html)


class ManagementServiceRootRedirectHandler(tornado.web.RequestHandler):

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

        self.write('OK')
        self.finish()
