#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: the top-level module of Mockintosh.
"""

import argparse
import json
import logging
import sys
from collections import OrderedDict
from os import path

import yaml
from jsonschema import validate

from mockintosh import configs
from mockintosh.exceptions import UnrecognizedConfigFileFormat
from mockintosh.methods import _detect_engine, _nostderr, _import_from
from mockintosh.recognizers import PathRecognizer, HeadersRecognizer, QueryStringRecognizer
from mockintosh.servers import HttpServer
from mockintosh.handlers import Request, Response  # noqa: F401

__version__ = "0.1"
__location__ = path.abspath(path.dirname(__file__))


class Definition():

    def __init__(self, source, schema, is_file=True):
        self.source = source
        self.source_text = None if is_file else source
        self.data = None
        self.schema = schema
        if self.source is None:
            self.data = configs.get_default()
        else:
            self.load()
        self.validate()
        self.template_engine = _detect_engine(self.data, 'config')
        self.analyze()

    def load(self):
        if self.source_text is None:
            with open(self.source, 'r') as file:
                logging.info('Reading configuration file from path: %s' % self.source)
                self.source_text = file.read()
                logging.debug('Configuration text: %s' % self.source_text)

        try:
            self.data = yaml.safe_load(self.source_text)
            logging.info('Configuration file is a valid YAML file.')
        except (yaml.scanner.ScannerError, yaml.parser.ParserError) as e:
            raise UnrecognizedConfigFileFormat(
                'Configuration file is neither a JSON file nor a YAML file!',
                self.source,
                str(e)
            )

    def validate(self):
        validate(instance=self.data, schema=self.schema)
        logging.info('Configuration file is valid according to the JSON schema.')

    def analyze(self):
        for service in self.data['services']:
            if 'endpoints' not in service:
                continue
            for endpoint in service['endpoints']:
                endpoint['params'] = {}
                endpoint['context'] = OrderedDict()

                path_recognizer = PathRecognizer(
                    endpoint['path'],
                    endpoint['params'],
                    endpoint['context'],
                    self.template_engine
                )
                endpoint['path'], endpoint['priority'] = path_recognizer.recognize()

                if 'headers' in endpoint and endpoint['headers']:
                    headers_recognizer = HeadersRecognizer(
                        endpoint['headers'],
                        endpoint['params'],
                        endpoint['context'],
                        self.template_engine
                    )
                    endpoint['headers'] = headers_recognizer.recognize()

                if 'queryString' in endpoint and endpoint['queryString']:
                    headers_recognizer = QueryStringRecognizer(
                        endpoint['queryString'],
                        endpoint['params'],
                        endpoint['context'],
                        self.template_engine
                    )
                    endpoint['queryString'] = headers_recognizer.recognize()


def get_schema():
    schema = None
    schema_path = path.join(__location__, 'schema.json')
    with open(schema_path, 'r') as file:
        schema_text = file.read()
        logging.debug('JSON schema: %s' % schema_text)
        schema = json.loads(schema_text)
    return schema


def import_interceptors(interceptors):
    imported_interceptors = []
    if interceptors is not None:
        if 'unittest' in sys.modules.keys():
            tests_dir = path.join(__location__, '../tests')
            sys.path.append(tests_dir)
        for interceptor in interceptors:
            module, name = interceptor[0].rsplit('.', 1)
            imported_interceptors.append(_import_from(module, name))
    return imported_interceptors


def run(source, is_file=True, debug=False, interceptors=()):
    schema = get_schema()

    if 'unittest' in sys.modules.keys():
        sys.stdin = sys.__stdin__
    if source is None and sys.stdin is not None and not sys.stdin.isatty():
        stdin_text = sys.stdin.read()
        if stdin_text:
            source = stdin_text
            is_file = False

    try:
        definition = Definition(source, schema, is_file=is_file)
        http_server = HttpServer(definition, debug=debug, interceptors=interceptors)
    except Exception:
        logging.exception('Mock server loading error:')
        with _nostderr():
            raise
    http_server.run()


def initiate():
    """The top-level method to serve as the entry point of Mockintosh.

    This method is the entry point defined in `setup.py` for the `mockintosh` executable that
    placed a directory in `$PATH`.

    This method parses the command-line arguments and handles the top-level initiations accordingly.
    """

    ap = argparse.ArgumentParser()
    ap.add_argument('source', help='Path to configuration file', nargs='?')
    ap.add_argument('-d', '--debug', help='Enable Tornado Web Server\'s debug mode', action='store_true')
    ap.add_argument('-q', '--quiet', help='Less logging messages, only warnings and errors', action='store_true')
    ap.add_argument('-v', '--verbose', help='More logging messages, including debug', action='store_true')
    ap.add_argument('-i', '--interceptor', help='A list of interceptors to be called in <package>.<module>.<function> format.', action='append', nargs='+')
    ap.add_argument('-l', '--logfile', help='Also write log into a file', action='store')
    args = vars(ap.parse_args())

    interceptors = import_interceptors(args['interceptor'])

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

    run(args['source'], debug=args['debug'], interceptors=interceptors)
