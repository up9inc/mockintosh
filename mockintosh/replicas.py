#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes that replicates some other classes from imported packages in a certain way.
"""

import json
import logging
from urllib.parse import urlencode
from http.client import responses

from mockintosh.methods import _b64encode
from mockintosh.constants import BASE64


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

    @property
    def json(self) -> [None, dict]:
        if isinstance(self._json, _NotParsedJSON):
            try:
                self._json = json.loads(self.body)
            except json.JSONDecodeError:
                logging.warning('Failed to decode request body to JSON:\n%s', self.body)
                self._json = None
        return self._json

    def _har(self) -> dict:
        qs = urlencode(self.queryString)

        extracted_keys = []
        headers = []
        for key, value in self.headers.items():
            if key.lower() in extracted_keys:
                continue
            extracted_keys.append(key.lower())
            headers.append({
                'name': key,
                'value': value
            })

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
            post_data = {}
            if isinstance(self.body, dict):
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
            elif isinstance(self.body, str):
                post_data = {
                    "mimeType": self.mimeType,
                    "params": [],
                    "text": self.body
                }
                if self.bodyType == BASE64:
                    post_data['_encoding'] = BASE64

            data['postData'] = post_data

        return data


class Response():
    """Class that defines the `Response` object which is being used by the interceptors."""

    def __init__(self) -> None:
        self.status = None
        self.headers = {}
        self.body = None
        self.bodySize = 0

    def _har(self) -> dict:
        headers = []
        for key, value in self.headers.items():
            headers.append({
                'name': key.title(),
                'value': value
            })

        body = '' if self.body is None else self.body
        content = {
            "size": self.bodySize,
            "mimeType": self.headers['Content-Type'] if 'Content-Type' in self.headers else "text/html; charset=utf-8",
            "text": body
        }
        if isinstance(content['text'], (bytes, bytearray)):
            content['text'] = _b64encode(content['text'])
            content['encoding'] = BASE64

        return {
            "status": self.status,
            "statusText": responses[self.status],
            "httpVersion": "HTTP/1.1",
            "cookies": [],
            "headers": headers,
            "content": content,
            "redirectURL": "",
            "headersSize": -1,
            "bodySize": self.bodySize
        }
