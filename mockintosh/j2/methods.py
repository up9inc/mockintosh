#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains methods to be injected into Jinja2 template engine.
"""

import re
import random
import string
import os
import binascii
import time
import html
from datetime import datetime
from datetime import timedelta
from uuid import uuid4

from jsonpath_ng import parse as jsonpath_parse
from jinja2.utils import contextfunction
from jinja2.exceptions import TemplateSyntaxError

from mockintosh.helpers import _jinja_add_varname, _jinja_add_to_context


def fake():
    # Fake fake :)
    raise NotImplementedError


@contextfunction
def reg_ex(context, regex, *args, **kwargs):
    if context['scope'] == 'path':
        for arg in args:
            _jinja_add_varname(context, arg)
    else:
        if context['scope'] == 'bodyText':
            pattern = re.compile(regex)
            if pattern.groups == 0:
                regex = '(%s)' % regex
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


def json_path(data, path):
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


def escape_html(text):
    return html.escape(text)


def env(name, default):
    return os.environ.get(name, default)


class Random():

    def __init__(self):
        self.int = self._int
        self.float = self._float
        self.hex = self._hex
        self.ascii = self._ascii

    def _int(self, minimum, maximum):
        return random.randint(int(minimum), int(maximum))

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


class Date():

    def timestamp(self, shift=0):
        return round(time.time()) + shift

    def ftimestamp(self, shift=0.0, precision=3):
        return round(time.time() + shift, precision)

    def date(
        self,
        pattern='%Y-%m-%dT%H:%M:%S.%f',
        seconds=0
    ):
        now = datetime.utcnow()
        shift_time = timedelta(
            seconds=abs(seconds)
        )
        if seconds < 0:
            now = now - shift_time
        else:
            now = now + shift_time
        return now.strftime(pattern)
