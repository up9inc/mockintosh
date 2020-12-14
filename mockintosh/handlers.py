#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains request handlers.
"""

import os
import logging
import inspect

import yaml
import tornado.web
from tornado.web import HTTPError

from mockintosh.constants import SUPPORTED_ENGINES, PYBARS, JINJA
from mockintosh.exceptions import UnsupportedTemplateEngine
from mockintosh.templating import TemplateRenderer
from mockintosh.params import PathParam
from mockintosh.methods import _safe_path_split, _detect_engine
from mockintosh.exceptions import UnrecognizedConfigFileFormat


class GenericHandler(tornado.web.RequestHandler):

    def initialize(self, method, response, params, context, definition_engine):
        self.custom_response = response
        self.custom_method = method.lower()
        self.custom_params = params
        self.definition_engine = definition_engine

        self.initial_context = context
        self.custom_request = self.build_custom_request()
        self.default_context = {
            'request': self.custom_request
        }
        self.custom_context = {}

    def super_verb(self, *args):
        self.populate_context(*args)
        self.determine_status_code()
        self.log_request()
        self.dynamic_unimplemented_method_guard()
        self.write(self.render_template())

    def get(self, *args):
        self.super_verb(*args)

    def post(self, *args):
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

    def dynamic_unimplemented_method_guard(self):
        if self.custom_method != inspect.stack()[2][3]:
            self._unimplemented_method()

    def log_request(self):
        logging.debug('Received request:\n%s' % self.request.__dict__)

    def add_params(self, context):
        for key, param in self.custom_params.items():
            if isinstance(param, PathParam):
                context[key] = _safe_path_split(self.request.path)[param.index]
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
            if body[0] == '@' and os.path.isfile(body[1:]):
                template_path = body[1:]
                with open(template_path, 'r') as file:
                    logging.info('Reading template file from path: %s' % template_path)
                    source_text = file.read()
                    logging.debug('Template file text: %s' % source_text)
            else:
                source_text = body
        else:
            return ''

        compiled = None
        if not is_response_str and (
            'useTemplating' in self.custom_response and self.custom_response['useTemplating'] is False
        ):
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

    def build_custom_request(self):
        custom_request = Request()
        custom_request.path = self.request.path
        for key, value in self.request.query_arguments.items():
            custom_request.queryString[key] = [x.decode('utf-8') for x in value]
            if len(custom_request.queryString[key]) == 1:
                custom_request.queryString[key] = custom_request.queryString[key][0]
        return custom_request

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


class Request():

    def __init__(self):
        self.path = None
        self.queryString = {}