#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains methods to be injected into template engines.
"""

from uuid import uuid4
import random
import re
from functools import wraps


def fake():
    # Fake fake :)
    pass


def hbs_fake(fake, attr):
    return getattr(fake, attr)()


def random_integer(minimum, maximum):
    return random.randint(minimum, maximum)


def uuid():
    return uuid4()


def reg_ex(regex, *args):
    return regex


def _ignore_first_arg(fn):
    @wraps(fn)
    def wrapper(_, /, *args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


def _safe_path_split(path):
    return re.split(r'/(?![^{{}}]*}})', path)


def _to_camel_case(snake_case):
    components = snake_case.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])
