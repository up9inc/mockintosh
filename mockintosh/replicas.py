#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes that replicates some other classes from imported packages in a certain way.
"""

import json
import logging


class _NotParsedJSON():
    """Class to determine wheter the request body is parsed into JSON or not."""
    pass


class Request():
    """Class that defines the `Request` object which is being injected into the response template."""

    def __init__(self) -> None:
        self.version = None
        self.remoteIp = None
        self.protocol = None
        self.host = None
        self.hostName = None
        self.uri = None
        self.method = None
        self.path = None
        self.headers = {}
        self.queryString = {}
        self.body = {}
        self._json = _NotParsedJSON()

    @property
    def json(self) -> [None, dict]:
        if isinstance(self._json, _NotParsedJSON):
            try:
                self._json = json.loads(self.body)
            except json.JSONDecodeError:
                logging.warning('Failed to decode request body to JSON:\n%s', self.body)
                self._json = None
        return self._json


class Response():
    """Class that defines the `Response` object which is being used by the interceptors."""

    def __init__(self) -> None:
        self.status = None
        self.headers = {}
        self.body = None
