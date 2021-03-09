#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains logging related classes.
"""

from tornado.http1connection import HTTP1ServerConnection

import mockintosh
from mockintosh.constants import PROGRAM
from mockintosh.replicas import Request, Response


class LogRecord:
    def __init__(
        self,
        request_start_time: int,
        elapsed_time_in_milliseconds: int,
        request: Request,
        response: Response,
        server_connection: HTTP1ServerConnection
    ):
        self.request_start_time = request_start_time
        self.elapsed_time_in_milliseconds = elapsed_time_in_milliseconds
        self.request = request
        self.response = response
        self.server_connection = server_connection

    def json(self):
        data = {
            'startedDateTime': self.request_start_time.isoformat(),
            'time': self.elapsed_time_in_milliseconds,
            'request': self.request._har(),
            'response': self.response._har(),
            'cache': {},
            'timings': {
                'send': 0,
                'receive': 0,
                'wait': self.elapsed_time_in_milliseconds,
                'connect': 0,
                'ssl': 0
            },
            'serverIPAddress': self.server_connection.stream.socket.getsockname()[0],
            'connection': str(self.server_connection.stream.socket.getsockname()[1])
        }
        return data


class EndpointLogs():
    def __init__(self):
        self.records = []

    def add_record(self, record: LogRecord):
        self.records.append(record)

    def json(self):
        data = []
        for record in self.records:
            data.append(record.json())
        return data


class ServiceLogs():
    def __init__(self):
        self.endpoints = []

    def add_endpoint(self):
        endpoint_logs = EndpointLogs()
        endpoint_logs.parent = self
        self.endpoints.append(endpoint_logs)

    def json(self):
        data = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "%s" % PROGRAM.capitalize(),
                    "version": "%s" % mockintosh.__version__
                },
                "entries": []
            }
        }

        for endpoint in self.endpoints:
            data['log']['entries'] += endpoint.json()

        return data


class Logs():
    def __init__(self):
        self.services = []

    def add_service(self):
        service_logs = ServiceLogs()
        service_logs.parent = self
        self.services.append(service_logs)

    def json(self):
        data = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "%s" % PROGRAM.capitalize(),
                    "version": "%s" % mockintosh.__version__
                },
                "entries": []
            }
        }

        for service in self.services:
            for endpoint in service.endpoints:
                data['log']['entries'] += endpoint.json()

        data['log']['entries'] = sorted(data['log']['entries'], key=lambda x: x['startedDateTime'], reverse=False)

        return data

    def reset(self):
        for service in self.services:
            for endpoint in service.endpoints:
                endpoint.records = []
