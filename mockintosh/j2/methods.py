#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains methods to be injected into Jinja2 template engine.
"""

import random
import string
import os
import binascii
from uuid import uuid4

from jsonpath_ng import parse as jsonpath_parse
from jinja2.utils import contextfunction
from jinja2.exceptions import TemplateSyntaxError

from mockintosh.methods import _jinja_add_varname, _jinja_add_to_context


def fake():
    # Fake fake :)
    pass


@contextfunction
def reg_ex(context, regex, *args, **kwargs):
    if context['scope'] == 'path':
        for arg in args:
            _jinja_add_varname(context, arg)
    else:
        _type = 'regex'
        _jinja_add_to_context(
            context,
            context['scope'],
            context['key'],
            {
                'type': _type,
                'regex': regex,
                'args': args
            }
        )
    return regex


def json_path(text, path):
    data = text
    if data is None:
        raise TemplateSyntaxError('JSON decode failure!', 0)
    jsonpath_expr = jsonpath_parse(path)
    match = jsonpath_expr.find(data)
    if len(match) < 1:
        return ''
    value = match[0].value
    if value is None:
        value = 'null'
    return value


@contextfunction
def counter(context, name):
    number = 0
    if name in context:
        number = context[name]
    number += 1
    _jinja_add_to_context(
        context,
        'counters',
        name,
        number
    )
    return number


class Random():

    def __init__(self):
        self.int = self._int
        self.float = self._float
        self.hex = self._hex
        self.ascii = self._ascii

    def _int(self, minimum, maximum):
        return random.randint(minimum, maximum)

    def _float(self, minimum, maximum, precision):
        return round(random.uniform(float(minimum), float(maximum)), precision)

    def alphanum(self, length):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def _hex(self, length):
        return binascii.b2a_hex(os.urandom(int(length / 2))).decode('utf-8')

    def uuid4(self):
        return uuid4()

    def _ascii(self, length):
        return ''.join(random.choices(string.ascii_letters, k=length))
