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

from mockintosh.config import ConfigService, ConfigExternalFilePath
from mockintosh.definition import Definition
from mockintosh.exceptions import CertificateLoadingError
from mockintosh.handlers import GenericHandler
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
from mockintosh.services.asynchronous._looping import run_loops as async_run_loops, stop_loops as async_stop_loops
from mockintosh.services.http import (
    HttpService,
    HttpPath,
    HttpAlternative
)
from mockintosh.stats import Stats

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

    @abstractmethod
    def stop(self):
        raise NotImplementedError


class TornadoImpl(Impl):
    def __init__(self) -> None:
        super().__init__()
        self.ioloop = None
        self.servers = []

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

        self.servers.append(server)
        return server

    def serve(self) -> None:
        self.ioloop = tornado.ioloop.IOLoop.current()
        logging.debug("Starting ioloop: %s", self.ioloop)
        try:
            self.ioloop.start()
        except KeyboardInterrupt:
            logging.debug("Shutdown: %s", traceback.format_exc())

        logging.debug("IOLoop has completed")

    def stop(self):
        logging.debug("Stopping servers...")
        for server in self.servers:
            logging.debug("Stopping: %s", server)
            self.ioloop.add_callback(server.close_all_connections)
            server.stop()

        logging.debug("Stopping IOLoop...")
        logging.debug("%s", self.ioloop)
        self.ioloop.add_callback_from_signal(self.ioloop.stop)

        logging.debug("TornadoImpl is stopped")


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

        for service in HttpService.services:
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
                    key_file = self.resolve_cert_path(service.ssl_key_file)
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

    def prepare_app(self, service: HttpService) -> Tuple[List[HttpPath], str]:
        http_path_list = []
        if service.endpoints:
            http_path_list = HttpServer.merge_alternatives(service, self.definition.stats)

        management_root = service.management_root

        return http_path_list, management_root

    def load_service(self, service: HttpService, rules: list, ssl: bool, ssl_options: dict) -> bool:
        if not self.load_guard(service):
            return False

        protocol = 'https' if ssl else 'http'
        http_path_list, management_root = self.prepare_app(service)
        app = self.make_app(service, http_path_list, self.globals, debug=self.debug, management_root=management_root)
        self._apps.apps[service.internal_http_service_id] = app
        address_str = self.address if self.address else 'localhost'
        self._apps.listeners[service.internal_http_service_id] = _Listener(
            service.hostname,
            service.port,
            address_str
        )

        if service.hostname is None:
            server = self.impl.get_server(app, ssl, ssl_options)
            logging.debug('Will listen: %s:%d', address_str, service.port)
            server.listen(service.port, address=self.address)
            self.services_log.append('Serving at %s://%s:%s%s' % (
                protocol,
                address_str,
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
        self._apps.apps = len(HttpService.services) * [None]
        self._apps.listeners = len(HttpService.services) * [None]

        for service in self.definition.services:
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
                logging.debug('Listening on port: %s:%d', self.address, service.port)
                server.listen(services[0].port, address=self.address)

        self.load_management_api()

    @staticmethod
    def merge_alternatives(service: HttpService, stats: Stats) -> List[HttpPath]:
        new_endpoints = {}
        i = 0
        for i, endpoint in enumerate(service.endpoints):
            hint = '%s %s%s' % (
                endpoint.method,
                endpoint.orig_path,
                ' - %s' % endpoint.id if endpoint.id is not None else ''
            )
            stats.services[service.internal_service_id].add_endpoint(hint)
            identifier = endpoint.path
            alternative = HttpAlternative(
                endpoint.id,
                endpoint.orig_path,
                endpoint.params,
                endpoint.context,
                endpoint.performance_profile,
                endpoint.query_string,
                endpoint.headers,
                endpoint.body,
                endpoint.dataset,
                endpoint.response,
                endpoint.multi_responses_looped,
                endpoint.dataset_looped,
                i
            )

            if identifier not in new_endpoints:
                new_endpoints[identifier] = HttpPath()
                new_endpoints[identifier].path = endpoint.path
                new_endpoints[identifier].priority = endpoint.priority
            if endpoint.method not in new_endpoints[identifier].methods:
                new_endpoints[identifier].methods[endpoint.method] = [alternative]
            else:
                new_endpoints[identifier].methods[endpoint.method].append(alternative)

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
        async_run_loops()
        self.impl.serve()

    def make_app(
            self,
            service: dict,
            http_path_list: List[HttpPath],
            _globals: dict,
            debug: bool = False,
            management_root: Union[str, None] = None
    ) -> tornado.web.Application:
        endpoint_handlers = []
        http_path_list = sorted(http_path_list, key=lambda x: x.priority, reverse=False)

        path_methods = []

        for http_path in http_path_list:
            path_methods.append((http_path.path, http_path.methods))

        endpoint_handlers.append(
            (
                r'.*',
                GenericHandler,
                dict(
                    http_server=self,
                    config_dir=self.definition.source_dir,
                    service_id=service.internal_service_id,
                    path_methods=path_methods,
                    _globals=_globals,
                    definition_engine=self.definition.template_engine,
                    rendering_queue=self.definition.rendering_queue,
                    interceptors=self.interceptors,
                    unhandled_data=None,
                    fallback_to=service.fallback_to,
                    tags=self.tags
                )
            )
        )

        HttpServer.log_path_methods(path_methods)

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
    def log_path_methods(path_methods: list) -> None:
        for _path, methods in path_methods:
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
        logging.debug("Listening on port %s:%s", self.address, config_management.port)
        server = self.impl.get_server(app, ssl, ssl_options)
        server.listen(config_management.port, address=self.address)
        self.services_log.append('Serving management UI+API at %s://%s:%s' % (
            protocol,
            self.address if self.address else 'localhost',
            config_management.port
        ))

    def clear_lists(self):
        HttpService.services = []
        ConfigService.services = []
        ConfigExternalFilePath.files = []

    def stop(self):
        logging.info("Stopping server...")
        self.impl.stop()
        logging.debug("Stoppping async actor threads")
        async_stop_loops()
        self.clear_lists()
        logging.debug("Done shutdown")
