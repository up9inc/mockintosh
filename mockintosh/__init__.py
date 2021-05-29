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
from os import path, environ
from gettext import gettext
from typing import (
    Tuple
)

from mockintosh.constants import PROGRAM
from mockintosh.definition import Definition
from mockintosh.replicas import Request, Response  # noqa: F401
from mockintosh.helpers import _nostderr, _import_from
from mockintosh.servers import HttpServer, TornadoImpl
from mockintosh.templating import RenderingQueue, RenderingJob
from mockintosh.transpilers import OASToConfigTranspiler

__version__ = "0.9"
__location__ = path.abspath(path.dirname(__file__))

should_cov = environ.get('COVERAGE_PROCESS_START', False)
cov_no_run = environ.get('COVERAGE_NO_RUN', False)


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
        logging.debug('JSON schema: %s', schema_text)
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


def run(
    source: str,
    is_file: bool = True,
    debug: bool = False,
    interceptors: tuple = (),
    address: str = '',
    services_list: list = [],
    tags: list = []
):
    queue, _ = start_render_queue()

    if address:  # pragma: no cover
        logging.info('Bind address: %s', address)
    schema = get_schema()

    try:
        definition = Definition(source, schema, queue, is_file=is_file)
        http_server = HttpServer(
            definition,
            TornadoImpl(),
            debug=debug,
            interceptors=interceptors,
            address=address,
            services_list=services_list,
            tags=tags
        )
    except Exception:  # pragma: no cover
        logging.exception('Mock server loading error:')
        with _nostderr():
            raise
    http_server.run()


def _gracefully_exit(num, frame):
    atexit._run_exitfuncs()
    if should_cov:  # pragma: no cover
        sys.exit()


def _cov_exit(cov):
    if should_cov:
        logging.debug('Stopping coverage')
        cov.stop()
        cov.save()  # pragma: no cover


def _handle_cli_args_logging(args: list, fmt: str) -> None:
    if args['quiet']:
        logging.basicConfig(level=logging.WARNING, format=fmt)
    elif args['verbose']:
        logging.basicConfig(level=logging.DEBUG, format=fmt)
    else:
        logging.basicConfig(level=logging.INFO, format=fmt)


def _handle_cli_args_logfile(args: list, fmt: str) -> None:
    if args['logfile']:
        handler = logging.FileHandler(args['logfile'])
        handler.setFormatter(logging.Formatter(fmt))
        logging.getLogger('').addHandler(handler)


def _handle_cli_args_tags(args: list) -> list:
    tags = []
    if args['enable_tags']:
        tags = args['enable_tags'].split(',')
    return tags


def _handle_cli_args(args: list) -> Tuple[tuple, str, list]:
    interceptors = import_interceptors(args['interceptor'])
    address = args['bind'] if args['bind'] is not None else ''
    tags = _handle_cli_args_tags(args)
    fmt = "[%(asctime)s %(name)s %(levelname)s] %(message)s"
    _handle_cli_args_logging(args, fmt)
    _handle_cli_args_logfile(args, fmt)

    return interceptors, address, tags


def _handle_oas_input(source: str, convert: str) -> str:
    oas_transpiler = OASToConfigTranspiler(source, convert)
    return oas_transpiler.transpile()


def initiate():
    if should_cov:  # pragma: no cover
        signal.signal(signal.SIGTERM, _gracefully_exit)
        logging.debug('Starting coverage')
        from coverage import Coverage
        cov = Coverage(data_suffix=True, config_file='.coveragerc')
        cov._warn_no_data = True
        cov._warn_unimported_source = True
        cov.start()
        atexit.register(_cov_exit, cov)

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
    ap.add_argument(
        '-c',
        '--convert',
        help='Convert an OpenAPI Specification (Swagger) 2.0 / 3.0 / 3.1 file to %s config' % PROGRAM.capitalize(),
        action='store'
    )
    ap.add_argument('--enable-tags', help='A comma separated list of tags to enable', action='store')
    args = vars(ap.parse_args())

    interceptors, address, tags = _handle_cli_args(args)

    debug_mode = environ.get('DEBUG', False) or environ.get('MOCKINTOSH_DEBUG', False)
    if debug_mode:
        logging.debug('Tornado Web Server\'s debug mode is enabled!')

    source = args['source'][0]
    services_list = args['source'][1:]
    convert = args['convert']

    if convert is not None:
        logging.info("Converting OpenAPI Specification %s to ./%s ...", source, convert)
        target_path = _handle_oas_input(source, convert)
        logging.info("The transpiled config YAML is ready at %s", target_path)
    else:
        logging.info("%s v%s is starting...", PROGRAM.capitalize(), __version__)

        if not cov_no_run:  # pragma: no cover
            run(
                source,
                debug=debug_mode,
                interceptors=interceptors,
                address=address,
                services_list=services_list,
                tags=tags
            )
