#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes that replicates some other classes from imported packages in a certain way.
"""

import json
import logging
from urllib.parse import unquote, urlencode
from http.client import responses
from pathlib import PurePosixPath
from typing import (
    Union
)

from mockintosh.helpers import _b64encode
from mockintosh.constants import BASE64


class _NotParsedJSON:
    """Class to determine wheter the request body is parsed into JSON or not."""
    pass


class _RequestPath:

    def __init__(self, path: str) -> None:
        self.path = path
        self.segments = PurePosixPath(unquote(self.path)).parts

    def __repr__(self):
        return self.path

    def __str__(self):
        return self.__repr__()

    def __getitem__(self, key):
        return self.segments[int(key)]

    def __eq__(self, other):
        return self.path == other

    def __ne__(self, other):  # pragma: no cover
        return self.path != other


class Request:
    """Class that defines the `Request` object which is being injected into the response template."""

    def __init__(self) -> None:
        self.version = None
        self.remoteIp = None
        self.protocol = None
        self.host = None
        self.hostName = None
        self.port = None
        self.uri = None
        self.method = None
        self.path = None
        self.headers = {}
        self.queryString = {}
        self.body = {}
        self.bodyType = {}
        self.bodySize = 0
        self._json = _NotParsedJSON()
        self.mimeType = None

    def set_path(self, path: str) -> None:
        self.path = _RequestPath(path)

    @property
    def json(self) -> [None, dict]:
        if isinstance(self._json, _NotParsedJSON):
            try:
                self._json = json.loads(self.body)
            except json.JSONDecodeError:
                logging.warning('Failed to decode request body to JSON:\n%s', self.body)
                self._json = None
        return self._json

    def _har_headers(self) -> list:
        extracted_keys = []
        headers = []

        for key, value in self.headers.items():
            if key.lower() in extracted_keys:
                continue
            extracted_keys.append(key.lower())
            headers.append({
                'name': key,
                'value': str(value)
            })

        return headers

    def _har_query_string(self) -> list:
        query_string = []

        for key, value in self.queryString.items():
            value_list = value
            if not isinstance(value_list, list):
                value_list = [value_list]

            for _value in value_list:
                query_string.append({
                    'name': key,
                    'value': _value
                })

        return query_string

    def _har_post_data(self) -> dict:
        post_data = {}
        if isinstance(self.body, dict):
            post_data = self._har_post_data_form()
        elif isinstance(self.body, str):
            post_data = self._har_post_data_plain()

        return post_data

    def _har_post_data_form(self) -> dict:
        post_data = {
            "mimeType": self.mimeType,
            "params": [],
            "text": ""
        }

        for key, value in self.body.items():
            row = {
                'name': key,
                'value': value
            }
            if self.bodyType[key] == BASE64:
                row['_encoding'] = BASE64
            post_data['params'].append(row)

        return post_data

    def _har_post_data_plain(self) -> dict:
        post_data = {
            "mimeType": self.mimeType,
            "params": [],
            "text": self.body
        }

        if self.bodyType == BASE64:
            post_data['_encoding'] = BASE64

        return post_data

    def _har(self) -> dict:
        qs = urlencode(self.queryString)
        headers = self._har_headers()
        query_string = self._har_query_string()

        data = {
            "method": self.method,
            "url": "%s://%s:%s%s%s" % (self.protocol, self.hostName, self.port, self.path, '?' + qs if qs else ''),
            "httpVersion": "HTTP/1.1",
            "cookies": [],
            "headers": headers,
            "queryString": query_string,
            "headersSize": -1,
            "bodySize": self.bodySize
        }

        if self.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            data['postData'] = self._har_post_data()

        return data


class Response:
    """Class that defines the `Response` object which is being used by the interceptors."""

    def __init__(self) -> None:
        self.status = None
        self.headers = {}
        self.body = None
        self.bodySize = 0

    def _har_headers(self) -> list:
        headers = []

        for key, value in self.headers.items():
            headers.append({
                'name': key.title(),
                'value': str(value)
            })

        return headers

    def _har_body(self) -> Union[str, None]:
        return '' if self.body is None else self.body

    def _har_mime_type(self) -> str:
        return self.headers['Content-Type'] if 'Content-Type' in self.headers else "text/html; charset=utf-8"

    def _har_status_text(self) -> Union[str, None]:
        return None if self.status is None else responses[self.status]

    def _har(self) -> dict:
        headers = self._har_headers()
        body = self._har_body()
        content = {
            "size": self.bodySize,
            "mimeType": self._har_mime_type(),
            "text": body
        }

        if isinstance(content['text'], (bytes, bytearray)):
            try:
                content['text'] = content['text'].decode()
            except (AttributeError, UnicodeDecodeError):
                content['text'] = _b64encode(content['text'])
                content['encoding'] = BASE64

        return {
            "status": self.status,
            "statusText": self._har_status_text(),
            "httpVersion": "HTTP/1.1",
            "cookies": [],
            "headers": headers,
            "content": content,
            "redirectURL": "",
            "headersSize": -1,
            "bodySize": self.bodySize
        }


class Consumed:
    """Class that defines the `Consumed` object which is being injected into the producers in the async handlers."""

    def __init__(self) -> None:
        self.key = None
        self.value = None
        self.headers = {}
