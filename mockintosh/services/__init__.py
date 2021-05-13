#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains common.
"""

from abc import abstractmethod


class ImplService:

    @abstractmethod
    def destroy(self):
        raise NotImplementedError
