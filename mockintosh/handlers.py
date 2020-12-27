#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains request handlers.
"""

import re
import os
import json
import logging
import urllib
from typing import (
    Union,
    Optional
)

import tornado.web
import jsonschema
from tornado.web import HTTPError
from tornado.concurrent import Future

import mockintosh
from mockintosh.constants import PROGRAM, SUPPORTED_ENGINES, PYBARS, JINJA, SPECIAL_CONTEXT
from mockintosh.exceptions import UnsupportedTemplateEngine
from mockintosh.templating import TemplateRenderer
from mockintosh.params import PathParam, HeaderParam, QueryStringParam
from mockintosh.methods import _safe_path_split, _detect_engine

OPTIONS = 'options'
ORIGIN = 'Origin'
AC_REQUEST_HEADERS = 'Access-Control-Request-Headers'
NON_PREFLIGHT_METHODS = ("GET", "HEAD", "POST", "DELETE", "PATCH", "PUT")


class GenericHandler(tornado.web.RequestHandler):

    def initialize(self, config_dir, methods, _globals, definition_engine, interceptors):
        self.config_dir = config_dir
        self.methods = {k.lower(): v for k, v in methods.items()}
        self.alternatives = None
        self.globals = _globals
        self.definition_engine = definition_engine
        self.interceptors = interceptors
        self.is_options = False

        self.special_request = self.build_special_request()
        self.default_context = {
            'request': self.special_request
        }
        self.custom_context = {}

    def super_verb(self, *args):
        self.set_default_headers()

        if not self.__class__.__name__ == 'ErrorHandler' and not self.is_options:
            self.dynamic_unimplemented_method_guard()

        try:
            _id, response, params, context = self.match_alternative()
        except TypeError:
            return
        self.custom_endpoint_id = _id
        self.custom_response = response
        self.custom_params = params
        self.initial_context = context

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

    def get(self, *args):
        self.super_verb(*args)

    def post(self, *args):
        self.super_verb(*args)

    def head(self, *args):
        self.super_verb(*args)

    def delete(self, *args):
        self.super_verb(*args)

    def patch(self, *args):
        self.super_verb(*args)

    def put(self, *args):
        self.super_verb(*args)

    def options(self, *args):
        self.is_options = True
        self.super_verb(*args)

    def populate_context(self, *args):
        self.custom_context = {}
        if args:
            if len(args) >= len(self.initial_context):
                for i, key in enumerate(self.initial_context):
                    self.custom_context[key] = args[i]
            else:
                HTTPError(400)
        self.custom_context.update(self.default_context)
        self.analyze_headers()
        self.analyze_query_string()

    def dynamic_unimplemented_method_guard(self):
        if self.request.method.lower() not in self.methods:
            self._unimplemented_method()

    def log_request(self):
        logging.debug('Received request:\n%s' % self.request.__dict__)

    def add_params(self, context):
        for key, param in self.custom_params.items():
            if isinstance(param, PathParam):
                context[key] = _safe_path_split(self.request.path)[param.index]
            if isinstance(param, HeaderParam):
                context[key] = self.request.headers.get(param.key.title())
            if isinstance(param, QueryStringParam):
                context[key] = self.get_query_argument(param.key)
        return context

    def render_template(self):
        source_text = None
        is_binary = False

        is_response_str = isinstance(self.custom_response, str)
        template_engine = _detect_engine(self.custom_response, 'response', default=self.definition_engine)

        if is_response_str:
            source_text = self.custom_response
        elif not self.custom_response:
            source_text = ''
            is_response_str = True
        elif 'body' in self.custom_response:
            source_text = self.custom_response['body']
            is_response_str = True
        else:
            return ''

        if len(source_text) > 1 and source_text[0] == '@':
            template_path = self.resolve_relative_path(source_text)
            if template_path is None:
                return None
            with open(template_path, 'rb') as file:
                logging.info('Reading template file from path: %s' % template_path)
                source_text = file.read()
                try:
                    source_text = source_text.decode('utf-8')
                    logging.debug('Template file text: %s' % source_text)
                except UnicodeDecodeError:
                    is_binary = True
                    logging.debug('Template file is binary. Templating disabled.')
            is_response_str = False

        compiled = None
        if is_binary or ('useTemplating' in self.custom_response and self.custom_response['useTemplating'] is False):
            compiled = source_text
        else:
            if template_engine == PYBARS:
                from mockintosh.hbs.methods import uuid, fake, random_integer
            elif template_engine == JINJA:
                from mockintosh.j2.methods import uuid, fake, random_integer
            else:
                raise UnsupportedTemplateEngine(template_engine, SUPPORTED_ENGINES)

            renderer = TemplateRenderer(
                template_engine,
                source_text,
                inject_objects=self.custom_context,
                inject_methods=[
                    uuid,
                    fake,
                    random_integer
                ],
                add_params_callback=self.add_params
            )
            compiled, _ = renderer.render()

        logging.debug('Render output: %s' % compiled)

        return compiled

    def build_special_request(self):
        request = Request()

        # Details
        request.version = self.request.version
        request.remoteIp = self.request.remote_ip
        request.protocol = self.request.protocol
        request.host = self.request.host
        request.hostName = self.request.host_name
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
            request.queryString[key] = [self.decoder(x) for x in value]
            if len(request.queryString[key]) == 1:
                request.queryString[key] = request.queryString[key][0]

        # Body
        request.body = self.decoder(self.request.body)
        request.files = self.request.files

        # Form Data
        for key, value in self.request.body_arguments.items():
            request.formData[key] = [self.decoder(x) for x in value]
            if len(request.formData[key]) == 1:
                request.formData[key] = request.formData[key][0]

        return request

    def build_special_response(self):
        response = Response()

        response.status = self._status_code
        response.headers = self._headers
        if not hasattr(self, 'rendered_body'):
            self.rendered_body = None
        response.body = self.rendered_body

        return response

    def update_response(self):
        self._status_code = self.special_response.status
        self._headers = self.special_response.headers
        self.rendered_body = self.special_response.body
        self._write_buffer = []
        if self.rendered_body is None:
            self.rendered_body = ''
        if self.should_write():
            self.write(self.rendered_body)

    def determine_status_code(self):
        status_code = None
        if 'status' in self.custom_response:
            if isinstance(self.custom_response['status'], str):
                renderer = TemplateRenderer(
                    self.definition_engine,
                    self.custom_response['status'],
                    inject_objects=self.custom_context,
                    inject_methods=[],
                    add_params_callback=self.add_params
                )
                compiled, _ = renderer.render()
                status_code = int(compiled)
            else:
                status_code = self.custom_response['status']
        else:
            status_code = 200
        self.set_status(status_code)

    def analyze_headers(self):
        if SPECIAL_CONTEXT not in self.initial_context or 'headers' not in self.initial_context[SPECIAL_CONTEXT]:
            return

        for header_key, header in self.initial_context[SPECIAL_CONTEXT]['headers'].items():
            if header_key.title() in self.request.headers._dict:
                if header['type'] == 'regex':
                    match = re.match(header['regex'], self.request.headers.get(header_key))
                    if match is not None:
                        for i, key in enumerate(header['args']):
                            self.custom_context[key] = match.group(i + 1)

    def analyze_query_string(self):
        if SPECIAL_CONTEXT not in self.initial_context or 'queryString' not in self.initial_context[SPECIAL_CONTEXT]:
            return

        for key, value in self.initial_context[SPECIAL_CONTEXT]['queryString'].items():
            if key in self.request.query_arguments:
                if value['type'] == 'regex':
                    match = re.match(value['regex'], self.get_query_argument(key))
                    if match is not None:
                        for i, key in enumerate(value['args']):
                            self.custom_context[key] = match.group(i + 1)

    def determine_headers(self):
        if self.custom_endpoint_id is not None:
            self.set_header('x-%s-endpoint-id' % PROGRAM.lower(), self.custom_endpoint_id)

        if 'headers' in self.globals:
            for key, value in self.globals['headers'].items():
                self.set_header(key, value)

        if not isinstance(self.custom_response, dict) or 'headers' not in self.custom_response:
            return

        for key, value in self.custom_response['headers'].items():
            value_list = None
            if isinstance(value, list):
                value_list = value

            if isinstance(value, str):
                value_list = [value]

            new_value_list = []
            for value in value_list:
                renderer = TemplateRenderer(
                    self.definition_engine,
                    value,
                    inject_objects=self.custom_context,
                    inject_methods=[],
                    add_params_callback=self.add_params
                )
                new_value, _ = renderer.render()
                new_value_list.append(new_value)

            for value in new_value_list:
                if key.title() == 'Set-Cookie':
                    value_splitted = value.split('=')
                    value_splitted[1] = urllib.parse.quote_plus(value_splitted[1])
                    self.set_cookie(value_splitted[0], value_splitted[1])
                else:
                    self.set_header(key, value)

    def match_alternative(self):
        if self.should_cors():
            self.respond_cors()
            return

        if not self.__class__.__name__ == 'ErrorHandler':
            self.alternatives = self.methods[self.request.method.lower()]

        response = None
        params = None
        context = None
        for alternative in self.alternatives:
            fail = False

            # Headers
            if 'headers' in alternative:
                for key, value in alternative['headers'].items():
                    request_header_val = self.request.headers.get(key.title())
                    if key.title() not in self.request.headers._dict:
                        fail = True
                        break
                    if value == request_header_val:
                        continue
                    value = '^%s$' % value
                    match = re.match(value, request_header_val)
                    if match is None:
                        fail = True
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
                        fail = True
                        break
                    if key not in self.request.query_arguments:
                        fail = True
                        break
                    if value == request_query_val:
                        continue
                    value = '^%s$' % value
                    match = re.match(value, request_query_val)
                    if match is None:
                        fail = True
                        break
                if fail:
                    continue

            # Body
            if 'body' in alternative:
                if 'schema' in alternative['body']:
                    json_schema = alternative['body']['schema']
                    if isinstance(json_schema, str) and len(json_schema) > 1 and json_schema[0] == '@':
                        json_schema_path = self.resolve_relative_path(json_schema)
                        with open(json_schema_path, 'r') as file:
                            logging.info('Reading JSON schema file from path: %s' % json_schema_path)
                            json_schema = json.load(file)
                            logging.debug('JSON schema: %s' % json_schema)
                    body = self.request.body.decode('utf-8')
                    json_data = None

                    if body and json_schema:
                        try:
                            json_data = json.loads(body)
                        except json.decoder.JSONDecodeError:
                            fail = True
                            break

                    if json_schema:
                        try:
                            jsonschema.validate(instance=json_data, schema=json_schema)
                        except jsonschema.exceptions.ValidationError:
                            fail = True
                            break

            if self.should_cors():
                self.respond_cors()
            else:
                self.set_cors_headers()

            _id = alternative['id']
            response = alternative['response']
            params = alternative['params']
            context = alternative['context']
            return _id, response, params, context

        self.set_status(404)
        self.finish()

    def trigger_interceptors(self):
        for interceptor in self.interceptors:
            interceptor(self.special_request, self.special_response)

    def finish(self, chunk: Optional[Union[str, bytes, dict]] = None) -> "Future[None]":
        if self._status_code not in (204, 500):
            if not hasattr(self, 'special_response'):
                self.special_response = self.build_special_response()
            self.trigger_interceptors()
            if self.interceptors:
                self.update_response()
        super().finish(chunk)

    def should_write(self):
        return not hasattr(self, 'custom_response') or (
            'body' in self.custom_response or isinstance(self.custom_response, str)
        )

    def decoder(self, string):
        try:
            return string.decode('utf-8')
        except UnicodeDecodeError:
            return string.decode('latin-1')

    def resolve_relative_path(self, source_text):
        relative_path = None
        orig_relative_path = source_text[1:]
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
        if 'message' in kwargs and kwargs['message']:
            self.finish(kwargs['message'])
        else:
            self.finish()

    def respond_cors(self):
        if ORIGIN not in self.request.headers._dict:
            # Invalid CORS preflight request
            self.set_status(404)
            self.finish()

        self.set_cors_headers()
        self.set_status(204)
        self.finish()

    def set_cors_headers(self):
        if ORIGIN in self.request.headers._dict:
            self.set_header('access-control-allow-methods', 'DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT')
            origin = self.request.headers.get(ORIGIN)
            self.set_header('access-control-allow-origin', origin)

            if AC_REQUEST_HEADERS in self.request.headers._dict:
                ac_request_headers = self.request.headers.get(AC_REQUEST_HEADERS)
                self.set_header('access-control-allow-headers', ac_request_headers)

    def set_default_headers(self):
        self.set_header('Server', '%s/%s' % (
            PROGRAM.capitalize(),
            mockintosh.__version__
        ))

    def should_cors(self):
        return not self.__class__.__name__ == 'ErrorHandler' and (
            self.is_options and self.request.method.lower() not in self.methods.keys()
        )


class Request():

    def __init__(self):
        self.version = None
        self.remoteIp = None
        self.protocol = None
        self.host = None
        self.hostName = None
        self.uri = None
        self.method = None
        self.path = None
        self.headers = {}
        self.queryString = {}
        self.body = None
        self.files = {}
        self.formData = {}


class Response():

    def __init__(self):
        self.status = None
        self.headers = {}
        self.body = None
