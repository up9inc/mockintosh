#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: the top-level module of Chupeta.
"""

import argparse
import inspect
import json
import logging
import sys
import re
from os import path
from uuid import uuid4
from functools import wraps

import tornado.ioloop
import tornado.web
import yaml
from faker import Faker
from jinja2 import Template
from pybars import Compiler
from tornado.routing import Rule, RuleRouter, HostMatches
from jsonschema import validate

from chupeta.exceptions import UnrecognizedConfigFileFormat
from chupeta import configs
from chupeta.params import PathParam
from chupeta.methods import hbs_fake, random_integer, regex, _ignore_first_arg, _safe_path_split

__location__ = path.abspath(path.dirname(__file__))

JINJA = 'Jinja2'
PYBARS = 'Handlebars'


class Definition():
    def __init__(self, source, schema):
        self.source = source
        self.data = None
        self.valid_json = False
        self.valid_yaml = False
        self.schema = schema
        if self.source is None:
            self.data = configs.get_default()
        else:
            self.load()
        self.validate()
        self.analyze()

    def load(self):
        source_text = None
        with open(self.source, 'r') as file:
            logging.info('Reading configuration file from path: %s' % self.source)
            source_text = file.read()
            logging.debug('Configuration text: %s' % source_text)

        invalid_json_error_msg = None
        invalid_yaml_error_msg = None

        try:
            self.data = json.loads(source_text)
            self.valid_json = True
            logging.info('Configuration file is a valid JSON file.')
        except json.decoder.JSONDecodeError as e:
            logging.debug('Configuration file is not recognized as a JSON file.')
            invalid_json_error_msg = str(e)

        try:
            self.data = yaml.safe_load(source_text)
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

    def analyze(self):
        for service in self.data['services']:
            for endpoint in service['endpoints']:
                endpoint['params'] = {}
                segments = _safe_path_split(endpoint['path'])
                new_segments = []
                for index, segment in enumerate(segments):
                    var, new_segment = self.render_segment(segment)
                    if var is not None:
                        param = PathParam(var, index)
                        endpoint['params'][var] = param
                    new_segments.append(new_segment)

                endpoint['path'] = '/'.join(new_segments)

    def render_segment(self, text):
        var = None
        context = {}
        helpers = {}
        helpers['regEx'] = _ignore_first_arg(regex)
        compiler = Compiler()
        template = compiler.compile(text)
        compiled = template(context, helpers=helpers)
        if not compiled:
            match = re.match(r'{{(.*)}}', text)
            if match is not None:
                name = match.group(1).strip()
                context[name] = '.*'
                compiled = template(context, helpers=helpers)
                var = name
            else:
                compiled = text
        return var, compiled


class GenericHandler(tornado.web.RequestHandler):
    def initialize(self, method, response, params):
        self.custom_response = response
        self.custom_method = method.lower()
        self.custom_params = params

    def get(self):
        self.log_request()
        self.dynamic_unimplemented_method_guard()
        self.write(self.render_template())

    def post(self):
        self.log_request()
        self.dynamic_unimplemented_method_guard()
        self.write(self.render_template())

    def dynamic_unimplemented_method_guard(self):
        if self.custom_method != inspect.stack()[1][3]:
            self._unimplemented_method()

    def log_request(self):
        logging.debug('Received request:\n%s' % self.request.__dict__)

    def add_globals(self, template, helpers=None):
        fake = Faker()
        context = {}
        if helpers is None:
            helpers = template.globals
            context = helpers
        helpers['uuid'] = uuid4
        helpers['fake'] = fake
        helpers['randomInteger'] = random_integer
        context = self.add_params(context)

        # It means the template engine is PYBARS
        if helpers is not None:
            for key, helper in helpers.items():
                if callable(helper):
                    helpers[key] = _ignore_first_arg(helper)

            def super_fake(_, /, *args, **kwargs):
                return hbs_fake(fake, *args, **kwargs)

            helpers['fake'] = super_fake

        return context, helpers

    def add_params(self, context):
        for key, param in self.custom_params.items():
            if isinstance(param, PathParam):
                context[key] = _safe_path_split(self.request.path)[param.index]
        return context

    def render_template(self):
        source_text = None
        is_response_str = isinstance(self.custom_response, str)

        template_engine = PYBARS
        if 'templatingEngine' in self.custom_response and self.custom_response['templatingEngine'] == JINJA:
            template_engine = JINJA
        logging.info('Templating engine is: %s' % template_engine)

        if is_response_str:
            source_text = self.custom_response
        elif 'text' in self.custom_response:
            source_text = self.custom_response['text']
        else:
            template_path = self.custom_response['fromFile']
            with open(template_path, 'r') as file:
                logging.info('Reading template file from path: %s' % template_path)
                source_text = file.read()
                logging.debug('Template file text: %s' % source_text)

        compiled = None
        if not is_response_str and (
            'useTemplating' in self.custom_response and self.custom_response['useTemplating'] is False
        ):
            compiled = source_text
        else:
            if template_engine == JINJA:
                template = Template(source_text)
                self.add_globals(template)
                compiled = template.render()
            else:
                compiler = Compiler()
                context, helpers = self.add_globals(compiler._compiler, helpers={})
                template = compiler.compile(source_text)
                compiled = template(context, helpers=helpers)

        logging.debug('Render output: %s' % compiled)

        valid_json = False
        valid_yaml = False

        try:
            response = json.loads(compiled)
            valid_json = True
            logging.info('Template is a valid JSON.')
        except json.decoder.JSONDecodeError as e:
            logging.debug('Template is not recognized as a JSON.')
            invalid_json_error_msg = str(e)

        try:
            response = yaml.safe_load(compiled)
            valid_yaml = True
            logging.info('Template is a valid YAML.')
        except yaml.scanner.ScannerError as e:
            logging.debug('Template is not recognized as a YAML.')
            invalid_yaml_error_msg = str(e)

        if not valid_json and not valid_yaml:
            raise UnrecognizedConfigFileFormat(
                'Template is neither a JSON nor a YAML!',
                compiled,
                invalid_json_error_msg,
                invalid_yaml_error_msg
            )

        if is_response_str:
            return response
        else:
            return response['body']


def make_app(endpoints, debug=False):
    endpoint_handlers = []
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
            app = make_app(service['endpoints'], args['debug'])
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


if __name__ == '__main__':
    initiate()
