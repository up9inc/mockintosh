#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes for performance profiling.
"""

import random
import time
from typing import (
    Union
)


class PerformanceProfile():

    def __init__(
        self,
        ratio: Union[float, int],
        delay: Union[float, int] = 0.0,
        faults: Union[dict, None] = None
    ):
        self.ratio = ratio
        self.delay = delay
        self.faults = {} if faults is None else faults

    def trigger(self, status_code: int) -> Union[int, str]:
        if random.uniform(0, 1) <= self.ratio:
            time.sleep(self.delay)
            if self.faults:
                chosen = random.choices(list(self.faults.keys()), weights=self.faults.values(), k=1)[0]
                if chosen == 'PASS':
                    return status_code
                else:
                    return int(chosen) if chosen not in ('RST', 'FIN') else chosen
        return status_code
