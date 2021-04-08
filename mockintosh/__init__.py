#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: the top-level module of Mockintosh.
"""

import argparse
import atexit
import json
import logging
import signal
import sys
import copy
from collections import OrderedDict
from os import path, environ
from gettext import gettext
from urllib.parse import parse_qs
from typing import (
    Tuple
)

import yaml
from jsonschema import validate

from mockintosh.constants import PROGRAM
from mockintosh.exceptions import UnrecognizedConfigFileFormat
from mockintosh.replicas import Request, Response  # noqa: F401
from mockintosh.helpers import _detect_engine, _nostderr, _import_from, _urlsplit
from mockintosh.recognizers import (
    PathRecognizer,
    HeadersRecognizer,
    QueryStringRecognizer,
    BodyTextRecognizer,
    BodyUrlencodedRecognizer,
    BodyMultipartRecognizer
)
from mockintosh.servers import HttpServer, TornadoImpl
from mockintosh.performance import PerformanceProfile
from mockintosh.templating import RenderingQueue, RenderingJob
from mockintosh.stats import Stats
from mockintosh.logs import Logs
from mockintosh.kafka import KafkaService, KafkaActor, KafkaConsumer, KafkaProducer

__version__ = "0.8.1"
__location__ = path.abspath(path.dirname(__file__))

should_cov = environ.get('COVERAGE_PROCESS_START', False)
cov_no_run = environ.get('COVERAGE_NO_RUN', False)

stats = Stats()
logs = Logs()


class Definition():

    def __init__(self, source, schema, rendering_queue, is_file=True):
        self.source = source
        self.source_text = None if is_file else source
        self.source_dir = path.dirname(path.abspath(source)) if source is not None and is_file else None
        self.data = None
        self.schema = schema
        self.rendering_queue = rendering_queue
        self.load()
        self.orig_data = copy.deepcopy(self.data)
        self.validate()
        for service in self.data['services']:
            service['orig_data'] = copy.deepcopy(service)
        self.template_engine = _detect_engine(self.data, 'config')
        self.data = self.analyze(self.data)
        self.stats = stats
        self.logs = logs

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

    def analyze(self, data):
        if 'performanceProfiles' in data:
            for key, performance_profile in data['performanceProfiles'].items():
                ratio = performance_profile.get('ratio')
                delay = performance_profile.get('delay', 0.0)
                faults = performance_profile.get('faults', {})
                data['performanceProfiles'][key] = PerformanceProfile(ratio, delay=delay, faults=faults)
        else:
            data['performanceProfiles'] = {}

        global_performance_profile = None
        if 'globals' in data:
            global_performance_profile = data['globals'].get('performanceProfile', None)

        data['kafka_services'] = []
        for service in data['services']:
            if 'type' in service:
                if service['type'] == 'kafka':
                    kafka_service = KafkaService(
                        service['address'],
                        name=service.get('name', None),
                        definition=self
                    )
                    data['kafka_services'].append(kafka_service)

                    for actor in service['actors']:
                        kafka_actor = KafkaActor(actor.get('name', None))
                        kafka_service.add_actor(kafka_actor)

                        if 'consume' in actor:
                            kafka_consumer = KafkaConsumer(actor['consume']['queue'])
                            kafka_actor.set_consumer(kafka_consumer)
                        if 'delay' in actor:
                            kafka_actor.set_delay(actor['delay'])
                        if 'produce' in actor:
                            kafka_producer = KafkaProducer(
                                actor['produce']['queue'],
                                actor['produce']['value'],
                                key=actor['produce'].get('key', None),
                                headers=actor['produce'].get('headers', {})
                            )
                            kafka_actor.set_producer(kafka_producer)
                        if 'limit' in actor:
                            kafka_actor.set_limit(actor['limit'])

                if service['type'] != 'http':
                    continue

            if 'endpoints' not in service:
                continue
            service = Definition.analyze_service(
                service,
                self.template_engine,
                self.rendering_queue,
                performance_profiles=data['performanceProfiles'],
                global_performance_profile=global_performance_profile
            )
        return data

    @staticmethod
    def analyze_service(
        service,
        template_engine,
        rendering_queue,
        performance_profiles={},
        global_performance_profile=None
    ):
        service_perfomance_profile = service.get('performanceProfile', global_performance_profile)
        for endpoint in service['endpoints']:
            endpoint['internalOrigPath'] = endpoint['path']
            endpoint['params'] = {}
            endpoint['context'] = OrderedDict()
            endpoint['performanceProfile'] = performance_profiles.get(
                endpoint.get('performanceProfile', service_perfomance_profile),
                None
            )

            scheme, netloc, path, query, fragment = _urlsplit(endpoint['path'])
            if 'queryString' not in endpoint:
                endpoint['queryString'] = {}
            parsed_query = parse_qs(query, keep_blank_values=True)
            endpoint['queryString'].update({k: parsed_query[k] for k, v in parsed_query.items()})

            path_recognizer = PathRecognizer(
                path,
                endpoint['params'],
                endpoint['context'],
                template_engine,
                rendering_queue
            )
            endpoint['path'], endpoint['priority'] = path_recognizer.recognize()

            if 'headers' in endpoint and endpoint['headers']:
                headers_recognizer = HeadersRecognizer(
                    endpoint['headers'],
                    endpoint['params'],
                    endpoint['context'],
                    template_engine,
                    rendering_queue
                )
                endpoint['headers'] = headers_recognizer.recognize()

            if 'queryString' in endpoint and endpoint['queryString']:
                query_string_recognizer = QueryStringRecognizer(
                    endpoint['queryString'],
                    endpoint['params'],
                    endpoint['context'],
                    template_engine,
                    rendering_queue
                )
                endpoint['queryString'] = query_string_recognizer.recognize()

            if 'body' in endpoint:
                if 'text' in endpoint['body'] and endpoint['body']['text']:
                    body_text_recognizer = BodyTextRecognizer(
                        endpoint['body']['text'],
                        endpoint['params'],
                        endpoint['context'],
                        template_engine,
                        rendering_queue
                    )
                    endpoint['body']['text'] = body_text_recognizer.recognize()

                if 'urlencoded' in endpoint['body'] and endpoint['body']['urlencoded']:
                    body_urlencoded_recognizer = BodyUrlencodedRecognizer(
                        endpoint['body']['urlencoded'],
                        endpoint['params'],
                        endpoint['context'],
                        template_engine,
                        rendering_queue
                    )
                    endpoint['body']['urlencoded'] = body_urlencoded_recognizer.recognize()

                if 'multipart' in endpoint['body'] and endpoint['body']['multipart']:
                    body_multipart_recognizer = BodyMultipartRecognizer(
                        endpoint['body']['multipart'],
                        endpoint['params'],
                        endpoint['context'],
                        template_engine,
                        rendering_queue
                    )
                    endpoint['body']['multipart'] = body_multipart_recognizer.recognize()

        return service


class CustomArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_help(sys.stderr)
        args = {'prog': self.prog, 'message': message}
        self.exit(2, gettext('\n%(prog)s: error: %(message)s\n') % args)


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


def start_render_queue() -> Tuple[RenderingQueue, RenderingJob]:
    queue = RenderingQueue()
    t = RenderingJob(queue)
    t.daemon = True
    t.start()

    return queue, t


def run(source, is_file=True, debug=False, interceptors=(), address='', services_list=[]):
    queue, _ = start_render_queue()

    if address:
        logging.info('Bind address: %s' % address)
    schema = get_schema()

    try:
        definition = Definition(source, schema, queue, is_file=is_file)
        http_server = HttpServer(
            definition,
            TornadoImpl(),
            debug=debug,
            interceptors=interceptors,
            address=address,
            services_list=services_list
        )
    except Exception:  # pragma: no cover
        logging.exception('Mock server loading error:')
        with _nostderr():
            raise
    http_server.run()


def gracefully_exit(num, frame):
    atexit._run_exitfuncs()
    if should_cov:  # pragma: no cover
        sys.exit()


def cov_exit(cov):
    if should_cov:
        logging.debug('Stopping coverage')
        cov.stop()
        cov.save()  # pragma: no cover


def initiate():
    if should_cov:  # pragma: no cover
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

    ap = CustomArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument(
        'source',
        help='Path to configuration file and (optional) a list of the service names\n'
             'to specify the services to be listened.',
        nargs='+'
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

    logging.info("%s v%s is starting..." % (PROGRAM.capitalize(), __version__))

    debug_mode = environ.get('DEBUG', False) or environ.get('MOCKINTOSH_DEBUG', False)
    if debug_mode:
        logging.debug('Tornado Web Server\'s debug mode is enabled!')

    source = args['source'][0]
    services_list = args['source'][1:]

    if not cov_no_run:  # pragma: no cover
        run(source, debug=debug_mode, interceptors=interceptors, address=address, services_list=services_list)
