#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that server classes.
"""

import sys
import logging

import tornado.ioloop
import tornado.web
from tornado.routing import Rule, RuleRouter, HostMatches

from mockintosh.handlers import GenericHandler
from mockintosh.overrides import Application


class HttpServer():

    def __init__(self, definition, debug=False, interceptors=()):
        self.definition = definition
        self.globals = self.definition.data['globals'] if 'globals' in self.definition.data else {}
        self.debug = debug
        self.interceptors = interceptors
        self.load()

    def load(self):
        port_mapping = {}
        for service in self.definition.data['services']:
            port = str(service['port'])
            if port not in port_mapping:
                port_mapping[port] = []
            port_mapping[port].append(service)

        for port, services in port_mapping.items():
            rules = []
            for service in services:
                endpoints = []
                if 'endpoints' in service:
                    endpoints = self.merge_alternatives(service['endpoints'])
                app = self.make_app(endpoints, self.globals, self.debug)
                if 'hostname' not in service:
                    app.listen(service['port'])
                    logging.info('Will listen port number: %d' % service['port'])
                else:
                    rules.append(
                        Rule(HostMatches(service['hostname']), app)
                    )

                    logging.info('Registered hostname and port: %s://%s:%d' % (
                        'http',
                        service['hostname'],
                        service['port']
                    ))
                logging.info('Finished registering: %s' % service['comment'])

            if rules:
                router = RuleRouter(rules)
                server = tornado.web.HTTPServer(router)
                server.listen(services[0]['port'])
                logging.info('Will listen port number: %d' % service['port'])

    def merge_alternatives(self, endpoints):
        new_endpoints = {}
        for endpoint in endpoints:
            if 'method' not in endpoint:
                endpoint['method'] = 'GET'
            identifier = '%s %s' % (endpoint['method'], endpoint['path'])
            extracted_parts = {}
            for key in endpoint:
                if key in ('method', 'path', 'priority'):
                    continue
                extracted_parts[key] = endpoint[key]
                if 'id' not in extracted_parts:
                    extracted_parts['id'] = None
            if identifier in new_endpoints:
                new_endpoints[identifier]['alternatives'].append(extracted_parts)
            else:
                new_endpoints[identifier] = {}
                new_endpoints[identifier]['method'] = endpoint['method']
                new_endpoints[identifier]['path'] = endpoint['path']
                new_endpoints[identifier]['priority'] = endpoint['priority']
                new_endpoints[identifier]['alternatives'] = [extracted_parts]
        return new_endpoints.values()

    def run(self):
        if 'unittest' in sys.modules.keys():
            import os
            import signal
            parent_pid = os.getppid()
            os.kill(parent_pid, signal.SIGALRM)

        logging.info('Mock server is ready!')
        tornado.ioloop.IOLoop.current().start()

    def make_app(self, endpoints, _globals, debug=False):
        endpoint_handlers = []
        endpoints = sorted(endpoints, key=lambda x: x['priority'], reverse=False)

        for endpoint in endpoints:
            endpoint_handlers.append(
                (
                    endpoint['path'],
                    GenericHandler,
                    dict(
                        method=endpoint['method'],
                        alternatives=endpoint['alternatives'],
                        _globals=_globals,
                        definition_engine=self.definition.template_engine,
                        interceptors=self.interceptors
                    )
                )
            )
            logging.info('Registered endpoint: %s %s' % (endpoint['method'].upper(), endpoint['path']))
            logging.debug('with alternatives:\n%s' % endpoint['alternatives'])
        return Application(endpoint_handlers, debug=debug, interceptors=self.interceptors)
