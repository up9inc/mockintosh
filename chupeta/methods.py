#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains methods to be injected into template engines.
"""

import random


def hbs_fake(fake, attr):
    return getattr(fake, attr)()


def random_integer(minimum, maximum):
    return random.randint(minimum, maximum)


def regex(regex, *args):
    return regex
