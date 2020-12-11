#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains templating related classes.
"""

from jinja2 import Template
from pybars import Compiler
from faker import Faker

from chupeta.constants import SUPPORTED_ENGINES, PYBARS, JINJA
from chupeta.exceptions import UnsupportedTemplateEngine
from chupeta.methods import hbs_fake, _ignore_first_arg, _to_camel_case

compiler = Compiler()


class TemplateRenderer():
    def __init__(self, engine, text, inject_methods=[], add_params_callback=None):
        self.engine = engine
        self.text = text
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
        compiler = Compiler()
        context, helpers = self.add_globals(compiler._compiler, helpers={})
        template = compiler.compile(self.text)
        return template(context, helpers=helpers)

    def render_jinja(self):
        template = Template(self.text)
        self.add_globals(template)
        return template.render()

    def add_globals(self, template, helpers=None):
        fake = None
        # Create the faker object if `fake` is in the `inject_methods`
        if 'fake' in self.inject_methods_name_list:
            fake = Faker()

        # To provide the support of both PYBARS and JINJA
        context = {}
        if helpers is None:
            helpers = template.globals
            context = helpers

        # Inject the methods:
        for method in self.inject_methods:
            if method.__name__ == 'fake':
                helpers[method.__name__] = fake
            else:
                helpers[_to_camel_case(method.__name__)] = method

        # If any params wants to injected
        if self.add_params_callback is not None:
            context = self.add_params_callback(context)

        # It means the template engine is PYBARS
        if helpers is not None:
            for key, helper in helpers.items():
                # PYBARS calls the methods with an extra and
                # unnecessary `this` argument at the beginning
                if callable(helper):
                    helpers[key] = _ignore_first_arg(helper)

            # Workaround to provide Faker support in PYBARS
            if 'fake' in self.inject_methods_name_list:
                def super_fake(_, /, *args, **kwargs):
                    return hbs_fake(fake, *args, **kwargs)

                helpers['fake'] = super_fake

        return context, helpers
