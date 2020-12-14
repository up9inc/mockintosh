#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains methods to be injected into Handlebars template engine.
"""

import random
from uuid import uuid4


def fake(this, fake, attr):
    return getattr(fake, attr)()


def random_integer(this, minimum, maximum):
    return random.randint(minimum, maximum)


def uuid(this):
    return uuid4()


def reg_ex(this, regex, *args, **kwargs):
    for arg in args:
        this.context[arg] = None
    return regex
