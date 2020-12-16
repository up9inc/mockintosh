#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains the constants.
"""

PROGRAM = 'mockintosh'

PYBARS = 'Handlebars'
JINJA = 'Jinja2'

SHORT_PYBARS = 'hbs'
SHORT_JINJA = 'j2'

SUPPORTED_ENGINES = (PYBARS, JINJA)

SPECIAL_CONTEXT = '%s_special_context' % PROGRAM

JINJA_VARNAME_DICT = 'jinja_varname_dict'
