#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains the constants.
"""

from os import environ


PROGRAM = 'mockintosh'

PYBARS = 'Handlebars'
JINJA = 'Jinja2'

SHORT_PYBARS = 'hbs'
SHORT_JINJA = 'j2'

SPECIAL_CONTEXT = '%s_special_context' % PROGRAM

JINJA_VARNAME_DICT = 'jinja_varname_dict'

BASE64 = 'base64'

LOGGING_LENGTH_LIMIT = int(environ.get('%s_LOGGING_LENGTH_LIMIT' % PROGRAM, 100))

WARN_GPUBSUB_PACKAGE = 'google-cloud-pubsub Python package is not installed! (gpubsub)'
WARN_AMAZONSQS_PACKAGE = 'boto3 Python package is not installed! (amazonsqs)'
