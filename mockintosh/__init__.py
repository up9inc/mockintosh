import json
import logging
from os import path
from typing import Union

from mockintosh.definition import Definition
from mockintosh.helpers import _nostderr
from mockintosh.replicas import Request, Response  # noqa: F401

__location__ = path.abspath(path.dirname(__file__))

from mockintosh.servers import TornadoImpl


def get_schema():
    schema_path = path.join(__location__, 'schema.json')
    with open(schema_path, 'r') as file:
        schema_text = file.read()
        logging.debug('JSON schema: %s', schema_text)
        schema = json.loads(schema_text)
    return schema


def run(
        source: str,
        is_file: bool = True,
        debug: bool = False,
        interceptors: tuple = (),
        address: str = '',
        services_list: list = [],
        tags: list = [],
        load_override: Union[dict, None] = None
):
    queue, _ = start_render_queue()

    if address:  # pragma: no cover
        logging.info('Bind address: %s', address)
    schema = get_schema()

    try:
        definition = Definition(source, schema, queue, is_file=is_file, load_override=load_override)
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


class Mockintosh:
    def __init__(self, bind_address='', interceptors=(), debug=False) -> None:
        super().__init__()
        self.management = Management()

    def run(self):
        pass


class Service:
    pass


class Management(Service):
    def set_config(self, config, services_list):
        pass

    def set_enabled_tags(self, tags: list):
        pass
