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
from os import path
from typing import (
    Union,
    Tuple,
    List
)

import tornado.ioloop
import tornado.web
from tornado.routing import Rule, RuleRouter, HostMatches

from mockintosh.exceptions import CertificateLoadingError
from mockintosh.definition import Definition
from mockintosh.handlers import GenericHandler
from mockintosh.http import (
    HttpService,
    HttpAlternative
)
from mockintosh.management import (
    ManagementRootHandler,
    ManagementConfigHandler,
    ManagementStatsHandler,
    ManagementLogsHandler,
    ManagementResetIteratorsHandler,
    ManagementUnhandledHandler,
    ManagementOasHandler,
    ManagementTagHandler,
    ManagementAsyncHandler,
    ManagementAsyncProducersHandler,
    ManagementAsyncConsumersHandler,
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
from mockintosh import kafka


__location__ = path.abspath(path.dirname(__file__))


class Impl:
    @abstractmethod
    def get_server(
        self,
        router: Union[RuleRouter, tornado.web.Application],
        is_ssl: bool,
        ssl_options: dict
    ):
        raise NotImplementedError

    @abstractmethod
    def serve(self):
        raise NotImplementedError


class TornadoImpl(Impl):
    def get_server(
        self,
        router: Union[RuleRouter, tornado.web.Application],
        is_ssl: bool,
        ssl_options: dict
    ) -> tornado.web.HTTPServer:
        if is_ssl:
            server = tornado.web.HTTPServer(router, ssl_options=ssl_options)
        else:
            server = tornado.web.HTTPServer(router)

        return server

    def serve(self) -> None:
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

    def __init__(
        self,
        definition: Definition,
        impl: Impl,
        debug: bool = False,
        interceptors: tuple = (),
        address: str = '',
        services_list: tuple = (),
        tags: list = []
    ):
        self.definition = definition
        self.impl = impl
        self.address = address
        self.globals = self.definition.data['globals'] if 'globals' in self.definition.data else {}
        self.debug = debug
        self.interceptors = interceptors
        self.services_list = services_list
        self.services_log = []
        self._apps = _Apps()
        self.unhandled_data = UnhandledData()
        self.tags = tags
        self.load()

    def map_ports(self) -> OrderedDict:
        port_mapping = OrderedDict()

        for service in self.definition.services:
            if not isinstance(service, HttpService):
                continue

            port = str(service.port)
            if port not in port_mapping:
                port_mapping[port] = []
            port_mapping[port].append(service)

        return port_mapping

    def resolve_ssl(self, services: list) -> Tuple[bool, dict]:
        ssl = False
        cert_file = path.join(__location__, 'ssl', 'cert.pem')
        key_file = path.join(__location__, 'ssl', 'key.pem')
        for service in services:
            ssl = service.ssl
            if ssl:
                if service.ssl_cert_file is not None:
                    cert_file = self.resolve_cert_path(service.ssl_cert_file)
                if service.ssl_key_file is not None:
                    key_file = self.resolve_cert_path(service. ssl_key_file)
                break
        ssl_options = {
            "certfile": cert_file,
            "keyfile": key_file,
        }
        return ssl, ssl_options

    def load_guard(self, service: HttpService) -> bool:
        if self.services_list:
            if service.name is not None:
                if service.name not in self.services_list:
                    return False
            else:  # pragma: no cover
                return False  # https://github.com/nedbat/coveragepy/issues/198
        return True

    def prepare_app(self, service: HttpService) -> Tuple[List[HttpAlternative], str]:
        alternatives = []
        if service.endpoints:
            alternatives = HttpServer.merge_alternatives(service, self.definition.stats)

        management_root = service.management_root

        return alternatives, management_root

    def load_service(self, service: HttpService, rules: list, ssl: bool, ssl_options: dict) -> bool:
        if not self.load_guard(service):
            return False

        protocol = 'https' if ssl else 'http'
        alternatives, management_root = self.prepare_app(service)
        app = self.make_app(service, alternatives, self.globals, debug=self.debug, management_root=management_root)
        self._apps.apps[service.internal_service_id] = app
        self._apps.listeners[service.internal_service_id] = _Listener(
            service.hostname,
            service.port,
            self.address if self.address else 'localhost'
        )

        if service.hostname is None:
            server = self.impl.get_server(app, ssl, ssl_options)
            server.listen(service.port, address=self.address)
            logging.debug('Will listen port number: %d', service.port)
            self.services_log.append('Serving at %s://%s:%s%s' % (
                protocol,
                self.address if self.address else 'localhost',
                service.port,
                ' the mock for %r' % service.get_name_or_empty()
            ))
        else:
            rules.append(
                Rule(HostMatches(service.hostname), app)
            )

            logging.debug(
                'Registered hostname and port: %s://%s:%d',
                protocol,
                service.hostname,
                service.port
            )
            self.services_log.append('Serving at %s://%s:%s%s' % (
                protocol,
                service.hostname,
                service.port,
                ' the mock for %r' % service.get_name_or_empty()
            ))

        if service.name is not None:
            logging.debug('Finished registering: %s', service.name)

        return True

    def load(self) -> None:
        services = self.definition.services
        self._apps.apps = len(services) * [None]
        self._apps.listeners = len(services) * [None]
        for service in services:
            self.unhandled_data.requests.append({})

        port_mapping = self.map_ports()

        for port, services in port_mapping.items():
            ssl, ssl_options = self.resolve_ssl(services)

            rules = []
            for service in services:
                if not self.load_service(service, rules, ssl, ssl_options):
                    continue

            if rules:
                router = RuleRouter(rules)
                server = self.impl.get_server(router, ssl, ssl_options)
                server.listen(services[0].port, address=self.address)
                logging.debug('Will listen port number: %d', service.port)

        self.load_management_api()

    @staticmethod
    def merge_alternatives(service: HttpService, stats: Stats) -> List[HttpAlternative]:
        new_endpoints = {}
        i = 0
        for endpoint in service.endpoints:
            hint = '%s %s%s' % (
                endpoint.method,
                endpoint.orig_path,
                ' - %s' % ''
            )
            stats.services[service.internal_service_id].add_endpoint(hint)
            identifier = endpoint.path
            extracted_parts = {}
            for key in endpoint.__dict__.keys():
                if key in ('method', 'path', 'priority'):
                    continue
                extracted_parts[key] = getattr(endpoint, key)

            extracted_parts['internalEndpointId'] = i
            i += 1
            if 'id' not in extracted_parts:
                extracted_parts['id'] = None
            if 'counters' not in extracted_parts:
                extracted_parts['counters'] = {}

            if identifier not in new_endpoints:
                new_endpoints[identifier] = HttpAlternative()
                new_endpoints[identifier].path = endpoint.path
                new_endpoints[identifier].priority = endpoint.priority
            if endpoint.method not in new_endpoints[identifier].methods:
                new_endpoints[identifier].methods[endpoint.method] = [extracted_parts]
            else:
                new_endpoints[identifier].methods[endpoint.method].append(extracted_parts)

        return list(new_endpoints.values())

    def run(self) -> None:
        if 'unittest' in sys.modules.keys():
            import os
            import signal
            parent_pid = os.getppid()
            os.kill(parent_pid, signal.SIGALRM)

        for service_log in self.services_log:
            logging.info(service_log)

        logging.info('Mock server is ready!')
        stop = {'val': False}
        self.definition.add_stopper(stop)
        kafka.run_loops(self.definition, stop)
        self.impl.serve()

    def make_app(
        self,
        service: dict,
        alternatives: list,
        _globals: dict,
        debug: bool = False,
        management_root: str = None
    ) -> tornado.web.Application:
        endpoint_handlers = []
        alternatives = sorted(alternatives, key=lambda x: x.priority, reverse=False)

        merged_alternatives = []

        for alternative in alternatives:
            merged_alternatives.append((alternative.path, alternative.methods))

        unhandled_enabled = True if (management_root is not None or self.definition.config_root.management is not None) else False

        endpoint_handlers.append(
            (
                r'.*',
                GenericHandler,
                dict(
                    http_server=self,
                    config_dir=self.definition.source_dir,
                    service_id=service.internal_service_id,
                    alternatives=merged_alternatives,
                    _globals=_globals,
                    definition_engine=self.definition.template_engine,
                    rendering_queue=self.definition.rendering_queue,
                    interceptors=self.interceptors,
                    unhandled_data=self.unhandled_data if unhandled_enabled else None,
                    fallback_to=service.fallback_to,
                    tags=self.tags
                )
            )
        )

        HttpServer.log_merged_alternatives(merged_alternatives)

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
                        service_id=service.internal_service_id
                    )
                ),
                (
                    '/%s/stats' % management_root,
                    ManagementServiceStatsHandler,
                    dict(
                        stats=self.definition.stats,
                        service_id=service.internal_service_id
                    )
                ),
                (
                    '/%s/traffic-log' % management_root,
                    ManagementServiceLogsHandler,
                    dict(
                        logs=self.definition.logs,
                        service_id=service.internal_service_id
                    )
                ),
                (
                    '/%s/reset-iterators' % management_root,
                    ManagementServiceResetIteratorsHandler,
                    dict(
                        http_server=self,
                        service_id=service.internal_service_id
                    )
                ),
                (
                    '/%s/unhandled' % management_root,
                    ManagementServiceUnhandledHandler,
                    dict(
                        http_server=self,
                        service_id=service.internal_service_id
                    )
                ),
                (
                    '/%s/oas' % management_root,
                    ManagementServiceOasHandler,
                    dict(
                        http_server=self,
                        service_id=service.internal_service_id
                    )
                ),
                (
                    '/%s/tag' % management_root,
                    ManagementServiceTagHandler,
                    dict(
                        http_server=self,
                        service_id=service.internal_service_id
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
    def log_merged_alternatives(merged_alternatives: list) -> None:
        for _path, methods in merged_alternatives:
            for method, alternatives in methods.items():
                logging.debug('Registered endpoint: %s %s', method.upper(), _path)
                logging.debug('with alternatives:\n%s', alternatives)

    def resolve_cert_path(self, cert_path: str) -> str:
        relative_path = path.join(self.definition.source_dir, cert_path)
        relative_path = path.abspath(relative_path)
        if not path.isfile(relative_path):
            raise CertificateLoadingError('File not found on path `%s`' % cert_path)
        if not relative_path.startswith(self.definition.source_dir):
            raise CertificateLoadingError('Path `%s` is inaccessible!' % cert_path)

        return relative_path

    def load_management_api(self) -> None:
        if self.definition.config_root.management is None:
            return

        config_management = self.definition.config_root.management
        ssl, ssl_options = self.resolve_ssl([config_management])
        protocol = 'https' if ssl else 'http'

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
                    stats=self.definition.stats
                )
            ),
            (
                '/traffic-log',
                ManagementLogsHandler,
                dict(
                    logs=self.definition.logs
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
            ),
            (
                '/async',
                ManagementAsyncHandler,
                dict(
                    http_server=self
                )
            ),
            (
                '/async/producers/(.+)',
                ManagementAsyncProducersHandler,
                dict(
                    http_server=self
                )
            ),
            (
                '/async/consumers/(.+)',
                ManagementAsyncConsumersHandler,
                dict(
                    http_server=self
                )
            )
        ])
        server = self.impl.get_server(app, ssl, ssl_options)
        server.listen(config_management.port, address=self.address)
        self.services_log.append('Serving management API at %s://%s:%s' % (
            protocol,
            self.address if self.address else 'localhost',
            config_management.port
        ))
