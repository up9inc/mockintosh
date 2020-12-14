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

from mockintosh.constants import PYBARS, JINJA, SHORT_JINJA, JINJA_VARNAME_DICT


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
    logging.info('Templating engine (%s) is: %s' % (context, template_engine))
    return template_engine


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
