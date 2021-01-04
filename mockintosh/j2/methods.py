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

from jinja2.utils import contextfunction

from mockintosh.methods import _jinja_add_varname, _jinja_add_regex_context


def fake():
    # Fake fake :)
    pass


@contextfunction
def reg_ex(context, regex, *args, **kwargs):
    if context['scope'] == 'path':
        for arg in args:
            _jinja_add_varname(context, arg)
    else:
        _jinja_add_regex_context(context, context['scope'], context['key'], regex, *args)
    return regex


class Random():

    def __init__(self):
        self.int = self._int
        self.float = self._float
        self.hex = self._hex
        self.ascii = self._ascii

    def _int(self, minimum, maximum):
        return random.randint(minimum, maximum)

    def _float(self, minimum, maximum, precision):
        return round(random.uniform(minimum, maximum), precision)

    def alphanum(self, length):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def _hex(self, length):
        return binascii.b2a_hex(os.urandom(length))

    def uuid4(self):
        return uuid4()

    def _ascii(self, length):
        return ''.join(random.choices(string.ascii_letters, k=length))
