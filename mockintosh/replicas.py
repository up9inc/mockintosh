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
            query_string.append({
                'name': key,
                'value': value
            })

        post_data = {}
        if self.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if isinstance(self.body, dict):
                post_data = {
                    "mimeType": "application/x-www-form-urlencoded",
                    "params": [],
                    "text": ""
                }
                for key, value in self.body.items():
                    post_data['params'].append({
                        'name': key,
                        'value': value
                    })
            elif isinstance(self.body, str):
                post_data = {
                    "mimeType": "text/plain",
                    "params": [],
                    "text": self.body
                }

        return {
            "method": self.method,
            "url": "%s://%s:%s%s%s" % (self.protocol, self.hostName, 80, self.path, '?' + qs if qs else ''),
            "httpVersion": "HTTP/1.1",
            "cookies": [],
            "headers": headers,
            "queryString": query_string,
            "postData": post_data,
            "headersSize": 0,
            "bodySize": 0,
            "comment": ""
        }


class Response():
    """Class that defines the `Response` object which is being used by the interceptors."""

    def __init__(self) -> None:
        self.status = None
        self.headers = {}
        self.body = None

    def _har(self) -> dict:
        extracted_keys = []
        headers = []
        for key, value in self.headers.items():
            if key.lower() in extracted_keys:
                continue
            extracted_keys.append(key.lower())
            headers.append({
                'name': key.title(),
                'value': value
            })

        content = {
            "size": 0,
            "compression": 0,
            "mimeType": self.headers['Content-Type'] if 'Content-Type' in self.headers else "text/html; charset=utf-8",
            "text": self.body
        }

        return {
            "status": self.status,
            "statusText": responses[self.status],
            "httpVersion": "HTTP/1.1",
            "cookies": [],
            "headers": headers,
            "content": content,
            "redirectURL": "",
            "headersSize": 0,
            "bodySize": 0
        }
