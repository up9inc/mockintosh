#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains request handlers.
"""

import json
import logging
import os
import re
import time
import socket
import struct
import traceback
import copy
from urllib.parse import quote_plus
from datetime import datetime, timezone
from typing import (
    Union,
    Optional,
    Awaitable,
    Tuple
)

import httpx
import jsonschema
import tornado.web
from accept_types import parse_header
from tornado.concurrent import Future
from tornado.http1connection import HTTP1Connection, HTTP1ServerConnection
from tornado import httputil

import mockintosh
from mockintosh.constants import PROGRAM, PYBARS, JINJA, SPECIAL_CONTEXT, BASE64
from mockintosh.replicas import Request, Response
from mockintosh.hbs.methods import Random as hbs_Random, Date as hbs_Date
from mockintosh.j2.methods import Random as j2_Random, Date as j2_Date
from mockintosh.helpers import _detect_engine, _b64encode
from mockintosh.params import (
    HeaderParam,
    QueryStringParam,
    BodyTextParam,
    BodyUrlencodedParam,
    BodyMultipartParam
)
from mockintosh.logs import Logs, LogRecord
from mockintosh.stats import Stats
from mockintosh.templating import TemplateRenderer, RenderingQueue

OPTIONS = 'options'
ORIGIN = 'Origin'
AC_REQUEST_HEADERS = 'Access-Control-Request-Headers'
NON_PREFLIGHT_METHODS = ('GET', 'HEAD', 'POST', 'DELETE', 'PATCH', 'PUT')
POST_CONFIG_RESTRICTED_FIELDS = ('port', 'hostname', 'ssl', 'sslCertFile', 'sslKeyFile')
IMAGE_MIME_TYPES = [
    'image/apng',
    'image/avif',
    'image/gif',
    'image/jpeg',
    'image/png',
    'image/svg+xml',
    'image/webp',
    'image/*'
]
IMAGE_EXTENSIONS = [
    '.apng',
    '.avif',
    '.gif',
    '.jpg',
    '.jpeg',
    '.jfif',
    '.pjpeg',
    '.pjp',
    '.png',
    '.svg',
    '.webp'
]

FALLBACK_TO_TIMEOUT = int(os.environ.get('MOCKINTOSH_FALLBACK_TO_TIMEOUT', 30))
CONTENT_TYPE = 'Content-Type'

hbs_random = hbs_Random()
j2_random = j2_Random()

hbs_date = hbs_Date()
j2_date = j2_Date()

client = httpx.AsyncClient()

__location__ = os.path.abspath(os.path.dirname(__file__))


class NewHTTPError(Exception):
    """Class as an alternative to raising `HTTPError` (workaround)."""
    pass


class Counters:
    def __init__(self):
        self.data = {}


counters = Counters()


class BaseHandler:

    def __init__(self):
        self.custom_context = {}
        self.counters = counters
        self.replica_request = None
        self.replica_response = None

    def resolve_relative_path(self, source_text: str) -> Tuple[str, str]:
        """Method to resolve the relative path (relative to the config file)."""
        orig_relative_path = source_text[1:]

        orig_relative_path, context = self.common_template_renderer(self.definition_engine, orig_relative_path)
        self.populate_counters(context)

        if orig_relative_path[0] == '/':
            orig_relative_path = orig_relative_path[1:]
        return os.path.join(self.config_dir, orig_relative_path), orig_relative_path

    def common_template_renderer(self, template_engine: str, text: str) -> Tuple[str, dict]:
        """Common method to initialize `TemplateRenderer` and call `render()`."""
        if template_engine == PYBARS:
            from mockintosh.hbs.methods import fake, counter, json_path, escape_html, env
            self.custom_context['random'] = hbs_random
            self.custom_context['date'] = hbs_date
        elif template_engine == JINJA:
            from mockintosh.j2.methods import fake, counter, json_path, escape_html, env
            self.custom_context['random'] = j2_random
            self.custom_context['date'] = j2_date

        renderer = TemplateRenderer()
        return renderer.render(
            template_engine,
            text,
            self.rendering_queue,
            inject_objects=self.custom_context,
            inject_methods=[
                fake,
                counter,
                json_path,
                escape_html,
                env
            ],
            add_params_callback=self.add_params,
            counters=self.counters
        )

    def populate_counters(self, context: [None, dict]) -> None:
        """Method that retrieves counters from template engine contexts."""
        if SPECIAL_CONTEXT in context and 'counters' in context[SPECIAL_CONTEXT]:
            for key, value in context[SPECIAL_CONTEXT]['counters'].items():
                self.counters.data[key] = value

    def analyze_counters(self) -> None:
        """Method that injects counters into template engine contexts."""
        for key, value in self.counters.data.items():
            self.custom_context[key] = value

    def add_params(self, context: [None, dict]) -> [None, dict]:
        raise NotImplementedError

    def add_log_record(
        self,
        elapsed_time_in_milliseconds: int,
        request_start_datetime: datetime,
        server_connection: Union[HTTP1ServerConnection, None]
    ) -> LogRecord:
        """Method that creates a log record and inserts it to log tracking system."""
        if not self.logs.services[self.service_id].is_enabled():
            logging.debug('Not logging the request because logging is disabled.')
            return

        log_record = LogRecord(
            self.logs.services[self.service_id].name,
            request_start_datetime,
            elapsed_time_in_milliseconds,
            self.replica_request,
            self.replica_response,
            server_connection
        )
        self.logs.services[self.service_id].add_record(log_record)

        return log_record

    def load_dataset(self, dataset: [list, str]) -> dict:
        """Method that loads a dataset."""
        if isinstance(dataset, list):
            return dataset
        else:
            dataset_path, _ = self.resolve_relative_path(dataset)
            with open(dataset_path, 'r') as file:
                logging.info('Reading dataset file from path: %s', dataset_path)
                data = json.load(file)
                logging.debug('Dataset: %s', data)
                return data


class GenericHandler(tornado.web.RequestHandler, BaseHandler):
    """Class to handle all mocked requests."""

    def prepare(self) -> Optional[Awaitable[None]]:
        """Overriden method of tornado.web.RequestHandler"""
        self.dont_add_status_code = False
        super().prepare()

    def on_finish(self) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        elapsed_time = self.request.request_time()
        request_start_datetime = datetime.fromtimestamp(self.request._start_time)
        request_start_datetime.replace(tzinfo=timezone.utc)
        self.add_log_record(
            int(round(elapsed_time * 1000)),
            request_start_datetime,
            self.request.server_connection
        )
        if self.get_status() != 500 and not self.is_options and self.methods is not None:
            if self.get_status() != 405:
                self.set_elapsed_time(elapsed_time)
            if not self.dont_add_status_code:
                if self.get_status() == 405:
                    self.stats.services[self.service_id].add_status_code(
                        str(self.get_status())
                    )
                else:
                    self.stats.services[self.service_id].endpoints[self.internal_endpoint_id].add_status_code(
                        str(self.get_status())
                    )
        super().on_finish()

    def clear(self) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        self._headers = httputil.HTTPHeaders(
            {
                "Date": httputil.format_timestamp(time.time()),
            }
        )
        self.set_default_headers()
        self._write_buffer = []
        self._status_code = 200
        self._reason = httputil.responses[200]

    def write(self, chunk: Union[str, bytes, dict]) -> None:
        super().write(chunk)
        if self.replica_response is not None:
            self.replica_response.bodySize = len(b"".join(self._write_buffer))

    def set_elapsed_time(self, elapsed_time_in_seconds: float) -> None:
        """Method to calculate and store the elapsed time of the request handling to be used in stats."""
        self.stats.services[self.service_id].endpoints[self.internal_endpoint_id].add_request_elapsed_time(
            elapsed_time_in_seconds
        )

    def initialize(
        self,
        http_server,
        config_dir: str,
        service_id: int,
        endpoints: list,
        _globals: dict,
        definition_engine: str,
        rendering_queue: RenderingQueue,
        interceptors: list,
        unhandled_data,
        fallback_to: Union[str, None],
        tags: list
    ) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        try:
            self.http_server = http_server
            self.config_dir = config_dir
            self.endpoints = endpoints
            self.methods = None
            self.custom_args = ()
            self.stats = self.http_server.definition.stats
            self.logs = self.http_server.definition.logs
            self.service_id = service_id
            self.internal_endpoint_id = None
            self.unhandled_data = unhandled_data
            self.fallback_to = fallback_to
            self.tags = tags

            for path, methods in self.endpoints:
                if re.fullmatch(path, self.request.path):
                    groups = re.findall(path, self.request.path)
                    if isinstance(groups[0], tuple):
                        self.custom_args = groups[0]
                    elif isinstance(groups, list) and groups:
                        self.custom_args = tuple(groups)
                    self.methods = {k.lower(): v for k, v in methods.items()}
                    break

            self.alternatives = None
            self.globals = _globals
            self.definition_engine = definition_engine
            self.rendering_queue = rendering_queue
            self.interceptors = interceptors
            self.is_options = False
            self.custom_dataset = {}

            self.replica_request = self.build_replica_request()
            self.default_context = {
                'request': self.replica_request
            }
        except Exception as e:  # pragma: no cover
            self.set_status(500)
            self.write(''.join(traceback.format_tb(e.__traceback__)))
            self.write('%s' % str(e))

    async def super_verb(self, *args) -> None:
        """A method to unify all the HTTP verbs under a single flow."""
        try:
            self.args_backup = args

            if not self.is_options:
                if self.custom_args:
                    args = self.custom_args
                if self.methods is None:
                    await self.raise_http_error(404)
                await self.dynamic_unimplemented_method_guard()

            self._set_default_headers()

            match_alternative_return = await self.match_alternative()
            if not match_alternative_return:
                return
            _id, response, params, context, dataset, internal_endpoint_id, performance_profile = match_alternative_return
            self.internal_endpoint_id = internal_endpoint_id
            self.stats.services[self.service_id].endpoints[self.internal_endpoint_id].increase_request_counter()
            self.custom_endpoint_id = _id
            self.custom_response = response
            self.custom_params = params
            self.initial_context = context
            self.custom_dataset = dataset
            self.performance_profile = performance_profile

            self.populate_context(*args)
            self.determine_status_code()
            self.determine_headers()
            self.log_request()

            self.rendered_body = self.render_template()

            if self.rendered_body is None:
                return
            self.replica_response = self.build_replica_response()
            if self.should_write():
                self.write(self.rendered_body)
        except NewHTTPError:
            return
        except Exception as e:  # pragma: no cover
            self.set_status(500)
            self.write(''.join(traceback.format_tb(e.__traceback__)))
            self.write('%s' % str(e))

    async def get(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        await self.super_verb(*args)

    async def post(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        await self.super_verb(*args)

    async def head(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        await self.super_verb(*args)

    async def delete(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        await self.super_verb(*args)

    async def patch(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        await self.super_verb(*args)

    async def put(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        await self.super_verb(*args)

    async def options(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        self.is_options = True
        await self.super_verb(*args)

    def populate_context(self, *args) -> None:
        """Method to populate the context to be used by the templating engines."""
        self.custom_context = {}
        for key, value in self.custom_dataset.items():
            self.custom_context[key] = value
        if args:
            for i, key in enumerate(self.initial_context):
                if key == SPECIAL_CONTEXT:
                    continue
                try:
                    self.custom_context[key] = args[i]
                except IndexError:
                    pass
        self.custom_context.update(self.default_context)
        self.analyze_component('headers')
        self.analyze_component('queryString')
        self.analyze_component('bodyText')
        self.analyze_component('bodyUrlencoded')
        self.analyze_component('bodyMultipart')
        self.analyze_counters()

    async def dynamic_unimplemented_method_guard(self) -> None:
        """Method to handle unimplemented HTTP verbs (`405`)."""
        if self.request.method.lower() not in self.methods:
            self.write('Supported HTTP methods: %s' % ', '.join([x.upper() for x in self.methods.keys()]))
            await self.raise_http_error(405)

    def _request_object_to_dict(self, obj):
        result = {}
        for key, value in obj.__dict__.items():
            if not (
                isinstance(value, HTTP1Connection) or isinstance(value, HTTP1ServerConnection)
            ) and hasattr(value, '__dict__'):
                result[key] = self._request_object_to_dict(value)
            else:
                result[key] = value
        return result

    def log_request(self) -> None:
        """Method that logs the request."""
        logging.debug('Received request:\n%s', self._request_object_to_dict(self.request))

    def add_params(self, context: [None, dict]) -> [None, dict]:
        """Method that injects parameters defined in the config into template engine contexts."""
        if not hasattr(self, 'custom_params'):
            return context
        query_arguments = self.request.query_arguments
        for key, param in self.custom_params.items():
            if isinstance(param, HeaderParam):
                context[key] = self.request.headers.get(param.key.title())
            if isinstance(param, QueryStringParam):
                try:
                    context[key] = query_arguments[param.key].pop(0).decode()
                except IndexError:
                    try:
                        context[key] = self.get_query_argument(param.key)
                    except tornado.web.MissingArgumentError:
                        context[key] = self.get_argument(param.key)
                except KeyError:
                    for arg in query_arguments:
                        match = re.search(key, arg)
                        if match is not None:
                            try:
                                context[param.key] = match.group(1).strip()
                                break
                            except IndexError:
                                continue
            if isinstance(param, BodyTextParam):
                context[key] = self.request.body.decode()
            if isinstance(param, BodyUrlencodedParam):
                context[key] = self.get_body_argument(param.key)
            if isinstance(param, BodyMultipartParam):
                context[key] = self.request.files[param.key][0].body.decode()
        return context

    def render_template(self) -> str:
        """Method that handles response template rendering."""
        is_binary = False
        template_engine = _detect_engine(self.custom_response, 'response', default=self.definition_engine)
        source_text = self.custom_response['body'] if 'body' in self.custom_response else None

        if source_text is None:
            return source_text

        if len(source_text) > 1 and source_text[0] == '@':
            template_path, _ = self.resolve_relative_path(source_text)
            with open(template_path, 'rb') as file:
                logging.debug('Reading external file from path: %s', template_path)
                source_text = file.read()
                try:
                    source_text = source_text.decode()
                    logging.debug('Template file text: %s', source_text)
                except UnicodeDecodeError:
                    is_binary = True
                    logging.debug('Template file is binary. Templating disabled.')

        compiled = None
        context = None
        if is_binary or not self.custom_response.get('useTemplating', True):
            compiled = source_text
        else:
            compiled, context = self.common_template_renderer(template_engine, source_text)
            self.populate_counters(context)

        if not is_binary:
            logging.debug('Render output: %s', compiled)

        return compiled

    def build_replica_request(self) -> Request:
        """Method that builds the replica `Request` object to be injected into the response templating."""
        request = Request()

        # Details
        request.version = self.request.version
        request.remoteIp = self.request.remote_ip
        request.protocol = self.request.protocol
        request.host = self.request.host
        request.hostName = self.request.host_name
        request.port = self.request.server_connection.stream.socket.getsockname()[1]
        request.uri = self.request.uri

        # Method
        request.method = self.request.method

        # Path
        request.set_path(self.request.path)

        # Headers
        for key, value in self.request.headers._dict.items():
            request.headers[key] = value
            request.headers[key.lower()] = value

        # Query String
        for key, value in self.request.query_arguments.items():
            request.queryString[key] = [x.decode() for x in value]
            if len(request.queryString[key]) == 1:
                request.queryString[key] = request.queryString[key][0]

        # Body
        if self.request.body_arguments:
            request.mimeType = 'application/x-www-form-urlencoded'
            for key, value in self.request.body_arguments.items():
                try:
                    request.bodyType[key] = 'str'
                    request.body[key] = [x.decode() for x in value]
                except (AttributeError, UnicodeDecodeError):
                    request.bodyType[key] = BASE64
                    request.body[key] = [_b64encode(x) for x in value]
                if len(request.body[key]) == 1:
                    request.body[key] = request.body[key][0]
        elif self.request.files:
            request.mimeType = 'multipart/form-data'
            for key, value in self.request.files.items():
                try:
                    request.bodyType[key] = 'str'
                    request.body[key] = [x.body.decode() for x in value]
                except (AttributeError, UnicodeDecodeError):
                    request.bodyType[key] = BASE64
                    request.body[key] = [_b64encode(x.body) for x in value]
                if len(request.body[key]) == 1:
                    request.body[key] = request.body[key][0]
        else:
            request.mimeType = 'text/plain'
            try:
                request.bodyType = 'str'
                request.body = self.request.body.decode()
            except (AttributeError, UnicodeDecodeError):
                request.bodyType = BASE64
                request.body = _b64encode(self.request.body)
        request.bodySize = len(self.request.body)

        # Files
        request.files = self.request.files

        return request

    def build_replica_response(self) -> Response:
        """Method that prepares replica `Response` object to be modified by the interceptors."""
        response = Response()

        response.status = self._status_code
        response.headers = self._headers
        if not hasattr(self, 'rendered_body'):
            self.rendered_body = None
        response.body = self.rendered_body

        return response

    def update_response(self) -> None:
        """Updates the response according to modifications made in interceptors."""
        self._status_code = self.replica_response.status
        self._headers = self.replica_response.headers
        self.rendered_body = self.replica_response.body
        self._write_buffer = []
        if self.rendered_body is None:
            self.rendered_body = ''
        if self.should_write():
            self.write(self.rendered_body)

    def determine_status_code(self) -> None:
        """Method to determine the status code of the response."""
        status_code = None
        if 'status' in self.custom_response:
            if isinstance(self.custom_response['status'], str):
                compiled, context = self.common_template_renderer(
                    self.definition_engine,
                    self.custom_response['status']
                )
                self.populate_counters(context)
                try:
                    status_code = int(compiled)
                except ValueError:
                    status_code = compiled
            else:
                status_code = self.custom_response['status']
        else:
            status_code = 200

        if self.performance_profile is not None:
            status_code = self.performance_profile.trigger(status_code)

        if isinstance(status_code, str) and status_code.lower() == 'rst':
            self.request.server_connection.stream.socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_LINGER,
                struct.pack('ii', 1, 0)
            )
            self.request.server_connection.stream.close()
            self.set_elapsed_time(self.request.request_time())
            self.stats.services[self.service_id].endpoints[self.internal_endpoint_id].add_status_code('RST')
        if isinstance(status_code, str) and status_code.lower() == 'fin':
            self.request.server_connection.stream.close()
            self.stats.services[self.service_id].endpoints[self.internal_endpoint_id].add_status_code('FIN')
            self.dont_add_status_code = True
        else:
            self.set_status(status_code)

    def analyze_component(self, component: str) -> None:
        """Method that analyzes various HTTP components."""
        if SPECIAL_CONTEXT not in self.initial_context or component not in self.initial_context[SPECIAL_CONTEXT]:
            return

        payload = None
        if component == 'headers':
            payload = self.request.headers._dict
        elif component == 'queryString':
            payload = self.request.query_arguments
        elif component == 'bodyText':
            payload = self.request.body.decode()
        elif component == 'bodyUrlencoded':
            payload = self.request.body_arguments
        elif component == 'bodyMultipart':
            payload = self.request.files

        for key, value in self.initial_context[SPECIAL_CONTEXT][component].items():
            _key = key
            if component == 'headers':
                _key = key.title()
            if _key in payload or component == 'bodyText':
                if value['type'] == 'regex':
                    match_string = None
                    if component == 'headers':
                        match_string = self.request.headers.get(key)
                    elif component == 'queryString':
                        match_string = self.get_query_argument(key)
                    elif component == 'bodyText':
                        match_string = payload
                    elif component == 'bodyUrlencoded':
                        match_string = self.get_body_argument(key)
                    elif component == 'bodyMultipart':
                        match_string = self.request.files[key][0].body.decode()

                    match = re.search(value['regex'], match_string)
                    if match is not None:
                        for i, key in enumerate(value['args']):
                            self.custom_context[key] = match.group(i + 1)

    def determine_headers(self) -> None:
        """Method to determine the headers of the response."""
        if self.custom_endpoint_id is not None:
            self.set_header('x-%s-endpoint-id' % PROGRAM.lower(), self.custom_endpoint_id)

        if 'headers' in self.globals:
            for key, value in self.globals['headers'].items():
                self.set_header(key, value)

        if 'headers' not in self.custom_response:
            return

        for key, value in self.custom_response['headers'].items():
            value_list = None
            if isinstance(value, list):
                value_list = value

            if isinstance(value, str):
                value_list = [value]

            new_value_list = []
            for value in value_list:
                new_value, context = self.common_template_renderer(self.definition_engine, value)
                self.populate_counters(context)
                new_value_list.append(new_value)

            for value in new_value_list:
                if key.title() == 'Set-Cookie':
                    value_splitted = value.split('=')
                    value_splitted[1] = quote_plus(value_splitted[1])
                    self.set_cookie(value_splitted[0], value_splitted[1])
                else:
                    self.set_header(key, value)

    async def match_alternative(self) -> tuple:
        """Method to handles all the request matching logic.

        If the request does not match to any alternatives defined in the config, it returns `400`.

        It also handles the automatic CORS.
        """
        if await self.should_cors():
            self.respond_cors()
            return ()

        self.alternatives = self.methods[self.request.method.lower()]

        response = None
        params = None
        context = None
        reason = None
        for alternative in self.alternatives:
            fail = False

            # Headers
            if 'headers' in alternative:
                for key, value in alternative['headers'].items():
                    request_header_val = self.request.headers.get(key.title())
                    if key.title() not in self.request.headers._dict:
                        self.internal_endpoint_id = alternative['internalEndpointId']
                        fail = True
                        reason = '%r not in the request headers!' % key.title()
                        break
                    if value == request_header_val:
                        continue
                    value = '^%s$' % value
                    match = re.search(value, request_header_val)
                    if match is None:
                        self.internal_endpoint_id = alternative['internalEndpointId']
                        fail = True
                        reason = 'Request header value %r on key %r does not match to regex: %s' % (
                            request_header_val,
                            key.title(),
                            value
                        )
                        break
                if fail:
                    continue

            # Query String
            if 'queryString' in alternative:
                for key, value in alternative['queryString'].items():
                    # To prevent 400, default=None
                    default = None
                    request_query_val = self.get_query_argument(key, default=default)
                    if request_query_val is default:
                        is_matched = False
                        if re.escape(key) != key:
                            for _key in self.request.query_arguments:
                                match = re.search(key, _key)
                                if match is not None:
                                    is_matched = True
                                    break
                        if not is_matched:
                            self.internal_endpoint_id = alternative['internalEndpointId']
                            fail = True
                            reason = 'Key %r couldn\'t found in the query string!' % key
                            break
                    if value == request_query_val:
                        continue
                    if request_query_val is default:
                        continue
                    value = '^%s$' % value
                    match = re.search(value, request_query_val)
                    if match is None:
                        self.internal_endpoint_id = alternative['internalEndpointId']
                        fail = True
                        reason = 'Request query parameter value %r on key %r does not match to regex: %s' % (
                            request_query_val,
                            key,
                            value
                        )
                        break
                if fail:
                    continue

            # Body
            if 'body' in alternative:
                body = self.request.body.decode()

                # Schema
                if 'schema' in alternative['body']:
                    json_schema = alternative['body']['schema']
                    if isinstance(json_schema, str) and len(json_schema) > 1 and json_schema[0] == '@':
                        json_schema_path, _ = self.resolve_relative_path(json_schema)
                        with open(json_schema_path, 'r') as file:
                            logging.info('Reading JSON schema file from path: %s', json_schema_path)
                            try:
                                json_schema = json.load(file)
                            except json.decoder.JSONDecodeError:
                                self.send_error(
                                    500,
                                    message='JSON decode error of the JSON schema file: %s' % json_schema
                                )
                                return
                            logging.debug('JSON schema: %s', json_schema)
                    json_data = None

                    if body and json_schema:
                        try:
                            json_data = json.loads(body)
                        except json.decoder.JSONDecodeError:
                            self.internal_endpoint_id = alternative['internalEndpointId']
                            fail = True
                            reason = 'JSON decode error of the request body:\n\n%s' % body
                            break

                    if json_schema:
                        try:
                            jsonschema.validate(instance=json_data, schema=json_schema)
                        except jsonschema.exceptions.ValidationError:
                            self.internal_endpoint_id = alternative['internalEndpointId']
                            fail = True
                            reason = 'Request body:\n\n%s\nDoes not match to JSON schema:\n\n%s' % (
                                json_data,
                                json_schema
                            )
                            break

                # Text
                if 'text' in alternative['body']:
                    value = alternative['body']['text']
                    if not body == value:
                        match = re.search(value, body)
                        if match is None:
                            self.internal_endpoint_id = alternative['internalEndpointId']
                            fail = True
                            reason = 'Request body:\n\n%s\nDeos not match to regex:\n\n%s' % (body, value)
                            break

                # Urlencoded
                if 'urlencoded' in alternative['body']:
                    for key, value in alternative['body']['urlencoded'].items():
                        # To prevent 400, default=None
                        default = None
                        body_argument = self.get_body_argument(key, default=default)
                        if body_argument is default:
                            self.internal_endpoint_id = alternative['internalEndpointId']
                            fail = True
                            reason = 'Key %r couldn\'t found in the form data!' % key
                            break
                        if value == body_argument:
                            continue
                        value = '^%s$' % value
                        match = re.search(value, body_argument)
                        if match is None:
                            self.internal_endpoint_id = alternative['internalEndpointId']
                            fail = True
                            reason = 'Form field value %r on key %r does not match to regex: %s' % (
                                body_argument,
                                key,
                                value
                            )
                            break
                    if fail:
                        continue

                # Multipart
                if 'multipart' in alternative['body']:
                    for key, value in alternative['body']['multipart'].items():
                        if key not in self.request.files:
                            self.internal_endpoint_id = alternative['internalEndpointId']
                            fail = True
                            reason = 'Key %r couldn\'t found in the multipart data!' % key
                            break
                        multipart_argument = self.request.files[key][0].body.decode()
                        if value == multipart_argument:
                            continue
                        value = '^%s$' % value
                        match = re.search(value, multipart_argument)
                        if match is None:
                            self.internal_endpoint_id = alternative['internalEndpointId']
                            fail = True
                            reason = 'Multipart field value %r on key %r does not match to regex: %s' % (
                                multipart_argument,
                                key,
                                value
                            )
                            break
                    if fail:
                        continue

            # Multiple responses
            if 'response' in alternative:
                response = alternative['response']
                if isinstance(alternative['response'], list):
                    if not len(alternative['response']) > 0:
                        response = {'body': None}
                    else:
                        response = self.loop_alternative(alternative, 'response', 'multiResponses')
                        if not response:
                            return ()

                response = response if isinstance(response, dict) else {'body': response}
            else:
                response = {'body': None}

            # Dataset
            dataset = {}
            if 'dataset' in alternative:
                alternative['dataset'] = self.load_dataset(alternative['dataset'])
                if alternative['dataset']:
                    dataset = self.loop_alternative(alternative, 'dataset', 'dataset')
                    if not dataset:
                        return ()

            _id = alternative['id']
            params = alternative['params']
            context = alternative['context']
            internal_endpoint_id = alternative['internalEndpointId']
            performance_profile = alternative['performanceProfile']
            return (_id, response, params, context, dataset, internal_endpoint_id, performance_profile)

        self.write(reason)
        await self.raise_http_error(400)

    def trigger_interceptors(self) -> None:
        """Method to trigger the interceptors"""
        for interceptor in self.interceptors:
            interceptor(self.replica_request, self.replica_response)

    def finish(self, chunk: Optional[Union[str, bytes, dict]] = None) -> "Future[None]":
        """Overriden method of tornado.web.RequestHandler"""
        if self._status_code not in (204, 500, 'RST', 'FIN'):
            if self.replica_response is None:
                self.replica_response = self.build_replica_response()
            self.trigger_interceptors()
            if self.interceptors:
                self.update_response()
        if self._status_code not in ('RST', 'FIN'):
            try:
                int(self._status_code)
                super().finish(chunk)
            except ValueError:
                self._status_code = 500
                super().finish('Status code is neither an integer nor in \'RST\', \'FIN\'!')

    def should_write(self) -> bool:
        """Method that decides whether if calling `self.write()` is applicable or not."""
        return not hasattr(self, 'custom_response') or 'body' in self.custom_response

    def resolve_relative_path(self, source_text: str) -> [None, str]:
        relative_path, orig_relative_path = super().resolve_relative_path(source_text)
        error_msg = 'External template file %r couldn\'t be accessed or found!' % orig_relative_path
        if not os.path.isfile(relative_path):
            self.send_error(500, message=error_msg)
            return None
        relative_path = os.path.abspath(relative_path)
        if not relative_path.startswith(self.config_dir):
            self.send_error(500, message=error_msg)
            return None

        return relative_path, orig_relative_path

    def write_error(self, status_code: int, **kwargs) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        if 'message' in kwargs and kwargs['message']:
            self.finish(kwargs['message'])
        else:  # pragma: no cover
            self.finish()

    def respond_cors(self) -> None:
        """Method that handles automatic CORS."""
        if ORIGIN not in self.request.headers._dict:
            # Invalid CORS preflight request
            self.set_status(404)
            return

        self.set_status(204)
        self.finish()

    def set_cors_headers(self) -> None:
        """Method that sets the CORS headers."""
        if ORIGIN in self.request.headers._dict:
            self.set_header('Access-Control-Allow-Methods', 'DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT')
            origin = self.request.headers.get(ORIGIN)
            self.set_header('Access-Control-Allow-Origin', origin)

            if AC_REQUEST_HEADERS in self.request.headers._dict:
                ac_request_headers = self.request.headers.get(AC_REQUEST_HEADERS)
                self.set_header('Access-Control-Allow-Headers', ac_request_headers)

    def _set_default_headers(self) -> None:
        """Method that sets the default headers."""
        self.set_header('Server', '%s/%s' % (
            PROGRAM.capitalize(),
            mockintosh.__version__
        ))
        self.set_header('x-%s-prompt' % PROGRAM.lower(), "Hello, I'm Mockintosh.")  # clear signature that it's mock
        self.set_cors_headers()

    async def should_cors(self) -> bool:
        """Method that decides whether the request is applicable for automatic CORS or not."""
        if self.is_options and self.methods is None:
            await self.raise_http_error(404)
        return self.is_options and self.methods is not None and self.request.method.lower() not in self.methods.keys()

    def loop_alternative(self, alternative: dict, key: str, subkey: str) -> dict:
        """Method that contains the logic to loop through the alternatives."""
        index_key = '%sIndex' % subkey
        loop_key = '%sLooped' % subkey
        if index_key not in alternative:
            alternative[index_key] = 0
        else:
            alternative[index_key] += 1

        resetted = False
        if alternative[index_key] > len(alternative[key]) - 1:
            if alternative.get(loop_key, True):
                alternative[index_key] = 0
                resetted = True
            else:
                self.internal_endpoint_id = alternative['internalEndpointId']
                self.set_status(410)
                self.finish()
                return False

        if 'tag' in alternative[key][alternative[index_key]]:
            if alternative[key][alternative[index_key]]['tag'] not in self.tags:
                if resetted:
                    self.internal_endpoint_id = alternative['internalEndpointId']
                    self.set_status(410)
                    self.finish()
                    return False
                else:
                    return self.loop_alternative(alternative, key, subkey)
            else:
                return alternative[key][alternative[index_key]]
        else:
            return alternative[key][alternative[index_key]]

    async def raise_http_error(self, status_code: int) -> None:
        """Method to throw a `NewHTTPError`."""
        await self.resolve_unhandled_request()

        self.set_status(status_code)

        if status_code == 404 and self.is_request_image_like():
            with open(os.path.join(__location__, 'res/mock.png'), 'rb') as file:
                image = file.read()
                self.set_header(CONTENT_TYPE, 'image/png')
                self.write(image)
                self.rendered_body = image

        raise NewHTTPError()

    async def resolve_unhandled_request(self) -> None:
        if self.fallback_to is None:
            if not self.is_request_image_like():
                self.insert_unhandled_data((self.request, None))
            return

        # Headers
        headers = {}
        for key, value in self.request.headers._dict.items():
            if key.title() in (
                'Host',
                'Content-Length'
            ):
                continue
            headers[key] = value
        headers['Cache-Control'] = 'no-cache'
        headers['If-None-Match'] = '0'

        # Query String
        query_string = ''
        for key, value in self.request.query_arguments.items():
            if not query_string:
                query_string = '?'
            values = [x.decode() for x in value]
            if len(values) == 1:
                query_string += '%s=%s' % (key, values[0])
            else:
                for _value in values:
                    query_string += '%s[]=%s' % (key, _value)

        # Body
        data = {}
        files = {}
        if self.request.body_arguments:
            for key, value in self.request.body_arguments.items():
                try:
                    data[key] = [x.decode() for x in value]
                except (AttributeError, UnicodeDecodeError):
                    data[key] = [x for x in value]
                if len(data[key]) == 1:
                    data[key] = data[key][0]
        elif self.request.files:
            for key, value in self.request.files.items():
                try:
                    files[key] = [x.body.decode() for x in value]
                except (AttributeError, UnicodeDecodeError):
                    files[key] = [x.body for x in value]
                if len(files[key]) == 1:
                    files[key] = files[key][0]
        else:
            data = self.request.body.decode()

        url = self.fallback_to.rstrip('/') + self.request.path + query_string

        # The service is external
        logging.info('Forwarding the unhandled request to: %s %s', self.request.method, url)

        http_verb = getattr(client, self.request.method.lower())
        try:
            if self.request.method.upper() in ('POST', 'PUT', 'PATCH', 'DELETE'):
                resp = await http_verb(url, headers=headers, timeout=FALLBACK_TO_TIMEOUT, data=data, files=files)
            else:
                resp = await http_verb(url, headers=headers, timeout=FALLBACK_TO_TIMEOUT)
        except httpx.TimeoutException:
            self.set_status(504)
            self.write('Forwarded request to: %s %s is timed out!' % (self.request.method, url))
            raise NewHTTPError()
        except httpx.ConnectError:
            self.set_status(502)
            self.write('Name or service not known: %s' % self.fallback_to.rstrip('/'))
            raise NewHTTPError()

        logging.debug('Returned back from the forwarded request.')

        self.set_status(resp.status_code if resp.status_code != 304 else 200)
        for key, value in resp.headers.items():
            if key.title() in (
                'Transfer-Encoding',
                'Content-Length',
                'Content-Encoding',
                'Access-Control-Allow-Methods',
                'Access-Control-Allow-Origin'
            ):
                continue
            self.set_header(key, value)

        self.write(resp.content)
        self.replica_response = self.build_replica_response()
        self.replica_response.body = resp.content

        if not self.is_request_image_like():
            self.insert_unhandled_data((self.request, self.replica_response))
        raise NewHTTPError()

    def insert_unhandled_data(self, row: tuple) -> None:
        if self.unhandled_data is None:
            return

        identifier = '%s %s' % (self.request.method.upper(), self.request.path)
        if identifier not in self.unhandled_data.requests[self.service_id]:
            self.unhandled_data.requests[self.service_id][identifier] = []
        self.unhandled_data.requests[self.service_id][identifier].append(row)

    def is_request_image_like(self) -> bool:
        ext = os.path.splitext(self.request.path)[1]
        parsed_header = parse_header(self.request.headers.get('Accept', 'text/html'))
        client_mime_types = [parsed.mime_type for parsed in parsed_header if parsed.mime_type != '*/*']
        return (client_mime_types and set(client_mime_types).issubset(IMAGE_MIME_TYPES)) or ext in IMAGE_EXTENSIONS


class KafkaHandler(BaseHandler):
    """Class to handle mocked Kafka data."""

    def __init__(
        self,
        actor_id: int,
        internal_endpoint_id: [int, None],
        config_dir: [str, None],
        template_engine: str,
        rendering_queue: RenderingQueue,
        logs: Logs,
        stats: Stats,
        address: str,
        topic: str,
        is_producer: bool,
        service_id: int = None,
        value: Union[str, None] = None,
        key: Union[str, None] = None,
        headers: dict = {},
        context: dict = {},
        params: dict = {}
    ):
        super().__init__()
        self.actor_id = actor_id
        self.internal_endpoint_id = internal_endpoint_id
        self.config_dir = config_dir
        self.definition_engine = template_engine
        self.rendering_queue = rendering_queue
        self.initial_context = context
        if is_producer:
            self.custom_context = context
        else:
            self.custom_context = {}
        self.custom_params = params
        self.logs = logs
        self.stats = stats
        self.address = address
        self.topic = topic
        self.service_id = service_id
        self.is_producer = is_producer
        self.value = value
        self.key = key
        self.headers = headers
        self.response_body = None
        self.response_headers = None

        if not is_producer:
            self.analyze_component('asyncHeaders')
            self.analyze_component('asyncValue')
            self.analyze_component('asyncKey')

        self.analyze_counters()
        self.replica_request = self.build_replica_request()

    def _render_value(self, value):
        is_binary = False
        if len(value) > 1 and value[0] == '@':
            template_path, context = self.resolve_relative_path(value)
            with open(template_path, 'rb') as file:
                logging.debug('Reading external file from path: %s', template_path)
                value = file.read()
                try:
                    value = value.decode()
                    logging.debug('Template file text: %s', value)
                except UnicodeDecodeError:
                    is_binary = True
                    logging.debug('Template file is binary. Templating disabled.')
        compiled = None
        context = None
        if is_binary:
            compiled = value
        else:
            compiled, context = self.common_template_renderer(self.definition_engine, value)
            self.populate_counters(context)

        if not is_binary:
            logging.debug('Render output: %s', compiled)

        return compiled

    def _render_attributes(self, *args):
        rendered = []
        for arg in args:
            if arg is None:
                rendered.append(arg)

            if isinstance(arg, dict):
                new_arg = {}
                for key, value in arg.items():
                    new_arg[key] = self._render_value(value)
                rendered.append(new_arg)
            elif isinstance(arg, str):
                rendered.append(self._render_value(arg))

        return rendered

    def render_attributes(self):
        self.key, self.value, self.headers = self._render_attributes(
            self.key,
            self.value,
            self.headers
        )
        self.replica_request = self.build_replica_request()
        return self.key, self.value, self.headers

    def add_params(self, context):
        return context

    def set_response(
        self,
        key: Union[str, None] = None,
        value: Union[str, None] = None,
        headers: dict = {}
    ):
        self.response_body = value
        self.response_headers = copy.deepcopy(headers)
        if key is not None:
            self.response_headers['x-%s-message-key' % PROGRAM.lower()] = key

    def finish(self) -> Union[LogRecord, None]:
        self.replica_response = self.build_replica_response()

        if self.logs is None:
            return None

        timestamp = datetime.fromtimestamp(time.time())
        timestamp.replace(tzinfo=timezone.utc)

        self.add_log_record(
            0,
            timestamp,
            None
        )

        return LogRecord(
            self.logs.services[self.service_id].name,
            timestamp,
            0,
            self.replica_request,
            self.replica_response,
            None
        )

    def build_replica_request(self) -> Request:
        """Method that builds the replica `Request` object."""
        request = Request()

        hostname, port = self.address.split(':')

        # Details
        request.version = None
        request.remoteIp = None
        request.protocol = 'kafka'
        request.host = self.address
        request.hostName = hostname
        request.port = port
        request.uri = None

        # Method
        request.method = NON_PREFLIGHT_METHODS[5] if self.is_producer else NON_PREFLIGHT_METHODS[0]

        # Path
        request.path = '/%s' % self.topic

        # Headers
        for key, value in self.headers.items():
            request.headers[key.title()] = value

        # Query String
        if self.key is not None:
            request.queryString['key'] = self.key

        # Body
        request.mimeType = 'text/plain'
        if isinstance(self.value, (bytes, bytearray)):
            request.bodyType = BASE64
            request.body = _b64encode(self.value)
        else:
            request.bodyType = 'str'
            request.body = self.value
        request.bodySize = 0 if self.value is None else len(self.value)

        # Files
        request.files = []

        return request

    def build_replica_response(self) -> Response:
        """Method that prepares replica `Response` object."""
        response = Response()
        status_code = 202 if self.is_producer else 200
        response.status = status_code

        if self.stats is not None:
            self.stats.services[self.service_id].endpoints[self.internal_endpoint_id].increase_request_counter()
            self.stats.services[self.service_id].endpoints[self.internal_endpoint_id].add_status_code(status_code)
            self.stats.services[self.service_id].endpoints[self.actor_id].add_request_elapsed_time(0)

        if self.response_body is None:
            response.body = ''
            return response

        response.headers = self.response_headers
        response.body = self.response_body

        return response

    def analyze_component(self, component: str) -> None:
        """Method that analyzes various async components."""
        if SPECIAL_CONTEXT not in self.initial_context or component not in self.initial_context[SPECIAL_CONTEXT]:
            return

        payload = None
        if component == 'asyncHeaders':
            payload = self.headers
        elif component == 'asyncValue':
            payload = self.value
        elif component == 'asyncKey':
            payload = self.key

        for key, value in self.initial_context[SPECIAL_CONTEXT][component].items():
            _key = key
            if (payload is not None and _key in payload) or component in ('asyncValue', 'asyncKey'):
                if value['type'] == 'regex':
                    match_string = None
                    if component == 'asyncHeaders':
                        match_string = self.headers.get(key)
                    elif component == 'asyncValue':
                        match_string = payload
                    elif component == 'asyncKey':
                        match_string = payload

                    if match_string is None:
                        continue

                    match = re.search(value['regex'], match_string)
                    if match is not None:
                        for i, key in enumerate(value['args']):
                            self.custom_context[key] = match.group(i)
