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

from chupeta.handlers import GenericHandler


class HttpServer():
    def __init__(self, definition, debug=False):
        self.definition = definition
        self.debug = debug

    def run(self):
        port_mapping = {}
        for service in self.definition.data['services']:
            port = str(service['port'])
            if port not in port_mapping:
                port_mapping[port] = []
            port_mapping[port].append(service)

        for port, services in port_mapping.items():
            rules = []
            for service in services:
                app = self.make_app(service['endpoints'], self.debug)
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

        if 'unittest' in sys.modules.keys():
            import os
            import signal
            parent_pid = os.getppid()
            os.kill(parent_pid, signal.SIGALRM)

        logging.info('Mock server is ready!')
        tornado.ioloop.IOLoop.current().start()

    def make_app(self, endpoints, debug=False):
        endpoint_handlers = []
        endpoints = sorted(endpoints, key=lambda x: x['priority'], reverse=False)

        for endpoint in endpoints:
            if 'method' not in endpoint:
                endpoint['method'] = 'GET'

            endpoint_handlers.append(
                (
                    endpoint['path'],
                    GenericHandler,
                    dict(
                        method=endpoint['method'],
                        response=endpoint['response'],
                        params=endpoint['params']
                    )
                )
            )
            logging.info('Registered endpoint: %s %s' % (endpoint['method'].upper(), endpoint['path']))
            logging.debug('with response:\n%s' % endpoint['response'])
        return tornado.web.Application(endpoint_handlers, debug=debug)
