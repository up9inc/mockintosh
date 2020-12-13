#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains methods to be injected into Jinja2 template engine.
"""

import random
from uuid import uuid4

from jinja2.utils import contextfunction

from chupeta.methods import _jinja_add_varname


def fake():
    # Fake fake :)
    pass


def random_integer(minimum, maximum):
    return random.randint(minimum, maximum)


def uuid():
    return uuid4()


@contextfunction
def reg_ex(context, regex, *args, **kwargs):
    for arg in args:
        _jinja_add_varname(context, arg)
    return regex
