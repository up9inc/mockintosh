#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains methods to be injected into template engines.
"""

import random
import re
from functools import wraps


def hbs_fake(fake, attr):
    return getattr(fake, attr)()


def random_integer(minimum, maximum):
    return random.randint(minimum, maximum)


def regex(regex, *args):
    return regex


def _ignore_first_arg(fn):
    @wraps(fn)
    def wrapper(_, /, *args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


def _safe_path_split(path):
    return re.split(r'/(?![^{{}}]*}})', path)
