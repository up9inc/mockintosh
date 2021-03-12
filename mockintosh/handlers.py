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
import socket
import struct
import traceback
from urllib.parse import quote_plus, urlparse
from datetime import datetime, timezone
from typing import (
    Union,
    Optional,
    Awaitable
)

import requests
import jsonschema
import tornado.web
from accept_types import parse_header
from tornado.concurrent import Future

import mockintosh
from mockintosh.constants import PROGRAM, SUPPORTED_ENGINES, PYBARS, JINJA, SPECIAL_CONTEXT
from mockintosh.replicas import Request, Response
from mockintosh.exceptions import UnsupportedTemplateEngine
from mockintosh.hbs.methods import Random as hbs_Random, Date as hbs_Date
from mockintosh.j2.methods import Random as j2_Random, Date as j2_Date
from mockintosh.methods import _safe_path_split, _detect_engine, _decoder, _is_mostly_bin, _b64encode
from mockintosh.params import (
    PathParam,
    HeaderParam,
    QueryStringParam,
    BodyTextParam,
    BodyUrlencodedParam,
    BodyMultipartParam
)
from mockintosh.stats import Stats
from mockintosh.logs import Logs, LogRecord
from mockintosh.templating import TemplateRenderer

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

hbs_random = hbs_Random()
j2_random = j2_Random()

hbs_date = hbs_Date()
j2_date = j2_Date()

counters = {}

__location__ = os.path.abspath(os.path.dirname(__file__))


class NewHTTPError(Exception):
    """Class as an alternative to raising `HTTPError` (workaround)."""
    pass


class GenericHandler(tornado.web.RequestHandler):
    """Class to handle all mocked requests."""

    def prepare(self) -> Optional[Awaitable[None]]:
        """Overriden method of tornado.web.RequestHandler"""
        self.dont_add_status_code = False
        super().prepare()

    def on_finish(self) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        elapsed_time = self.request.request_time()
        self.add_log_record(int(round(elapsed_time * 1000)))
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
        if self.is_unhandled_request:
            self.insert_unhandled_data((self.request, self.special_response))
        super().on_finish()

    def write(self, chunk: Union[str, bytes, dict]) -> None:
        super().write(chunk)
        if hasattr(self, 'special_response'):
            self.special_response.bodySize = len(b"".join(self._write_buffer))

    def set_elapsed_time(self, elapsed_time_in_seconds: float) -> None:
        """Method to calculate and store the elapsed time of the request handling to be used in stats."""
        self.stats.services[self.service_id].endpoints[self.internal_endpoint_id].add_request_elapsed_time(
            elapsed_time_in_seconds
        )

    def add_log_record(self, elapsed_time_in_milliseconds: int) -> None:
        """Method that creates a log record and inserts it to log tracking system."""
        if not self.logs.services[self.service_id].is_enabled() or self.request.server_connection.stream.socket is None:
            return

        if not hasattr(self, 'special_response'):
            self.special_response = self.build_special_response()

        request_start_datetime = datetime.fromtimestamp(self.request._start_time)
        request_start_datetime.replace(tzinfo=timezone.utc)
        log_record = LogRecord(
            self.logs.services[self.service_id].name,
            request_start_datetime,
            elapsed_time_in_milliseconds,
            self.special_request,
            self.special_response,
            self.request.server_connection
        )
        self.logs.services[self.service_id].add_record(log_record)

    def initialize(
        self,
        http_server,
        config_dir: str,
        service_id: int,
        endpoints: list,
        _globals: dict,
        definition_engine: str,
        interceptors: list,
        stats: Stats,
        logs: Logs,
        unhandled_data,
        fallback_to: Union[str, None],
        tag: Union[str, None],
        is_unhandled_request: bool
    ) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        try:
            self.http_server = http_server
            self.config_dir = config_dir
            self.endpoints = endpoints
            self.methods = None
            self.custom_args = ()
            self.stats = stats
            self.logs = logs
            self.service_id = service_id
            self.internal_endpoint_id = None
            self.unhandled_data = unhandled_data
            self.fallback_to = fallback_to
            self.tag = tag
            self.is_unhandled_request = is_unhandled_request

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
            self.interceptors = interceptors
            self.is_options = False
            self.custom_dataset = {}

            self.special_request = self.build_special_request()
            self.default_context = {
                'request': self.special_request
            }
            self.custom_context = {}
        except Exception as e:
            self.set_status(500)
            self.write(''.join(traceback.format_tb(e.__traceback__)))
            self.write('%s' % str(e))

    def super_verb(self, *args) -> None:
        """A method to unify all the HTTP verbs under a single flow."""
        try:
            self.args_backup = args
            self.set_default_headers()

            if not self.is_options:
                if self.custom_args:
                    args = self.custom_args
                if self.methods is None:
                    self.raise_http_error(404)
                self.dynamic_unimplemented_method_guard()

            match_alternative_return = self.match_alternative()
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
            self.special_response = self.build_special_response()
            if self.should_write():
                self.write(self.rendered_body)
        except NewHTTPError:
            return
        except Exception as e:
            self.set_status(500)
            self.write(''.join(traceback.format_tb(e.__traceback__)))
            self.write('%s' % str(e))

    def get(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        self.super_verb(*args)

    def post(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        self.super_verb(*args)

    def head(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        self.super_verb(*args)

    def delete(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        self.super_verb(*args)

    def patch(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        self.super_verb(*args)

    def put(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        self.super_verb(*args)

    def options(self, *args) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        self.is_options = True
        self.super_verb(*args)

    def populate_context(self, *args) -> None:
        """Method to populate the context to be used by the templating engines."""
        self.custom_context = {}
        for key, value in self.custom_dataset.items():
            self.custom_context[key] = value
        if args:
            if len(args) >= len(self.initial_context):
                for i, key in enumerate(self.initial_context):
                    self.custom_context[key] = args[i]
            else:
                self.raise_http_error(404)
        self.custom_context.update(self.default_context)
        self.analyze_component('headers')
        self.analyze_component('queryString')
        self.analyze_component('bodyText')
        self.analyze_component('bodyUrlencoded')
        self.analyze_component('bodyMultipart')
        self.analyze_counters()

    def populate_counters(self, context: [None, dict]) -> None:
        """Method that retrieves counters from template engine contexts."""
        if context is None:
            return

        if SPECIAL_CONTEXT in context and 'counters' in context[SPECIAL_CONTEXT]:
            for key, value in context[SPECIAL_CONTEXT]['counters'].items():
                counters[key] = value

    def dynamic_unimplemented_method_guard(self) -> None:
        """Method to handle unimplemented HTTP verbs (`405`)."""
        if self.methods is None:
            self.raise_http_error(404)
        if self.request.method.lower() not in self.methods:
            self.write('Supported HTTP methods: %s' % ', '.join([x.upper() for x in self.methods.keys()]))
            self.raise_http_error(405)

    def log_request(self) -> None:
        """Method that logs the request."""
        logging.debug('Received request:\n%s', self.request.__dict__)

    def add_params(self, context: [None, dict]) -> [None, dict]:
        """Method that injects parameters defined in the config into template engine contexts."""
        if not hasattr(self, 'custom_params'):
            return context
        for key, param in self.custom_params.items():
            if isinstance(param, PathParam):
                context[key] = _safe_path_split(self.request.path)[param.key]
            if isinstance(param, HeaderParam):
                context[key] = self.request.headers.get(param.key.title())
            if isinstance(param, QueryStringParam):
                context[key] = self.get_query_argument(param.key)
            if isinstance(param, BodyTextParam):
                context[key] = _decoder(self.request.body)
            if isinstance(param, BodyUrlencodedParam):
                context[key] = self.get_body_argument(param.key)
            if isinstance(param, BodyMultipartParam):
                context[key] = _decoder(self.request.files[param.key][0].body)
        return context

    def render_template(self) -> str:
        """Method that handles response template rendering."""
        is_binary = False
        template_engine = _detect_engine(self.custom_response, 'response', default=self.definition_engine)
        source_text = self.custom_response['body'] if 'body' in self.custom_response else None

        if source_text is None:
            return source_text

        if len(source_text) > 1 and source_text[0] == '@':
            template_path = self.resolve_relative_path(source_text)
            if template_path is None:
                return None
            with open(template_path, 'rb') as file:
                logging.debug('Reading external file from path: %s', template_path)
                source_text = file.read()
                try:
                    source_text = source_text.decode('utf-8')
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

    def build_special_request(self) -> Request:
        """Method that builds the `Request` object to be injected into the response templating."""
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
        request.path = self.request.path

        # Headers
        for key, value in self.request.headers._dict.items():
            request.headers[key] = value
            request.headers[key.lower()] = value

        # Query String
        for key, value in self.request.query_arguments.items():
            request.queryString[key] = [_decoder(x) for x in value]
            if len(request.queryString[key]) == 1:
                request.queryString[key] = request.queryString[key][0]

        # Body
        if self.request.body_arguments:
            request.mimeType = 'application/x-www-form-urlencoded'
            for key, value in self.request.body_arguments.items():
                if any(_is_mostly_bin(x) for x in value):
                    request.bodyType[key] = 'base64'
                    request.body[key] = [_b64encode(x) for x in value]
                else:
                    request.bodyType[key] = 'str'
                    request.body[key] = [_decoder(x) for x in value]
                if len(request.body[key]) == 1:
                    request.body[key] = request.body[key][0]
        elif self.request.files:
            request.mimeType = 'multipart/form-data'
            for key, value in self.request.files.items():
                if any(_is_mostly_bin(x.body) for x in value):
                    request.bodyType[key] = 'base64'
                    request.body[key] = [_b64encode(x.body) for x in value]
                else:
                    request.bodyType[key] = 'str'
                    request.body[key] = [_decoder(x.body) for x in value]
                if len(request.body[key]) == 1:
                    request.body[key] = request.body[key][0]
        else:
            request.mimeType = 'text/plain'
            if _is_mostly_bin(request.body):
                request.bodyType = 'base64'
                request.body = _b64encode(self.request.body)
            else:
                request.bodyType = 'str'
                request.body = _decoder(self.request.body)
        request.bodySize = len(self.request.body)

        request.files = self.request.files

        return request

    def build_special_response(self) -> Response:
        """Method that prepares `Response` object to be modified by the interceptors."""
        response = Response()

        response.status = self._status_code
        response.headers = self._headers
        if not hasattr(self, 'rendered_body'):
            self.rendered_body = None
        response.body = self.rendered_body

        return response

    def update_response(self) -> None:
        """Updates the response according to modifications made in interceptors."""
        self._status_code = self.special_response.status
        self._headers = self.special_response.headers
        self.rendered_body = self.special_response.body
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
            payload = _decoder(self.request.body)
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
                        match_string = _decoder(self.request.files[key][0].body)

                    match = re.search(value['regex'], match_string)
                    if match is not None:
                        for i, key in enumerate(value['args']):
                            self.custom_context[key] = match.group(i + 1)

    def analyze_counters(self) -> None:
        """Method that injects counters into template engine contexts."""
        for key, value in counters.items():
            self.custom_context[key] = value

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

    def match_alternative(self) -> tuple:
        """Method to handles all the request matching logic.

        If the request does not match to any alternatives defined in the config, it returns `400`.

        It also handles the automatic CORS.
        """
        if self.should_cors():
            self.respond_cors()
            return ()

        if self.methods is None:
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
                        reason = '\'%s\' not in the request headers!' % key.title()
                        break
                    if value == request_header_val:
                        continue
                    value = '^%s$' % value
                    match = re.search(value, request_header_val)
                    if match is None:
                        self.internal_endpoint_id = alternative['internalEndpointId']
                        fail = True
                        reason = 'Request header value \'%s\' on key \'%s\' does not match to regex: %s' % (
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
                        self.internal_endpoint_id = alternative['internalEndpointId']
                        fail = True
                        reason = 'Key \'%s\' couldn\'t found in the query string!' % key
                        break
                    if key not in self.request.query_arguments:
                        self.internal_endpoint_id = alternative['internalEndpointId']
                        fail = True
                        reason = 'Key \'%s\' couldn\'t found in the query string!' % key
                        break
                    if value == request_query_val:
                        continue
                    value = '^%s$' % value
                    match = re.search(value, request_query_val)
                    if match is None:
                        self.internal_endpoint_id = alternative['internalEndpointId']
                        fail = True
                        reason = 'Request query parameter value \'%s\' on key \'%s\' does not match to regex: %s' % (
                            request_query_val,
                            key,
                            value
                        )
                        break
                if fail:
                    continue

            # Body
            if 'body' in alternative:
                body = _decoder(self.request.body)

                # Schema
                if 'schema' in alternative['body']:
                    json_schema = alternative['body']['schema']
                    if isinstance(json_schema, str) and len(json_schema) > 1 and json_schema[0] == '@':
                        json_schema_path = self.resolve_relative_path(json_schema)
                        with open(json_schema_path, 'r') as file:
                            logging.info('Reading JSON schema file from path: %s', json_schema_path)
                            json_schema = json.load(file)
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

                # Urlncoded
                if 'urlencoded' in alternative['body']:
                    for key, value in alternative['body']['urlencoded'].items():
                        # To prevent 400, default=None
                        default = None
                        body_argument = self.get_body_argument(key, default=default)
                        if body_argument is default:
                            self.internal_endpoint_id = alternative['internalEndpointId']
                            fail = True
                            reason = 'Key \'%s\' couldn\'t found in the form data!' % key
                            break
                        if key not in self.request.body_arguments:
                            self.internal_endpoint_id = alternative['internalEndpointId']
                            fail = True
                            reason = 'Key \'%s\' couldn\'t found in the form data!' % key
                            break
                        if value == body_argument:
                            continue
                        value = '^%s$' % value
                        match = re.search(value, body_argument)
                        if match is None:
                            self.internal_endpoint_id = alternative['internalEndpointId']
                            fail = True
                            reason = 'Form field value \'%s\' on key \'%s\' does not match to regex: %s' % (
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
                            reason = 'Key \'%s\' couldn\'t found in the multipart data!' % key
                            break
                        multipart_argument = _decoder(self.request.files[key][0].body)
                        if value == multipart_argument:
                            continue
                        value = '^%s$' % value
                        match = re.search(value, multipart_argument)
                        if match is None:
                            self.internal_endpoint_id = alternative['internalEndpointId']
                            fail = True
                            reason = 'Multipart field value \'%s\' on key \'%s\' does not match to regex: %s' % (
                                multipart_argument,
                                key,
                                value
                            )
                            break
                    if fail:
                        continue

            if self.should_cors():
                self.respond_cors()

            # Multiple responses
            if 'response' in alternative:
                response = alternative['response']
                if isinstance(alternative['response'], list):
                    if not len(alternative['response']) > 0:
                        response = {
                            'body': None
                        }
                    else:
                        response = self.loop_alternative(alternative, 'response', 'multiResponses')
                        if not response:
                            return ()

                response = response if isinstance(response, dict) else {
                    'body': response
                }
            else:
                response = {
                    'body': None
                }

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
        self.raise_http_error(400)
        self.finish()

    def trigger_interceptors(self) -> None:
        """Method to trigger the interceptors"""
        for interceptor in self.interceptors:
            interceptor(self.special_request, self.special_response)

    def finish(self, chunk: Optional[Union[str, bytes, dict]] = None) -> "Future[None]":
        """Overriden method of tornado.web.RequestHandler"""
        if self._status_code not in (204, 500, 'RST', 'FIN'):
            if not hasattr(self, 'special_response'):
                self.special_response = self.build_special_response()
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
        """Method to resolve the relative path (relative to the config file)."""
        relative_path = None
        orig_relative_path = source_text[1:]

        orig_relative_path, context = self.common_template_renderer(self.definition_engine, orig_relative_path)
        self.populate_counters(context)

        error_msg = 'External template file \'%s\' couldn\'t be accessed or found!' % orig_relative_path
        if orig_relative_path[0] == '/':
            orig_relative_path = orig_relative_path[1:]
        relative_path = os.path.join(self.config_dir, orig_relative_path)
        if not os.path.isfile(relative_path):
            self.send_error(403, message=error_msg)
            return None
        relative_path = os.path.abspath(relative_path)
        if not relative_path.startswith(self.config_dir):
            self.send_error(403, message=error_msg)
            return None

        return relative_path

    def write_error(self, status_code: int, **kwargs) -> None:
        """Overriden method of tornado.web.RequestHandler"""
        if 'message' in kwargs and kwargs['message']:
            self.finish(kwargs['message'])
        else:
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

    def set_default_headers(self) -> None:
        """Method that sets the default headers."""
        self.set_header('Server', '%s/%s' % (
            PROGRAM.capitalize(),
            mockintosh.__version__
        ))
        self.set_header('X-Mockintosh-Prompt', "Hello, I'm Mockintosh.")  # clear signature that it's mock
        self.set_cors_headers()

    def should_cors(self) -> bool:
        """Method that decides whether the request is applicable for automatic CORS or not."""
        if self.is_options and self.methods is None:
            self.raise_http_error(404)
        return self.is_options and self.methods is not None and self.request.method.lower() not in self.methods.keys()

    def load_dataset(self, dataset: [list, str]) -> dict:
        """Method that loads a dataset."""
        if isinstance(dataset, list):
            return dataset
        else:
            dataset_path = self.resolve_relative_path(dataset)
            with open(dataset_path, 'r') as file:
                logging.info('Reading dataset file from path: %s', dataset_path)
                data = json.load(file)
                logging.debug('Dataset: %s', data)
                return data

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
            if self.tag is None:
                if resetted:
                    self.internal_endpoint_id = alternative['internalEndpointId']
                    self.set_status(410)
                    self.finish()
                    return False
                else:
                    return self.loop_alternative(alternative, key, subkey)
            elif self.tag != alternative[key][alternative[index_key]]['tag']:
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

    def common_template_renderer(self, template_engine: str, text: str) -> str:
        """Common method to initialize `TemplateRenderer` and call `render()`."""
        if template_engine == PYBARS:
            from mockintosh.hbs.methods import fake, counter, json_path, escape_html
            self.custom_context['random'] = hbs_random
            self.custom_context['date'] = hbs_date
        elif template_engine == JINJA:
            from mockintosh.j2.methods import fake, counter, json_path, escape_html
            self.custom_context['random'] = j2_random
            self.custom_context['date'] = j2_date
        else:
            raise UnsupportedTemplateEngine(template_engine, SUPPORTED_ENGINES)

        renderer = TemplateRenderer(
            template_engine,
            text,
            inject_objects=self.custom_context,
            inject_methods=[
                fake,
                counter,
                json_path,
                escape_html
            ],
            add_params_callback=self.add_params,
            fill_undefineds=True
        )
        return renderer.render()

    def raise_http_error(self, status_code: int) -> None:
        """Method to throw a `NewHTTPError`."""
        self.resolve_unhandled_request()

        self.set_status(status_code)

        if status_code == 404:
            ext = os.path.splitext(self.request.path)[1]
            parsed_header = parse_header(self.request.headers.get('Accept', 'text/html'))
            client_mime_types = [parsed.mime_type for parsed in parsed_header if parsed.mime_type != '*/*']
            if (client_mime_types and set(client_mime_types).issubset(IMAGE_MIME_TYPES)) or ext in IMAGE_EXTENSIONS:
                with open(os.path.join(__location__, 'res/mock.png'), 'rb') as file:
                    image = file.read()
                    self.set_header('content-type', 'image/png')
                    self.write(image)
                    self.rendered_body = image

        raise NewHTTPError()

    def resolve_unhandled_request(self) -> None:
        if self.fallback_to is None:
            self.insert_unhandled_data((self.request, None))
            return

        # Headers
        headers = {}
        for key, value in self.request.headers._dict.items():
            if key.title() in (
                'Host'
            ):
                continue
            headers[key] = value

        # Query String
        query_string = ''
        for key, value in self.request.query_arguments.items():
            if not query_string:
                query_string = '?'
            values = [_decoder(x) for x in value]
            if len(values) == 1:
                query_string += '%s=%s' % (key, values[0])
            else:
                for _value in values:
                    query_string += '%s[]=%s' % (key, _value)

        # Body
        body = None
        if self.request.body_arguments:
            body = {}
            for key, value in self.request.body_arguments.items():
                body[key] = [_decoder(x) for x in value]
                if len(body[key]) == 1:
                    body[key] = body[key][0]
        elif self.request.files:
            body = {}
            for key, value in self.request.files.items():
                body[key] = [_decoder(x.body) for x in value]
                if len(body[key]) == 1:
                    body[key] = body[key][0]
        else:
            body = _decoder(self.request.body)

        url = self.fallback_to.rstrip('/') + self.request.path + query_string
        url_parsed = urlparse(url)

        for i, app in enumerate(self.http_server._apps.apps):
            listener = self.http_server._apps.listeners[i]
            if (
                listener.hostname == url_parsed.hostname or listener.address == url_parsed.hostname
            ) and listener.port == url_parsed.port:
                # Found the service internally
                logging.info('Redirecting the unhandled request to internal: %s %s' % (self.request.method, url))
                for rule in self.http_server._apps.apps[i].default_router.rules[0].target.rules:
                    if rule.target == GenericHandler:
                        new_target_kwargs = rule.target_kwargs
                        new_target_kwargs['is_unhandled_request'] = True
                        rule.target.initialize(self, *new_target_kwargs.values())
                        rule.target.super_verb(self, *self.args_backup)
                logging.info('Returned back from the internal redirected request.')
                raise NewHTTPError()

        # The service is external
        logging.info('Redirecting the unhandled request to external: %s %s' % (self.request.method, url))

        http_verb = getattr(requests, self.request.method.lower())
        resp = http_verb(url, headers=headers, timeout=5)

        logging.info('Returned back from the external redirected request.')

        self.set_status(resp.status_code if resp.status_code != 304 else 200)
        for key, value in resp.headers.items():
            if key.title() in (
                'Server',
                'Transfer-Encoding',
                'Content-Encoding',
                'Access-Control-Allow-Methods',
                'Access-Control-Allow-Origin'
            ):
                continue
            self.set_header(key, value)

        self.write(resp.text)
        self.special_response = self.build_special_response()
        self.special_response.body = resp.text

        self.insert_unhandled_data((self.request, self.special_response))
        raise NewHTTPError()

    def insert_unhandled_data(self, row: tuple) -> None:
        if self.unhandled_data is None:
            return

        identifier = '%s %s' % (self.request.method.upper(), self.request.path)
        if identifier not in self.unhandled_data.requests[self.service_id]:
            self.unhandled_data.requests[self.service_id][identifier] = []
        self.unhandled_data.requests[self.service_id][identifier].append(row)
