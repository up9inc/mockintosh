#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains common methods.
"""

import re
import logging

from chupeta.constants import PYBARS, JINJA, SHORT_JINJA


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
