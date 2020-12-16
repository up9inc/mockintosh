#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains methods to be injected into Jinja2 template engine.
"""

import random
from uuid import uuid4

from jinja2.utils import contextfunction

from mockintosh.methods import _jinja_add_varname, _jinja_add_regex_context


def fake():
    # Fake fake :)
    pass


def random_integer(minimum, maximum):
    return random.randint(minimum, maximum)


def uuid():
    return uuid4()


@contextfunction
def reg_ex(context, regex, *args, **kwargs):
    if context['scope'] == 'path':
        for arg in args:
            _jinja_add_varname(context, arg)
    else:
        _jinja_add_regex_context(context, context['scope'], context['key'], regex, *args)
    return regex
