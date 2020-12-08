#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :platform: Unix
    :synopsis: the top-level module of Chupeta.
.. moduleauthor:: M. Mert Yildiran <mehmet@up9.com>
"""

import argparse
import inspect
import json
import logging
import sys
from os import path
from uuid import uuid4

import tornado.ioloop
import tornado.web
import yaml
from faker import Faker
from jinja2 import Template
from tornado.routing import Rule, RuleRouter, HostMatches  # PathMatches can be used too
from jsonschema import validate

from chupeta.exceptions import UnrecognizedConfigFileFormat
from chupeta import configs

__location__ = path.abspath(path.dirname(__file__))


class Definition():
    def __init__(self, source, schema):
        self.source = source
        self.compiled = None
        self.data = None
        self.valid_json = False
        self.valid_yaml = False
        self.schema = schema
        self._compile()
        self.load()
        self.validate()

    def add_globals(self, template):
        fake = Faker()
        template.globals['uuid'] = uuid4
        template.globals['fake'] = fake

    def _compile(self):
        source_text = None
        if self.source is None:
            source_text = configs.get_default()
        else:
            with open(self.source, 'r') as file:
                logging.info('Reading configuration file from path: %s' % self.source)
                source_text = file.read()
                logging.debug('Configuration text: %s' % source_text)
        logging.info('Parsing the configuration file...')
        template = Template(source_text)
        self.add_globals(template)
        self.compiled = template.render()

    def load(self):
        invalid_json_error_msg = None
        invalid_yaml_error_msg = None

        try:
            self.data = json.loads(self.compiled)
            self.valid_json = True
            logging.info('Configuration file is a valid JSON file.')
        except json.decoder.JSONDecodeError as e:
            logging.debug('Configuration file is not recognized as a JSON file.')
            invalid_json_error_msg = str(e)

        try:
            self.data = yaml.safe_load(self.compiled)
            self.valid_yaml = True
            logging.info('Configuration file is a valid YAML file.')
        except yaml.scanner.ScannerError as e:
            logging.debug('Configuration file is not recognized as a YAML file.')
            invalid_yaml_error_msg = str(e)

        if not self.valid_json and not self.valid_yaml:
            raise UnrecognizedConfigFileFormat(
                'Configuration file is neither a JSON file nor a YAML file!',
                self.source,
                invalid_json_error_msg,
                invalid_yaml_error_msg
            )

    def validate(self):
        validate(instance=self.data, schema=self.schema)
        logging.info('Configuration file is valid according to the JSON schema.')


class GenericHandler(tornado.web.RequestHandler):
    def initialize(self, method, response):
        self.custom_response = response
        self.custom_method = method.lower()

    def get(self):
        self.log_request()
        self.dynamic_unimplemented_method_guard()
        self.write(self.custom_response)

    def post(self):
        self.log_request()
        self.dynamic_unimplemented_method_guard()
        self.write(self.custom_response)

    def dynamic_unimplemented_method_guard(self):
        if self.custom_method != inspect.stack()[1][3]:
            self._unimplemented_method()

    def log_request(self):
        logging.debug('Received request:\n%s' % self.request.__dict__)


def make_app(endpoints, debug=False):
    endpoint_handlers = []
    for endpoint in endpoints:
        endpoint_handlers.append(
            (
                endpoint['path'],
                GenericHandler,
                dict(
                    method=endpoint['method'],
                    response=endpoint['response']
                )
            )
        )
        logging.info('Registered endpoint: %s %s' % (endpoint['method'].upper(), endpoint['path']))
        logging.debug('with response:\n%s' % endpoint['response'])
    return tornado.web.Application(endpoint_handlers, debug=debug)


def initiate():
    """The top-level method to serve as the entry point of Chupeta.

    This method is the entry point defined in `setup.py` for the `chupeta` executable that
    placed a directory in `$PATH`.

    This method parses the command-line arguments and handles the top-level initiations accordingly.
    """

    ap = argparse.ArgumentParser()
    ap.add_argument('source', help='Path to configuration file', nargs='?')
    ap.add_argument('-d', '--debug', help='Enable Tornado Web Server\'s debug mode', action='store_true')
    ap.add_argument('-q', '--quiet', help='Less logging messages, only warnings and errors', action='store_true')
    ap.add_argument('-v', '--verbose', help='More logging messages, including debug', action='store_true')
    ap.add_argument('-l', '--logfile', help='Also write log into a file', action='store')
    args = vars(ap.parse_args())

    fmt = "[%(asctime)s %(name)s %(levelname)s] %(message)s"
    if args['quiet']:
        logging.basicConfig(level=logging.WARNING, format=fmt)
    elif args['verbose']:
        logging.basicConfig(level=logging.DEBUG, format=fmt)
    else:
        logging.basicConfig(level=logging.INFO, format=fmt)

    if args['logfile']:
        handler = logging.FileHandler(args['logfile'])
        handler.setFormatter(logging.Formatter(fmt))
        logging.getLogger('').addHandler(handler)

    schema_path = path.join(__location__, 'schema.json')
    with open(schema_path, 'r') as file:
        schema_text = file.read()
        logging.debug('JSON schema: %s' % schema_text)
        schema = json.loads(schema_text)

    source = args['source']
    definition = Definition(source, schema)
    port_mapping = {}
    for service in definition.data['services']:
        port = str(service['port'])
        if port not in port_mapping:
            port_mapping[port] = []
        port_mapping[port].append(service)

    for port, services in port_mapping.items():
        rules = []
        for service in services:
            if 'hostname' not in service:
                service['hostname'] = 'localhost'
            app = make_app(service['endpoints'], args['debug'])
            rules.append(
                Rule(HostMatches(service['hostname']), app)
            )

            logging.info('Registered hostname and port: %s://%s:%d' % ('http', service['hostname'], service['port']))
            logging.info('Finished registering: %s' % service['comment'])

        if services:
            router = RuleRouter(rules)
            server = tornado.web.HTTPServer(router)
            server.listen(services[0]['port'])
            logging.info('Will listen port number: %d' % service['port'])

    if 'unittest' in sys.modules.keys():
        import os
        import signal
        parent_pid = os.getppid()
        os.kill(parent_pid, signal.SIGUSR1)

    logging.info('Mock server is ready!')
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    initiate()
