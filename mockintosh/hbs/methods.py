#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains methods to be injected into Handlebars template engine.
"""

import re
import random
import string
import os
import binascii
import time
import html
import json
from datetime import datetime
from datetime import timedelta
from uuid import uuid4

from jsonpath_ng import parse as jsonpath_parse
from pybars import PybarsError
from faker import Faker

from mockintosh.helpers import _handlebars_add_to_context


def fake():
    # Fake fake :)
    raise NotImplementedError


def reg_ex(this, regex, *args, **kwargs):
    if this.context['scope'] == 'path':
        for arg in args:
            this.context[arg] = None
    else:
        if this.context['scope'] == 'bodyText':
            pattern = re.compile(regex)
            if pattern.groups == 0:
                regex = '(%s)' % regex
        _type = 'regex'
        _handlebars_add_to_context(
            this.context,
            this.context['scope'],
            this.context['key'],
            {
                'type': _type,
                'regex': regex,
                'args': args
            }
        )
    return regex


def json_path(this, data, path):
    if data is None:
        raise PybarsError('JSON decode failure!')
    jsonpath_expr = jsonpath_parse(path)
    match = jsonpath_expr.find(data)
    if len(match) < 1:
        return ''
    value = match[0].value
    if value is None:
        value = 'null'
    return value


def counter(this, name):
    number = 0
    if name in this.context:
        number = this.context[name]
    number += 1
    _handlebars_add_to_context(
        this.context,
        'counters',
        name,
        number
    )
    return number


def escape_html(this, text):
    return html.escape(text)


def env(this, name, default):
    return os.environ.get(name, default)


def tojson(this, text):
    return json.dumps(text) \
        .replace(u'<', u'\\u003c') \
        .replace(u'>', u'\\u003e') \
        .replace(u'&', u'\\u0026') \
        .replace(u"'", u'\\u0027')


def array(this, *args):
    return [*args]


def replace(this, text, old, new, count=None):
    if count is None:
        count = -1
    text = text.replace(str(old), str(new))
    return text


class Random():

    def __init__(self):
        self.int = self._int
        self.float = self._float
        self.hex = self._hex
        self.ascii = self._ascii

    def _int(self, this, minimum, maximum):
        return random.randint(int(minimum), int(maximum))

    def _float(self, this, minimum, maximum, precision):
        return round(random.uniform(float(minimum), float(maximum)), precision)

    def alphanum(self, this, length):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def _hex(self, this, length):
        return binascii.b2a_hex(os.urandom(int(length / 2))).decode('utf-8')

    def uuid4(self, this):
        return uuid4()

    def _ascii(self, this, length):
        return ''.join(random.choices(string.ascii_letters, k=length))


class Date():

    def timestamp(self, this, shift=0):
        return round(time.time()) + shift

    def ftimestamp(self, this, shift=0.0, precision=3):
        return round(time.time() + shift, precision)

    def date(
        self,
        this,
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


class HbsFaker(Faker):
    def __getattr__(self, name):
        attr = Faker.__getattr__(self, name)
        if hasattr(attr, '__call__'):
            def newfunc(this, *args, **kwargs):
                result = attr(*args, **kwargs)
                return result
            return newfunc
        else:  # pragma: no cover
            return attr
