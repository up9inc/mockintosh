#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains logging related classes.
"""

import socket

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
        port: int
    ):
        self.request_start_time = request_start_time
        self.elapsed_time_in_milliseconds = elapsed_time_in_milliseconds
        self.request = request
        self.response = response
        self.port = port

    def json(self):
        data = {
            'startedDateTime': self.request_start_time.isoformat(),
            'time': self.elapsed_time_in_milliseconds,
            'request': self.request._har(),
            'response': self.response._har(),
            'cache': {},
            'timings': {
                'send': self.elapsed_time_in_milliseconds,
                'receive': self.elapsed_time_in_milliseconds,
                'wait': self.elapsed_time_in_milliseconds,
                'connect': self.elapsed_time_in_milliseconds,
                'ssl': self.elapsed_time_in_milliseconds,
            },
            'serverIPAddress': str(socket.gethostbyname(self.request.hostName)),
            'connection': str(self.port)
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
            'services': []
        }

        for service in self.services:
            data['services'].append(service.json())

        return data

    def reset(self):
        for service in self.services:
            for endpoint in service.endpoints:
                endpoint.records = []
