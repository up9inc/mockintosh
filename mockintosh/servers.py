#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains server classes.
"""

import logging
import sys
from abc import abstractmethod
from os import path, environ

import tornado.ioloop
import tornado.web
from tornado.routing import Rule, RuleRouter, HostMatches

from mockintosh.exceptions import CertificateLoadingError
from mockintosh.handlers import GenericHandler
from mockintosh.management import (
    ManagementRootHandler,
    ManagementConfigHandler,
    ManagementStatsHandler,
    ManagementServiceRootHandler,
    ManagementServiceRootRedirectHandler,
    ManagementServiceConfigHandler,
    ManagementServiceStatsHandler
)
from mockintosh.overrides import Application
from mockintosh.stats import Stats

stats = Stats()

__location__ = path.abspath(path.dirname(__file__))


class Impl:
    @abstractmethod
    def get_server(self, app, is_ssl, ssl_options):
        pass

    @abstractmethod
    def serve(self):
        pass


class TornadoImpl(Impl):
    def get_server(self, router, is_ssl, ssl_options):
        if is_ssl:
            server = tornado.web.HTTPServer(router, ssl_options=ssl_options)
        else:
            server = tornado.web.HTTPServer(router)

        return server

    def serve(self):
        tornado.ioloop.IOLoop.current().start()


class _Apps:
    def __init__(self):
        self.apps = []


class HttpServer:

    def __init__(self, definition, impl: Impl, debug=False, interceptors=(), address='', services_list=()):
        self.definition = definition
        self.impl = impl
        self.address = address
        self.globals = self.definition.data['globals'] if 'globals' in self.definition.data else {}
        self.debug = debug
        self.interceptors = interceptors
        self.services_list = services_list
        self.services_log = []
        self._apps = _Apps()
        self.stats = stats
        self.load()

    def load(self):
        port_override = environ.get('MOCKINTOSH_FORCE_PORT', None)

        services = self.definition.data['services']
        service_id_counter = 0
        for service in services:
            service['internalServiceId'] = service_id_counter
            service_id_counter += 1

        cert_file = path.join(__location__, 'ssl', 'cert.pem')
        key_file = path.join(__location__, 'ssl', 'key.pem')

        for service in services:
            self.stats.add_service(
                '%s:%s%s' % (
                    service['hostname'] if 'hostname' in service else (
                        self.address if self.address else 'localhost'
                    ),
                    service['port'],
                    ' - %s' % service['name'] if 'name' in service else ''
                )
            )
            ssl = service.get('ssl', False)
            if ssl:
                if 'sslCertFile' in service:
                    cert_file = self.resolve_cert_path(service['sslCertFile'])
                if 'sslKeyFile' in service:
                    key_file = self.resolve_cert_path(service['sslKeyFile'])

            protocol = 'https' if ssl else 'http'
            ssl_options = {
                "certfile": cert_file,
                "keyfile": key_file,
            }

            if self.services_list:
                if port_override is not None:
                    service['port'] = int(port_override)

                if 'name' in service:
                    if service['name'] not in self.services_list:
                        continue
                else:
                    continue

            endpoints = []
            if 'endpoints' in service:
                endpoints = HttpServer.merge_alternatives(service, self.stats)

            management_root = None
            if 'managementRoot' in service:
                management_root = service['managementRoot']

            app = self.make_app(service, endpoints, self.globals, debug=self.debug, management_root=management_root)
            self._apps.apps.append(app)

            if 'hostname' not in service:
                server = self.impl.get_server(app, ssl, ssl_options)
                server.listen(service['port'], address=self.address)
                logging.debug('Will listen port number: %d' % service['port'])
                self.services_log.append('Serving at %s://%s:%s%s' % (
                    protocol,
                    self.address if self.address else 'localhost',
                    service['port'],
                    ' the mock for %r' % service['name'] if 'name' in service else ''
                ))
            else:
                rules = [Rule(HostMatches(service['hostname']), app)]

                logging.debug('Registered hostname and port: %s://%s:%d' % (
                    protocol,
                    service['hostname'],
                    service['port']
                ))
                self.services_log.append('Serving at %s://%s:%s%s' % (
                    protocol,
                    service['hostname'],
                    service['port'],
                    ' the mock for %r' % service['name'] if 'name' in service else ''
                ))

                router = RuleRouter(rules)
                server = self.impl.get_server(router, ssl, ssl_options)
                server.listen(service['port'], address=self.address)
                logging.debug('Will listen port number: %d' % service['port'])

            if 'name' in service:
                logging.debug('Finished registering: %s' % service['name'])

        self.load_management_api()

    @staticmethod
    def merge_alternatives(service, stats):
        new_endpoints = {}
        i = 0
        for endpoint in service['endpoints']:
            if 'method' not in endpoint:
                endpoint['method'] = 'GET'
            stats.services[service['internalServiceId']].add_endpoint(
                '%s %s%s' % (
                    endpoint['method'].upper(),
                    endpoint['path'],
                    ' - %s' % endpoint['id'] if 'id' in endpoint else ''
                )
            )
            identifier = endpoint['path']
            extracted_parts = {}
            for key in endpoint:
                if key in ('method', 'path', 'priority'):
                    continue
                extracted_parts[key] = endpoint[key]

            extracted_parts['internalEndpointId'] = i
            i += 1
            if 'id' not in extracted_parts:
                extracted_parts['id'] = None
            if 'counters' not in extracted_parts:
                extracted_parts['counters'] = {}

            if identifier not in new_endpoints:
                new_endpoints[identifier] = {}
                new_endpoints[identifier]['path'] = endpoint['path']
                new_endpoints[identifier]['priority'] = endpoint['priority']
                new_endpoints[identifier]['methods'] = {}
            if endpoint['method'] not in new_endpoints[identifier]['methods']:
                new_endpoints[identifier]['methods'][endpoint['method']] = [extracted_parts]
            else:
                new_endpoints[identifier]['methods'][endpoint['method']].append(extracted_parts)
        return new_endpoints.values()

    def run(self):
        if 'unittest' in sys.modules.keys():
            import os
            import signal
            parent_pid = os.getppid()
            os.kill(parent_pid, signal.SIGALRM)

        for service_log in self.services_log:
            logging.info(service_log)

        logging.info('Mock server is ready!')
        self.impl.serve()

    def make_app(self, service, endpoints, _globals, debug=False, management_root=None):
        endpoint_handlers = []
        endpoints = sorted(endpoints, key=lambda x: x['priority'], reverse=False)

        merged_endpoints = []

        for endpoint in endpoints:
            merged_endpoints.append((endpoint['path'], endpoint['methods']))

        endpoint_handlers.append(
            (
                r'.*',
                GenericHandler,
                dict(
                    config_dir=self.definition.source_dir,
                    service_id=service['internalServiceId'],
                    endpoints=merged_endpoints,
                    _globals=_globals,
                    definition_engine=self.definition.template_engine,
                    interceptors=self.interceptors,
                    stats=self.stats
                )
            )
        )

        HttpServer.log_merged_endpoints(merged_endpoints)

        if management_root is not None:
            endpoint_handlers = [
                (
                    '/%s/' % management_root,
                    ManagementServiceRootHandler,
                    dict()
                ),
                (
                    '/%s' % management_root,
                    ManagementServiceRootRedirectHandler,
                    dict(
                        management_root=management_root
                    )
                ),
                (
                    '/%s/config' % management_root,
                    ManagementServiceConfigHandler,
                    dict(
                        http_server=self,
                        service_id=service['internalServiceId']
                    )
                ),
                (
                    '/%s/stats' % management_root,
                    ManagementServiceStatsHandler,
                    dict(
                        stats=stats,
                        service_id=service['internalServiceId']
                    )
                )
            ] + endpoint_handlers

        return Application(endpoint_handlers, debug=debug, interceptors=self.interceptors)

    @staticmethod
    def log_merged_endpoints(merged_endpoints):
        for _path, methods in merged_endpoints:
            for method, alternatives in methods.items():
                logging.debug('Registered endpoint: %s %s' % (method.upper(), _path))
                logging.debug('with alternatives:\n%s' % alternatives)

    def resolve_cert_path(self, cert_path):
        relative_path = path.join(self.definition.source_dir, cert_path)
        if not path.isfile(relative_path):
            raise CertificateLoadingError('File not found on path `%s`' % cert_path)
        relative_path = path.abspath(relative_path)
        if not relative_path.startswith(self.definition.source_dir):
            raise CertificateLoadingError('Path `%s` is inaccessible!' % cert_path)

        return relative_path

    def load_management_api(self):
        if 'management' not in self.definition.data:
            return

        management_config = self.definition.data['management']

        cert_file = path.join(__location__, 'ssl', 'cert.pem')
        key_file = path.join(__location__, 'ssl', 'key.pem')
        ssl = management_config.get('ssl', False)
        if ssl:
            if 'sslCertFile' in management_config:
                cert_file = self.resolve_cert_path(management_config['sslCertFile'])
            if 'sslKeyFile' in management_config:
                key_file = self.resolve_cert_path(management_config['sslKeyFile'])

        protocol = 'https' if ssl else 'http'
        ssl_options = {
            "certfile": cert_file,
            "keyfile": key_file,
        }

        if 'port' in management_config:
            app = tornado.web.Application([
                (
                    '/',
                    ManagementRootHandler,
                    dict()
                ),
                (
                    '/config',
                    ManagementConfigHandler,
                    dict(
                        http_server=self
                    )
                ),
                (
                    '/stats',
                    ManagementStatsHandler,
                    dict(
                        stats=stats
                    )
                )
            ])
            server = self.impl.get_server(app, ssl, ssl_options)
            server.listen(management_config['port'], address=self.address)
            self.services_log.append('Serving management API at %s://%s:%s' % (
                protocol,
                self.address if self.address else 'localhost',
                management_config['port']
            ))
