#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains templating related classes.
"""

import copy
import logging
from os import environ

from jinja2 import Environment, meta
from jinja2.exceptions import TemplateSyntaxError
from pybars import Compiler, PybarsError
from faker import Faker

from mockintosh.constants import SUPPORTED_ENGINES, PYBARS, JINJA, JINJA_VARNAME_DICT, SPECIAL_CONTEXT
from mockintosh.exceptions import UnsupportedTemplateEngine
from mockintosh.methods import _to_camel_case
from mockintosh.hbs.methods import fake as hbs_fake

compiler = Compiler()
faker = Faker()

debug_mode = environ.get('MOCKINTOSH_DEBUG', False)


class TemplateRenderer():

    def __init__(
        self,
        engine,
        text,
        inject_objects={},
        inject_methods=[],
        add_params_callback=None,
        fill_undefineds=False
    ):
        self.engine = engine
        self.text = text
        self.inject_objects = inject_objects
        self.inject_methods = inject_methods
        self.inject_methods_name_list = tuple([method.__name__ for method in inject_methods])
        self.add_params_callback = add_params_callback
        self.fill_undefineds = fill_undefineds

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
        try:
            compiled = template(context, helpers=helpers)
        except PybarsError as e:
            if self.fill_undefineds:
                if debug_mode:
                    raise e
                compiled = self.text
            else:
                compiled = None
        return compiled, context

    def render_jinja(self):
        env = Environment()

        if JINJA_VARNAME_DICT in env.globals:
            env.globals[JINJA_VARNAME_DICT] = {}
        if SPECIAL_CONTEXT in env.globals:
            env.globals[SPECIAL_CONTEXT] = {}
        self.add_globals(env)
        if JINJA_VARNAME_DICT not in env.globals:
            env.globals[JINJA_VARNAME_DICT] = {}

        try:
            if self.fill_undefineds:
                ast = env.parse(self.text)
                for var in meta.find_undeclared_variables(ast):
                    env.globals[var] = '{{%s}}' % var

            template = env.from_string(self.text)
            compiled = template.render()
        except TemplateSyntaxError as e:
            if self.fill_undefineds and debug_mode:
                raise e
            compiled = self.text

        if SPECIAL_CONTEXT in env.globals:
            env.globals[JINJA_VARNAME_DICT][SPECIAL_CONTEXT] = env.globals[SPECIAL_CONTEXT]
        return compiled, copy.deepcopy(env.globals[JINJA_VARNAME_DICT])

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
