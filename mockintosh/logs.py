#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains logging related classes.
"""

from mockintosh.replicas import Request, Response


class LogRecord:
    def __init__(
        self,
        request_start_time: int,
        elapsed_time_in_seconds: int,
        request: Request,
        response: Response
    ):
        self.request_start_time = request_start_time
        self.elapsed_time_in_seconds = elapsed_time_in_seconds
        self.request = request
        self.response = response

    def json(self):
        data = {}
        return data


class BaseLogs():
    def __init__(self, hint: str):
        self.hint = hint

    def json(self):
        data = {}
        return data

    def reset(self):
        if hasattr(self, 'records'):
            self.records = []


class EndpointLogs(BaseLogs):
    def __init__(self, hint: str):
        self.records = []
        super().__init__(hint)

    def add_record(self, record: LogRecord):
        self.records.append(record)


class ServiceLogs(EndpointLogs):
    def __init__(self, hint: str):
        self.endpoints = []
        super().__init__(hint)

    def add_endpoint(self, hint: str):
        endpoint_logs = EndpointLogs(hint)
        endpoint_logs.parent = self
        self.endpoints.append(endpoint_logs)


class Logs(ServiceLogs):
    def __init__(self):
        self.services = []
        super().__init__(None)

    def add_service(self, hint: str):
        service_logs = ServiceLogs(hint)
        service_logs.parent = self
        self.services.append(service_logs)
