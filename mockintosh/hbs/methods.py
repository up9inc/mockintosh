#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains methods to be injected into Handlebars template engine.
"""

import random
from uuid import uuid4

from mockintosh.constants import SPECIAL_CONTEXT
from mockintosh.methods import _handlebars_add_to_context


def fake(this, fake, attr):
    return getattr(fake, attr)()


def random_integer(this, minimum, maximum):
    return random.randint(minimum, maximum)


def uuid(this):
    return uuid4()


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


def counter(this, name):
    number = 0
    if 'counters' in this.context[SPECIAL_CONTEXT] and name in this.context[SPECIAL_CONTEXT]['counters']:
        number = this.context[SPECIAL_CONTEXT]['counters'][name]
    number += 1
    _handlebars_add_to_context(
        this.context,
        'counters',
        name,
        number
    )
    return number
