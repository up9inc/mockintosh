#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains templating related classes.
"""

import copy
import logging
from os import environ

from jinja2 import Environment, StrictUndefined
from jinja2.exceptions import TemplateSyntaxError, UndefinedError
from pybars import Compiler, PybarsError
from faker import Faker

from mockintosh.constants import PYBARS, JINJA, JINJA_VARNAME_DICT, SPECIAL_CONTEXT
from mockintosh.methods import _to_camel_case
from mockintosh.hbs.methods import HbsFaker, tojson, array, replace
from mockintosh.j2.meta import find_undeclared_variables_in_order

compiler = Compiler()
faker = Faker()
hbs_faker = HbsFaker()

debug_mode = environ.get('MOCKINTOSH_DEBUG', False)


class TemplateRenderer():

    def __init__(
        self,
        engine,
        text,
        inject_objects={},
        inject_methods=[],
        add_params_callback=None,
        fill_undefineds_with=None,
    ):
        self.engine = engine
        self.text = text
        self.inject_objects = inject_objects
        self.inject_methods = inject_methods
        self.inject_methods_name_list = tuple([method.__name__ for method in inject_methods])
        self.add_params_callback = add_params_callback
        self.fill_undefineds_with = fill_undefineds_with
        self.keys_to_delete = []
        self.one_and_only_var = None

    def render(self):
        if self.engine == PYBARS:
            return self.render_handlebars()
        elif self.engine == JINJA:
            return self.render_jinja()

    def render_handlebars(self):
        context, helpers = self.add_globals(compiler._compiler, helpers={})
        try:
            template = compiler.compile(self.text)
            compiled = template(context, helpers=helpers)
        except (PybarsError, TypeError, SyntaxError) as e:
            if self.fill_undefineds_with is not None and str(e).startswith('Could not find variable'):
                var = str(e)[25:-1]
                self.inject_objects[var] = self.fill_undefineds_with
                self.keys_to_delete.append(var)
                if self.one_and_only_var is None:
                    self.one_and_only_var = var
                return self.render_handlebars()
            else:
                if debug_mode:
                    raise NotImplementedError
                else:
                    logging.warning('Handlebars: %s' % e)
                compiled = self.text
        return compiled, context

    def render_jinja(self):
        env = Environment(undefined=StrictUndefined)

        self.add_globals(env)
        if JINJA_VARNAME_DICT not in env.globals:
            env.globals[JINJA_VARNAME_DICT] = {}

        try:
            ast = env.parse(self.text)
            if self.fill_undefineds_with is not None:
                for var in find_undeclared_variables_in_order(ast):
                    env.globals[var] = self.fill_undefineds_with
                    self.keys_to_delete.append(var)
                    if self.one_and_only_var is None:
                        self.one_and_only_var = var
            else:
                for var in find_undeclared_variables_in_order(ast):
                    logging.warning('Jinja2: Could not find variable `%s`' % var)
                    env.globals[var] = '{{%s}}' % var

            template = env.from_string(self.text)
            compiled = template.render()
        except (TemplateSyntaxError, TypeError, UndefinedError) as e:
            if debug_mode:
                raise NotImplementedError
            else:
                logging.warning('Jinja2: %s' % e)
            compiled = self.text

        if SPECIAL_CONTEXT in env.globals:
            env.globals[JINJA_VARNAME_DICT][SPECIAL_CONTEXT] = env.globals[SPECIAL_CONTEXT]
        return compiled, copy.deepcopy(env.globals[JINJA_VARNAME_DICT])

    def add_globals(self, template, helpers=None):
        # To provide the support of both PYBARS and JINJA
        context = {}
        engine = PYBARS
        # It means the template engine is JINJA
        if helpers is None:
            engine = JINJA
            helpers = template.globals
            context = helpers

        if engine == PYBARS:
            self.inject_methods += [
                tojson,
                array,
                replace
            ]

        # Inject the methods:
        for method in self.inject_methods:
            if method.__name__ == 'fake':
                logging.debug('Inject Faker object into the template.')
                if engine == PYBARS:
                    # Workaround to provide Faker support in PYBARS
                    context['fake'] = hbs_faker
                else:
                    context['fake'] = faker
            else:
                helpers[_to_camel_case(method.__name__)] = method

        # Inject the objects:
        for key, value in self.inject_objects.items():
            context[key] = value

        # If any params wants to be injected
        if self.add_params_callback is not None:
            context = self.add_params_callback(context)

        return context, helpers
