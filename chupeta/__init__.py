#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: the top-level module of Chupeta.
"""

import argparse
import json
import logging
from os import path

import yaml
from jsonschema import validate

from chupeta.exceptions import UnrecognizedConfigFileFormat
from chupeta import configs
from chupeta.recognizers import PathRecognizer
from chupeta.servers import HttpServer
from chupeta.methods import _detect_engine

__location__ = path.abspath(path.dirname(__file__))


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
        self.template_engine = _detect_engine(self.data, 'config')
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

        if not self.valid_json:
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

                path_recognizer = PathRecognizer(
                    endpoint['path'],
                    endpoint['params'],
                    self.template_engine
                )
                endpoint['path'], endpoint['low_priority'] = path_recognizer.recognize()


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
    http_server = HttpServer(definition, args['debug'])
    http_server.run()


if __name__ == '__main__':
    initiate()
