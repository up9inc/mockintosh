#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains logging related classes.
"""

from datetime import datetime
from typing import (
    Union
)

from tornado.http1connection import HTTP1ServerConnection

import mockintosh
from mockintosh.constants import PROGRAM
from mockintosh.replicas import Request, Response


def _get_log_root(enabled) -> dict:
    return {
        "log": {
            "_enabled": enabled,
            "version": "1.2",
            "creator": {
                "name": "%s" % PROGRAM.capitalize(),
                "version": "%s" % mockintosh.__version__
            },
            "entries": []
        }
    }


class LogRecord:

    def __init__(
        self,
        service_name: str,
        request_start_datetime: datetime,
        elapsed_time_in_milliseconds: int,
        request: Request,
        response: Response,
        server_connection: Union[HTTP1ServerConnection, None]
    ):
        self.service_name = service_name
        self.request_start_datetime = request_start_datetime
        self.elapsed_time_in_milliseconds = elapsed_time_in_milliseconds
        self.request = request
        self.response = response
        if server_connection is not None and server_connection.stream.socket is not None:
            self.server_ip_address = server_connection.stream.socket.getsockname()[0]
            self.connection = str(server_connection.stream.socket.getsockname()[1])
        else:
            # It branches to here only if there is a proxy in front of Mockintosh
            # and socket connection is not used or the log comes from a non-HTTP service.
            self.server_ip_address = ''
            self.connection = ''

    def json(self) -> dict:
        data = {
            '_serviceName': self.service_name,
            'startedDateTime': self.request_start_datetime.astimezone().isoformat(),
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
            'serverIPAddress': self.server_ip_address,
            'connection': self.connection
        }

        data['serverIPAddress'] = self.server_ip_address
        data['connection'] = self.connection

        return data


class ServiceLogs():
    def __init__(self, name: str):
        self.records = []
        self.enabled = False
        self.name = name

    def is_enabled(self) -> bool:
        return self.enabled

    def add_record(self, record: LogRecord) -> None:
        self.records.append(record)

    def json(self) -> dict:
        data = _get_log_root(self.is_enabled())

        for record in self.records:
            data['log']['entries'].append(record.json())

        return data

    def reset(self) -> None:
        self.records = []


class Logs():
    def __init__(self):
        self.services = []

    def is_enabled(self) -> bool:
        return any(service.is_enabled() for service in self.services)

    def add_service(self, name: str) -> None:
        service_logs = ServiceLogs(name)
        service_logs.parent = self
        self.services.append(service_logs)

    def update_service(self, index: int, name: str) -> None:
        service_logs = self.services[index]
        service_logs.name = name

    def json(self) -> dict:
        data = _get_log_root(self.is_enabled())

        for service in self.services:
            for record in service.records:
                data['log']['entries'].append(record.json())

        data['log']['entries'] = sorted(data['log']['entries'], key=lambda x: x['startedDateTime'], reverse=False)

        return data

    def reset(self) -> None:
        for service in self.services:
            service.records = []
