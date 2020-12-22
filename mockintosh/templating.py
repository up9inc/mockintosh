#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains templating related classes.
"""

import copy
import logging

from jinja2 import Template
from pybars import Compiler
from faker import Faker

from mockintosh.constants import SUPPORTED_ENGINES, PYBARS, JINJA, JINJA_VARNAME_DICT, SPECIAL_CONTEXT
from mockintosh.exceptions import UnsupportedTemplateEngine
from mockintosh.methods import _to_camel_case
from mockintosh.hbs.methods import fake as hbs_fake

compiler = Compiler()
faker = Faker()


class TemplateRenderer():

    def __init__(self, engine, text, inject_objects={}, inject_methods=[], add_params_callback=None):
        self.engine = engine
        self.text = text
        self.inject_objects = inject_objects
        self.inject_methods = inject_methods
        self.inject_methods_name_list = tuple([method.__name__ for method in inject_methods])
        self.add_params_callback = add_params_callback

        self.check_engine_support()

    def render(self):
        if self.engine == PYBARS:
            return self.render_handlebars()
        elif self.engine == JINJA:
            return self.render_jinja()
        else:
            raise UnsupportedTemplateEngine(self.engine, SUPPORTED_ENGINES)

    def check_engine_support(self):
        if self.engine not in SUPPORTED_ENGINES:
            raise UnsupportedTemplateEngine(self.engine, SUPPORTED_ENGINES)
        else:
            pass

    def render_handlebars(self):
        context, helpers = self.add_globals(compiler._compiler, helpers={})
        template = compiler.compile(self.text)
        compiled = template(context, helpers=helpers)
        return compiled, context

    def render_jinja(self):
        template = Template(self.text)
        if JINJA_VARNAME_DICT in template.globals:
            template.globals[JINJA_VARNAME_DICT] = {}
        if SPECIAL_CONTEXT in template.globals:
            template.globals[SPECIAL_CONTEXT] = {}
        self.add_globals(template)
        if JINJA_VARNAME_DICT not in template.globals:
            template.globals[JINJA_VARNAME_DICT] = {}
        compiled = template.render()
        if SPECIAL_CONTEXT in template.globals:
            template.globals[JINJA_VARNAME_DICT][SPECIAL_CONTEXT] = template.globals[SPECIAL_CONTEXT]
        return compiled, copy.deepcopy(template.globals[JINJA_VARNAME_DICT])

    def add_globals(self, template, helpers=None):
        fake = None
        # Create the faker object if `fake` is in the `inject_methods`
        if 'fake' in self.inject_methods_name_list:
            fake = faker

        # To provide the support of both PYBARS and JINJA
        context = {}
        engine = PYBARS
        # It means the template engine is JINJA
        if helpers is None:
            engine = JINJA
            helpers = template.globals
            context = helpers

        # Inject the methods:
        for method in self.inject_methods:
            if method.__name__ == 'fake':
                logging.debug('Inject Faker object into the template.')
                helpers[method.__name__] = fake
            else:
                helpers[_to_camel_case(method.__name__)] = method

        # Inject the objects:
        for key, value in self.inject_objects.items():
            context[key] = value

        # If any params wants to be injected
        if self.add_params_callback is not None:
            context = self.add_params_callback(context)

        # Workaround to provide Faker support in PYBARS
        if engine == PYBARS and 'fake' in self.inject_methods_name_list:
            logging.debug('Use Handlebars version of Faker.')

            def super_fake(this, *args, **kwargs):
                return hbs_fake(this, fake, *args, **kwargs)

            helpers['fake'] = super_fake

        return context, helpers
