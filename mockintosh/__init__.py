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
import atexit
import signal
from collections import OrderedDict
from os import path, environ

import yaml
from jsonschema import validate

from mockintosh import configs
from mockintosh.exceptions import UnrecognizedConfigFileFormat
from mockintosh.methods import _detect_engine, _nostderr, _import_from
from mockintosh.recognizers import PathRecognizer, HeadersRecognizer, QueryStringRecognizer, BodyRecognizer
from mockintosh.servers import HttpServer, TornadoImpl
from mockintosh.handlers import Request, Response  # noqa: F401

__version__ = "0.5"
__location__ = path.abspath(path.dirname(__file__))

should_cov = environ.get('COVERAGE_PROCESS_START', False)


class Definition():

    def __init__(self, source, schema, is_file=True):
        self.source = source
        self.source_text = None if is_file else source
        self.source_dir = path.dirname(path.abspath(source)) if source is not None and is_file else None
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

                if 'body' in endpoint and 'text' in endpoint['body'] and endpoint['body']['text']:
                    body_recognizer = BodyRecognizer(
                        endpoint['body']['text'],
                        endpoint['params'],
                        endpoint['context'],
                        self.template_engine
                    )
                    endpoint['body']['text'] = body_recognizer.recognize()


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


def run(source, is_file=True, debug=False, interceptors=(), address='', services_list=[]):
    if address:
        logging.info('Bind address: %s' % address)
    schema = get_schema()

    try:
        definition = Definition(source, schema, is_file=is_file)
        http_server = HttpServer(
            definition,
            TornadoImpl(),
            debug=debug,
            interceptors=interceptors,
            address=address,
            services_list=services_list
        )
    except Exception:
        logging.exception('Mock server loading error:')
        with _nostderr():
            raise
    http_server.run()


def gracefully_exit(num, frame):
    atexit._run_exitfuncs()
    if should_cov:
        sys.exit()


def cov_exit(cov):
    if should_cov:
        logging.debug('Stopping coverage')
        cov.stop()
        cov.save()


def initiate():
    if should_cov:
        signal.signal(signal.SIGTERM, gracefully_exit)
        logging.debug('Starting coverage')
        from coverage import Coverage
        cov = Coverage(data_suffix=True, config_file='.coveragerc')
        cov._warn_no_data = True
        cov._warn_unimported_source = True
        cov.start()
        atexit.register(cov_exit, cov)

    """The top-level method to serve as the entry point of Mockintosh.

    This method is the entry point defined in `setup.py` for the `mockintosh` executable that
    placed a directory in `$PATH`.

    This method parses the command-line arguments and handles the top-level initiations accordingly.
    """

    ap = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument(
        'source',
        help='Path to configuration file and (optional) a list of the service names\n'
             'to specify the services to be listened.',
        nargs='*'
    )
    ap.add_argument('-q', '--quiet', help='Less logging messages, only warnings and errors', action='store_true')
    ap.add_argument('-v', '--verbose', help='More logging messages, including debug', action='store_true')
    ap.add_argument(
        '-i',
        '--interceptor',
        help='A list of interceptors to be called in <package>.<module>.<function> format',
        action='append',
        nargs='+'
    )
    ap.add_argument('-l', '--logfile', help='Also write log into a file', action='store')
    ap.add_argument('-b', '--bind', help='Address to specify the network interface', action='store')
    args = vars(ap.parse_args())

    interceptors = import_interceptors(args['interceptor'])

    address = args['bind'] if args['bind'] is not None else ''

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

    debug_mode = environ.get('DEBUG', False) or environ.get('MOCKINTOSH_DEBUG', False)
    if debug_mode:
        logging.debug('Tornado Web Server\'s debug mode is enabled!')

    source = None
    services_list = []
    if len(args['source']) > 0:
        source = args['source'][0]
        services_list = args['source'][1:]

    run(source, debug=debug_mode, interceptors=interceptors, address=address, services_list=services_list)
