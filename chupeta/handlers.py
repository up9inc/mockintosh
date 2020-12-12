#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains request handlers.
"""

import json
import logging
import inspect

import yaml
import tornado.web
from tornado.web import HTTPError

from chupeta.constants import SUPPORTED_ENGINES, PYBARS, JINJA
from chupeta.exceptions import UnsupportedTemplateEngine
from chupeta.templating import TemplateRenderer
from chupeta.params import PathParam
from chupeta.methods import _safe_path_split, _detect_engine
from chupeta.exceptions import UnrecognizedConfigFileFormat


class GenericHandler(tornado.web.RequestHandler):
    def initialize(self, method, response, params, context):
        self.custom_response = response
        self.custom_method = method.lower()
        self.custom_params = params

        self.initial_context = context
        self.default_context = {
            'request': self.request
        }
        self.custom_context = {}

    def super_verb(self, *args):
        self.populate_context(*args)
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
        template_engine = _detect_engine(self.custom_response, 'response')

        if is_response_str:
            source_text = self.custom_response
        elif 'text' in self.custom_response:
            source_text = self.custom_response['text']
        else:
            template_path = self.custom_response['fromFile']
            with open(template_path, 'r') as file:
                logging.info('Reading template file from path: %s' % template_path)
                source_text = file.read()
                logging.debug('Template file text: %s' % source_text)

        compiled = None
        if not is_response_str and (
            'useTemplating' in self.custom_response and self.custom_response['useTemplating'] is False
        ):
            compiled = source_text
        else:
            if template_engine == PYBARS:
                from chupeta.hbs.methods import uuid, fake, random_integer
            elif template_engine == JINJA:
                from chupeta.j2.methods import uuid, fake, random_integer
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

        valid_json = False
        valid_yaml = False

        if is_response_str:
            return compiled
        else:
            try:
                response = json.loads(compiled)
                valid_json = True
                logging.info('Template is a valid JSON.')
            except json.decoder.JSONDecodeError as e:
                logging.debug('Template is not recognized as a JSON.')
                invalid_json_error_msg = str(e)

            try:
                response = yaml.safe_load(compiled)
                valid_yaml = True
                logging.info('Template is a valid YAML.')
            except yaml.scanner.ScannerError as e:
                logging.debug('Template is not recognized as a YAML.')
                invalid_yaml_error_msg = str(e)

            if not valid_json and not valid_yaml:
                raise UnrecognizedConfigFileFormat(
                    'Template is neither a JSON nor a YAML!',
                    compiled,
                    invalid_json_error_msg,
                    invalid_yaml_error_msg
                )

        return response['body']
