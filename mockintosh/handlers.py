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
import inspect
import urllib
from typing import (
    Union,
    Optional
)

import yaml
import tornado.web
import jsonschema
from tornado.web import HTTPError
from tornado.concurrent import Future

from mockintosh.constants import PROGRAM, SUPPORTED_ENGINES, PYBARS, JINJA, SPECIAL_CONTEXT
from mockintosh.exceptions import UnsupportedTemplateEngine
from mockintosh.templating import TemplateRenderer
from mockintosh.params import PathParam, HeaderParam, QueryStringParam
from mockintosh.methods import _safe_path_split, _detect_engine
from mockintosh.exceptions import UnrecognizedConfigFileFormat


class GenericHandler(tornado.web.RequestHandler):

    def initialize(self, method, alternatives, _globals, definition_engine, interceptors):
        self.alternatives = alternatives
        self.globals = _globals
        self.custom_method = method.lower()
        self.definition_engine = definition_engine
        self.interceptors = interceptors

        self.special_request = self.build_special_request()
        self.default_context = {
            'request': self.special_request
        }
        self.custom_context = {}

    def super_verb(self, *args):
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
        self.dynamic_unimplemented_method_guard()
        self.rendered_body = self.render_template()
        self.special_response = self.build_special_response()
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
        if self.custom_method != inspect.stack()[2][3]:
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
        response = None

        is_response_str = isinstance(self.custom_response, str)
        template_engine = _detect_engine(self.custom_response, 'response', default=self.definition_engine)

        if is_response_str:
            source_text = self.custom_response
        elif not self.custom_response:
            source_text = ''
            is_response_str = True
        elif 'body' in self.custom_response:
            body = self.custom_response['body']
            if len(body) > 1 and body[0] == '@' and os.path.isfile(body[1:]):
                template_path = body[1:]
                with open(template_path, 'r') as file:
                    logging.info('Reading template file from path: %s' % template_path)
                    source_text = file.read()
                    logging.debug('Template file text: %s' % source_text)
            else:
                is_response_str = True
                source_text = body
        else:
            return ''

        compiled = None
        if 'useTemplating' in self.custom_response and self.custom_response['useTemplating'] is False:
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

        if is_response_str:
            return compiled
        else:
            try:
                response = yaml.safe_load(compiled)
                logging.info('Template is a valid YAML.')
            except (yaml.scanner.ScannerError, yaml.parser.ParserError) as e:
                raise UnrecognizedConfigFileFormat(
                    'Template is neither a JSON nor a YAML!',
                    compiled,
                    str(e)
                )

        return response

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
            request.queryString[key] = [x.decode('utf-8') for x in value]
            if len(request.queryString[key]) == 1:
                request.queryString[key] = request.queryString[key][0]

        # Body
        request.body = self.request.body.decode('utf-8')
        request.files = self.request.files

        # Form Data
        for key, value in self.request.body_arguments.items():
            request.formData[key] = [x.decode('utf-8') for x in value]
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
                    body = self.request.body.decode('utf-8')
                    json_data = None

                    try:
                        json_data = json.loads(body)
                    except json.decoder.JSONDecodeError:
                        self.set_status(404)
                        self.finish()

                    try:
                        jsonschema.validate(instance=json_data, schema=json_schema)
                    except jsonschema.exceptions.ValidationError:
                        self.set_status(404)
                        self.finish()

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
        if not self._status_code == 500:
            if not hasattr(self, 'special_response'):
                self.special_response = self.build_special_response()
            self.trigger_interceptors()
            self.update_response()
        super().finish(chunk)


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
