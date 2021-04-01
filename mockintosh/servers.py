#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains server classes.
"""

import logging
import sys
import traceback
from abc import abstractmethod
from collections import OrderedDict
from os import path, environ
from typing import Union

import tornado.ioloop
import tornado.web
from tornado.routing import Rule, RuleRouter, HostMatches

from mockintosh.exceptions import CertificateLoadingError
from mockintosh.handlers import GenericHandler
from mockintosh.logs import Logs
from mockintosh.management import (
    ManagementRootHandler,
    ManagementConfigHandler,
    ManagementStatsHandler,
    ManagementLogsHandler,
    ManagementResetIteratorsHandler,
    ManagementUnhandledHandler,
    ManagementOasHandler,
    ManagementTagHandler,
    ManagementResourcesHandler,
    ManagementServiceRootHandler,
    ManagementServiceRootRedirectHandler,
    ManagementServiceConfigHandler,
    ManagementServiceStatsHandler,
    ManagementServiceLogsHandler,
    ManagementServiceResetIteratorsHandler,
    ManagementServiceUnhandledHandler,
    ManagementServiceOasHandler,
    ManagementServiceTagHandler,
    UnhandledData
)
from mockintosh.stats import Stats

stats = Stats()
logs = Logs()

__location__ = path.abspath(path.dirname(__file__))


class Impl:
    @abstractmethod
    def get_server(self, app, is_ssl, ssl_options):
        raise NotImplementedError

    @abstractmethod
    def serve(self):
        raise NotImplementedError


class TornadoImpl(Impl):
    def get_server(self, router, is_ssl, ssl_options):
        if is_ssl:
            server = tornado.web.HTTPServer(router, ssl_options=ssl_options)
        else:
            server = tornado.web.HTTPServer(router)

        return server

    def serve(self):
        try:
            tornado.ioloop.IOLoop.current().start()
        except KeyboardInterrupt:
            logging.debug("Shutdown: %s", traceback.format_exc())


class _Listener:
    def __init__(self, hostname: Union[str, None], port: int, address: Union[str, None]):
        self.hostname = hostname
        self.port = port
        self.address = address


class _Apps:
    def __init__(self):
        self.apps = []
        self.listeners = []


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
        self.logs = logs
        self.unhandled_data = UnhandledData()
        self.load()

    def load(self):
        port_override = environ.get('MOCKINTOSH_FORCE_PORT', None)

        services = self.definition.data['services']
        service_id_counter = 0
        for service in services:
            service['internalServiceId'] = service_id_counter
            service_id_counter += 1

            self.unhandled_data.requests.append({})
            hint = '%s:%s%s' % (
                service['hostname'] if 'hostname' in service else (
                    self.address if self.address else 'localhost'
                ),
                service['port'],
                ' - %s' % service['name'] if 'name' in service else ''
            )
            self.stats.add_service(hint)
            self.logs.add_service(service['name'] if 'name' in service else '')

        port_mapping = OrderedDict()
        for service in self.definition.data['services']:
            port = str(service['port'])
            if port not in port_mapping:
                port_mapping[port] = []
            port_mapping[port].append(service)

        for port, services in port_mapping.items():
            rules = []
            ssl = False
            cert_file = path.join(__location__, 'ssl', 'cert.pem')
            key_file = path.join(__location__, 'ssl', 'key.pem')
            for service in services:
                ssl = service.get('ssl', False)
                if ssl:
                    if 'sslCertFile' in service:
                        cert_file = self.resolve_cert_path(service['sslCertFile'])
                    if 'sslKeyFile' in service:
                        key_file = self.resolve_cert_path(service['sslKeyFile'])
                    break

            protocol = 'https' if ssl else 'http'
            ssl_options = {
                "certfile": cert_file,
                "keyfile": key_file,
            }

            for service in services:
                if self.services_list:
                    if port_override is not None:
                        service['port'] = int(port_override)

                    if 'name' in service:
                        if service['name'] not in self.services_list:
                            continue
                    else:  # pragma: no cover
                        continue  # https://github.com/nedbat/coveragepy/issues/198

                endpoints = []
                if 'endpoints' in service:
                    endpoints = HttpServer.merge_alternatives(service, self.stats, self.logs)

                management_root = None
                if 'managementRoot' in service:
                    management_root = service['managementRoot']

                app = self.make_app(service, endpoints, self.globals, debug=self.debug, management_root=management_root)
                self._apps.apps.append(app)
                self._apps.listeners.append(
                    _Listener(
                        service['hostname'] if 'hostname' in service else None,
                        service['port'],
                        self.address if self.address else 'localhost'
                    )
                )

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
                    rules.append(
                        Rule(HostMatches(service['hostname']), app)
                    )

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

                if 'name' in service:
                    logging.debug('Finished registering: %s' % service['name'])

            if rules:
                router = RuleRouter(rules)
                server = self.impl.get_server(router, ssl, ssl_options)
                server.listen(services[0]['port'], address=self.address)
                logging.debug('Will listen port number: %d' % service['port'])

        self.load_management_api()

    @staticmethod
    def merge_alternatives(service: dict, stats: Stats, logs: Logs):
        new_endpoints = {}
        i = 0
        for endpoint in service['endpoints']:
            if 'method' not in endpoint:
                endpoint['method'] = 'GET'
            hint = '%s %s%s' % (
                endpoint['method'].upper(),
                endpoint['internalOrigPath'],
                ' - %s' % endpoint['id'] if 'id' in endpoint else ''
            )
            stats.services[service['internalServiceId']].add_endpoint(hint)
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

        unhandled_enabled = True if (management_root is not None or 'management' in self.definition.data) else False

        endpoint_handlers.append(
            (
                r'.*',
                GenericHandler,
                dict(
                    http_server=self,
                    config_dir=self.definition.source_dir,
                    service_id=service['internalServiceId'],
                    endpoints=merged_endpoints,
                    _globals=_globals,
                    definition_engine=self.definition.template_engine,
                    interceptors=self.interceptors,
                    stats=self.stats,
                    logs=self.logs,
                    unhandled_data=self.unhandled_data if unhandled_enabled else None,
                    fallback_to=service['fallbackTo'] if 'fallbackTo' in service else None,
                    tag=None
                )
            )
        )

        HttpServer.log_merged_endpoints(merged_endpoints)

        if management_root is not None:
            if management_root and management_root[0] == '/':
                management_root = management_root[1:]
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
                ),
                (
                    '/%s/traffic-log' % management_root,
                    ManagementServiceLogsHandler,
                    dict(
                        logs=logs,
                        service_id=service['internalServiceId']
                    )
                ),
                (
                    '/%s/reset-iterators' % management_root,
                    ManagementServiceResetIteratorsHandler,
                    dict(
                        http_server=self,
                        service_id=service['internalServiceId']
                    )
                ),
                (
                    '/%s/unhandled' % management_root,
                    ManagementServiceUnhandledHandler,
                    dict(
                        http_server=self,
                        service_id=service['internalServiceId']
                    )
                ),
                (
                    '/%s/oas' % management_root,
                    ManagementServiceOasHandler,
                    dict(
                        http_server=self,
                        service_id=service['internalServiceId']
                    )
                ),
                (
                    '/%s/tag' % management_root,
                    ManagementServiceTagHandler,
                    dict(
                        http_server=self,
                        service_id=service['internalServiceId']
                    )
                ),
                (
                    '/%s/resources' % management_root,
                    ManagementResourcesHandler,
                    dict(
                        http_server=self
                    )
                )
            ] + endpoint_handlers

        return tornado.web.Application(endpoint_handlers, debug=debug, interceptors=self.interceptors)

    @staticmethod
    def log_merged_endpoints(merged_endpoints):
        for _path, methods in merged_endpoints:
            for method, alternatives in methods.items():
                logging.debug('Registered endpoint: %s %s' % (method.upper(), _path))
                logging.debug('with alternatives:\n%s' % alternatives)

    def resolve_cert_path(self, cert_path):
        relative_path = path.join(self.definition.source_dir, cert_path)
        relative_path = path.abspath(relative_path)
        if not path.isfile(relative_path):
            raise CertificateLoadingError('File not found on path `%s`' % cert_path)
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
                ),
                (
                    '/traffic-log',
                    ManagementLogsHandler,
                    dict(
                        logs=logs
                    )
                ),
                (
                    '/reset-iterators',
                    ManagementResetIteratorsHandler,
                    dict(
                        http_server=self
                    )
                ),
                (
                    '/unhandled',
                    ManagementUnhandledHandler,
                    dict(
                        http_server=self
                    )
                ),
                (
                    '/oas',
                    ManagementOasHandler,
                    dict(
                        http_server=self
                    )
                ),
                (
                    '/tag',
                    ManagementTagHandler,
                    dict(
                        http_server=self
                    )
                ),
                (
                    '/resources',
                    ManagementResourcesHandler,
                    dict(
                        http_server=self
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
