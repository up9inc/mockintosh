#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains methods to be injected into Jinja2 template engine.
"""

import random
from uuid import uuid4


def fake():
    # Fake fake :)
    pass


def random_integer(minimum, maximum):
    return random.randint(minimum, maximum)


def uuid():
    return uuid4()


def reg_ex(this, regex, *args, **kwargs):
    # TODO: Add the ability to capture regex groups (just like in Handlebars)
    return regex
