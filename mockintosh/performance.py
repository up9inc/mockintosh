#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes for performance profiling.
"""

import random
import time


class PerformanceProfile():

    def __init__(self, ratio, delay=0.0, faults={}):
        self.ratio = ratio
        self.delay = delay
        self.faults = faults

    def trigger(self, status_code):
        if random.uniform(0, 1) <= self.ratio:
            time.sleep(self.delay)
            if self.faults:
                chosen = random.choices(list(self.faults.keys()), weights=self.faults.values(), k=1)[0]
                if chosen == 'PASS':
                    return status_code
                else:
                    return int(chosen) if chosen not in ('RST', 'FIN') else chosen
        return status_code
