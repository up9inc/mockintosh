# !/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: the top-level module of Mockintosh.
"""

import argparse
import logging
import os
import shutil
import sys
from collections import namedtuple
from gettext import gettext
from os import path, environ
from typing import Union, Tuple, List

from prance import ValidationError
from prance.util.url import ResolutionError

from mockintosh.constants import PROGRAM
from mockintosh.helpers import _import_from
from mockintosh.replicas import Request, Response  # noqa: F401
from mockintosh.transpilers import OASToConfigTranspiler

__location__ = path.abspath(path.dirname(__file__))
with open(os.path.join(__location__, "res", "version.txt")) as fp:
    __version__ = fp.read().strip()


class CustomArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_help(sys.stderr)
        args = {'prog': self.prog, 'message': message}
        self.exit(2, gettext('\n%(prog)s: error: %(message)s\n') % args)


def _import_interceptors(interceptors):
    imported_interceptors = []
    for interceptor in interceptors if interceptors else []:
        module, name = interceptor[0].rsplit('.', 1)
        imported_interceptors.append(_import_from(module, name))
    return imported_interceptors


def _configure_logging(quiet, verbose, logfile) -> None:
    fmt = "[%(asctime)s %(name)s %(levelname)s] %(message)s"
    if quiet:
        logging.basicConfig(level=logging.WARNING, format=fmt)
        logging.getLogger('pika').setLevel(logging.CRITICAL)
        logging.getLogger('rsmq').setLevel(logging.CRITICAL)
    elif verbose:
        logging.basicConfig(level=logging.DEBUG, format=fmt)
    else:
        logging.basicConfig(level=logging.INFO, format=fmt)
        logging.getLogger('pika').setLevel(logging.CRITICAL)
        logging.getLogger('rsmq').setLevel(logging.CRITICAL)
    logging.getLogger('botocore').setLevel(logging.CRITICAL)
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.CRITICAL)

    if logfile:
        handler = logging.FileHandler(logfile)
        handler.setFormatter(logging.Formatter(fmt))
        logging.getLogger('').addHandler(handler)


def _handle_cli_args(args: namedtuple) -> Tuple[tuple, str, list]:
    interceptors = _import_interceptors(args.interceptor)
    address = args.bind if args.bind else ''
    tags = args.enable_tags.split(',') if args.enable_tags else []
    _configure_logging(args.quiet, args.verbose, args.logfile)

    return tuple(interceptors), address, tags


def _handle_oas_input(source: str, convert_args: List[str], direct: bool = False) -> Union[str, dict]:
    oas_transpiler = OASToConfigTranspiler(source, convert_args)
    return oas_transpiler.transpile(direct=direct)


def _load_config(source):
    pass


def _initiate(args):
    """The top-level method to serve as the entry point of Mockintosh.

    This method is the entry point defined in `setup.py` for the `mockintosh` executable that
    placed a directory in `$PATH`.

    This method parses the command-line arguments and handles the top-level initiations accordingly.
    """

    interceptors, address, tags = _handle_cli_args(args)

    debug_mode = environ.get('DEBUG', False) or environ.get('MOCKINTOSH_DEBUG', False)
    if debug_mode:
        logging.debug('Tornado Web Server\'s debug mode is enabled!')

    source = args.source[0]
    convert_args = args.convert

    if args.sample_config:
        fname = os.path.abspath(source)
        shutil.copy(os.path.join(__location__, "res", "sample.yml"), fname)
        logging.info("Created sample configuration file in %r", fname)
        logging.info("To run it, use the following command:\n    mockintosh %s", os.path.basename(fname))
    elif convert_args:
        logging.info("Converting OpenAPI Specification %s to %s in %s format...",
                     source, convert_args[0], convert_args[1].upper())
        target_path = _handle_oas_input(source, convert_args)
        logging.info("The transpiled config %s is written to %s", convert_args[1].upper(), target_path)
    else:
        try:
            loaded_config = _handle_oas_input(source, ['config.yaml', 'yaml'], True)
            logging.info("Automatically transpiled the config YAML from OpenAPI Specification.")
        except (ValidationError, AttributeError, ResolutionError):
            logging.debug("The input is not a valid OpenAPI Specification, defaulting to Mockintosh config.")
            loaded_config = _load_config(source)

        services_list = args['source'][1:]

        logging.info("%s v%s is starting...", PROGRAM.capitalize(), __version__)

        run(
            source,
            debug=debug_mode,
            interceptors=interceptors,
            address=address,
            services_list=services_list,
            tags=tags,
            load_override=load_override
        )


def _configure_args():
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
        help='Convert an OpenAPI Specification (Swagger) 2.0 / 3.0 / 3.1 file to %s config. '
             'Example: `$ mockintosh petstore.json -c dev.json json`' % PROGRAM.capitalize(),
        action='store',
        nargs='+',
        metavar=('filename', 'format')
    )
    ap.add_argument('--enable-tags', help='A comma separated list of tags to enable', action='store')
    ap.add_argument('--sample-config', help='Writes sample config file to disk', action='store_true')
    return ap


def main(args=None):
    args_parser = _configure_args()
    _initiate(args_parser.parse_args(args))


if __name__ == '__main__':
    main()
