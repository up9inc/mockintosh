#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains common methods.
"""

import sys
import io
import re
import logging
from contextlib import contextmanager

from mockintosh.constants import PYBARS, JINJA, SHORT_JINJA, JINJA_VARNAME_DICT, SPECIAL_CONTEXT


def _safe_path_split(path):
    return re.split(r'/(?![^{{}}]*}})', path)


def _to_camel_case(snake_case):
    components = snake_case.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def _detect_engine(data, context='config', default=PYBARS):
    template_engine = default
    if 'templatingEngine' in data and (
        data['templatingEngine'].lower() in (JINJA.lower(), SHORT_JINJA)
    ):
        template_engine = JINJA
    logging.debug('Templating engine (%s) is: %s' % (context, template_engine))
    return template_engine


def _handlebars_add_to_context(context, scope, key, value):
    if SPECIAL_CONTEXT not in context:
        context[SPECIAL_CONTEXT] = {}
    if scope not in context[SPECIAL_CONTEXT]:
        context[SPECIAL_CONTEXT][scope] = {}
    context[SPECIAL_CONTEXT][scope][key] = value


def _jinja_add_to_context(context, scope, key, value):
    if SPECIAL_CONTEXT not in context.environment.globals:
        context.environment.globals[SPECIAL_CONTEXT] = {}
    if scope not in context.environment.globals[SPECIAL_CONTEXT]:
        context.environment.globals[SPECIAL_CONTEXT][scope] = {}
    context.environment.globals[SPECIAL_CONTEXT][scope][key] = value


def _jinja_add_varname(context, varname):
    if JINJA_VARNAME_DICT not in context.environment.globals:
        context.environment.globals[JINJA_VARNAME_DICT] = {}
    context.environment.globals[JINJA_VARNAME_DICT][varname] = None


@contextmanager
def _nostderr():
    """Method to suppress the standard error. (use it with `with` statements)
    """
    save_stderr = sys.stderr
    sys.stderr = io.StringIO()
    yield
    sys.stderr = save_stderr


def _import_from(module, name):
    module = __import__(module, fromlist=[name])
    return getattr(module, name)
