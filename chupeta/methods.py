#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains common methods.
"""

import re
import logging
from functools import wraps

from chupeta.constants import PYBARS, JINJA


def _safe_path_split(path):
    return re.split(r'/(?![^{{}}]*}})', path)


def _to_camel_case(snake_case):
    components = snake_case.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def _detect_engine(data, context='config'):
    template_engine = PYBARS
    if 'templatingEngine' in data and data['templatingEngine'].lower() == JINJA.lower():
        template_engine = JINJA
    logging.info('Templating engine (%s) is: %s' % (context, template_engine))
    return template_engine
