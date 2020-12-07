#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :platform: Unix
    :synopsis: the top-level module of Chupeta.
.. moduleauthor:: M. Mert Yildiran <mehmet@up9.com>
"""

import sys
import json
import yaml
import inspect
import argparse
import logging
from uuid import uuid4

from jinja2 import Template
from faker import Faker
import tornado.ioloop
import tornado.web

from chupeta.exceptions import UnrecognizedConfigFileFormat


class Definition():
    def __init__(self, source):
        self.source = source
        self.compiled = None
        self.data = None
        self.valid_json = False
        self.valid_yaml = False
        self._compile()
        self.load()

    def add_globals(self, template):
        fake = Faker()
        template.globals['uuid'] = uuid4
        template.globals['fake'] = fake

    def _compile(self):
        source_text = None
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


def make_app(endpoints):
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
    return tornado.web.Application(endpoint_handlers, debug=True)


def initiate():
    """The top-level method to serve as the entry point of Dragonfire.

    This method is the entry point defined in `setup.py` for the `dragonfire` executable that
    placed a directory in `$PATH`.

    This method parses the command-line arguments and handles the top-level initiations accordingly.
    """

    ap = argparse.ArgumentParser()
    ap.add_argument('source', help='Path to configuration file.', nargs='?')
    ap.add_argument('-q', '--quite', help='Disable all the log output.', action='store_true')
    ap.add_argument('-v', '--verbose', help='Increase verbosity of log output.', action='store_true')
    args = vars(ap.parse_args())

    if args['quite']:
        logging.basicConfig(level=logging.ERROR)
    elif args['verbose']:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    source = args['source']
    definition = Definition(source)
    for service in definition.data['services']:
        app = make_app(service['endpoints'])
        app.listen(service['port'])
        logging.warning('Started to listen: %s://%s:%s' % ('http', 'localhost', service['port']))
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    initiate()
