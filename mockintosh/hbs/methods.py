#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains methods to be injected into Handlebars template engine.
"""

import random
import string
import os
import binascii
from uuid import uuid4

from jsonpath_ng import parse as jsonpath_parse
from pybars import PybarsError

from mockintosh.methods import _handlebars_add_to_context


def fake(this, fake, attr):
    return getattr(fake, attr)()


def reg_ex(this, regex, *args, **kwargs):
    if this.context['scope'] == 'path':
        for arg in args:
            this.context[arg] = None
    else:
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


def json_path(this, text, path):
    data = text
    if data is None:
        raise PybarsError
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


class Random():

    def __init__(self):
        self.int = self._int
        self.float = self._float
        self.hex = self._hex
        self.ascii = self._ascii

    def _int(self, this, minimum, maximum):
        return random.randint(minimum, maximum)

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
