#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains templating related classes.
"""

from jinja2 import Template
from pybars import Compiler

from chupeta.constants import PYBARS, JINJA
from chupeta.exceptions import UnsupportedTemplateEngine

SUPPORTED_ENGINES = (PYBARS, JINJA)
compiler = Compiler()


class TemplateRenderer():
    def __init__(self, engine, text):
        self.engine = engine
        self.text = text
        self.check_engine_support()

    def render(self, globals_callback):
        if self.engine == PYBARS:
            return self.render_handlebars(globals_callback)
        elif self.engine == JINJA:
            return self.render_jinja(globals_callback)
        else:
            raise UnsupportedTemplateEngine(self.engine, SUPPORTED_ENGINES)

    def check_engine_support(self):
        if self.engine not in SUPPORTED_ENGINES:
            raise UnsupportedTemplateEngine(self.engine, SUPPORTED_ENGINES)
        else:
            pass

    def render_handlebars(self, globals_callback):
        compiler = Compiler()
        context, helpers = globals_callback(compiler._compiler, helpers={})
        template = compiler.compile(self.text)
        return template(context, helpers=helpers)

    def render_jinja(self, globals_callback):
        template = Template(self.text)
        globals_callback(template)
        return template.render()
