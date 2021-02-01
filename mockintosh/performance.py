#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes for performance profiling.
"""

import random
import time


class PerformanceProfile():

    def __init__(self, ratio, delay=0.0):
        self.ratio = ratio
        self.delay = delay

    def wait(self):
        if random.uniform(0, 1) <= self.ratio:
            time.sleep(self.delay)
