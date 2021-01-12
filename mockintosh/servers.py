#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that server classes.
"""

import logging
import sys
from abc import abstractmethod
from collections import OrderedDict
from os import path

import tornado.ioloop
import tornado.web
from tornado.routing import Rule, RuleRouter, HostMatches

from mockintosh.exceptions import CertificateLoadingError
from mockintosh.handlers import GenericHandler
from mockintosh.overrides import Application

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


class HttpServer:

    def __init__(self, definition, impl: Impl, debug=False, interceptors=(), address='', services_list=[]):
        self.definition = definition
        self.impl = impl
        self.address = address
        self.globals = self.definition.data['globals'] if 'globals' in self.definition.data else {}
        self.debug = debug
        self.interceptors = interceptors
        self.services_list = services_list
        self.services_log = []
        self.load()

    def load(self):
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
                    if 'name' in service:
                        if service['name'] not in self.services_list:
                            continue
                    else:
                        continue

                endpoints = []
                if 'endpoints' in service:
                    endpoints = self.merge_alternatives(service['endpoints'])
                app = self.make_app(endpoints, self.globals, debug=self.debug)
                if 'hostname' not in service:
                    server = self.impl.get_server(app, ssl, ssl_options)
                    server.listen(service['port'], address=self.address)
                    logging.debug('Will listen port number: %d' % service['port'])
                    self.services_log.append('Serving at %s://%s:%s%s' % (
                        protocol,
                        'localhost',
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

    def merge_alternatives(self, endpoints):
        new_endpoints = {}
        for endpoint in endpoints:
            if 'method' not in endpoint:
                endpoint['method'] = 'GET'
            identifier = endpoint['path']
            extracted_parts = {}
            for key in endpoint:
                if key in ('method', 'path', 'priority'):
                    continue
                extracted_parts[key] = endpoint[key]
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

    def make_app(self, endpoints, _globals, debug=False):
        endpoint_handlers = []
        endpoints = sorted(endpoints, key=lambda x: x['priority'], reverse=False)

        for endpoint in endpoints:
            endpoint_handlers.append(
                (
                    endpoint['path'],
                    GenericHandler,
                    dict(
                        config_dir=self.definition.source_dir,
                        methods=endpoint['methods'],
                        _globals=_globals,
                        definition_engine=self.definition.template_engine,
                        interceptors=self.interceptors
                    )
                )
            )
            for method, alternatives in endpoint['methods'].items():
                logging.debug('Registered endpoint: %s %s' % (method.upper(), endpoint['path']))
                logging.debug('with alternatives:\n%s' % alternatives)
        return Application(endpoint_handlers, debug=debug, interceptors=self.interceptors)

    def resolve_cert_path(self, cert_path):
        relative_path = path.join(self.definition.source_dir, cert_path)
        if not path.isfile(relative_path):
            raise CertificateLoadingError('File not found on path `%s`' % cert_path)
        relative_path = path.abspath(relative_path)
        if not relative_path.startswith(self.definition.source_dir):
            raise CertificateLoadingError('Path `%s` is inaccessible!' % cert_path)

        return relative_path
