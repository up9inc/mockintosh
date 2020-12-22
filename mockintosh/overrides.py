#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains overriden Tornado classes.
"""

from typing import (
    Dict,
    Any,
    Optional,
    List,
    Type,
)

import tornado.web
from tornado import httputil
from tornado.routing import (
    _RuleList,
)
from tornado.web import (
    OutputTransform,
    _HandlerDelegate,
)

from mockintosh.handlers import GenericHandler


class Application(tornado.web.Application):

    def __init__(
        self,
        handlers: Optional[_RuleList] = None,
        default_host: Optional[str] = None,
        transforms: Optional[List[Type["OutputTransform"]]] = None,
        **settings: Any
    ) -> None:
        self.interceptors = settings.get('interceptors')
        super().__init__(handlers, default_host, transforms, **settings)

    def get_handler_delegate(
        self,
        request: httputil.HTTPServerRequest,
        target_class: Type[tornado.web.RequestHandler],
        target_kwargs: Optional[Dict[str, Any]] = None,
        path_args: Optional[List[bytes]] = None,
        path_kwargs: Optional[Dict[str, bytes]] = None,
    ) -> "_HandlerDelegate":
        if target_class.__name__ == 'ErrorHandler':
            target_class = ErrorHandler
            target_kwargs['interceptors'] = self.interceptors
        return tornado.web._HandlerDelegate(
            self, request, target_class, target_kwargs, path_args, path_kwargs
        )


class ErrorHandler(GenericHandler):
    """Generates an error response with ``status_code`` for all requests."""

    def initialize(self, status_code: int, interceptors: list) -> None:
        self.alternatives = ()
        self.interceptors = interceptors
        self.special_request = self.build_special_request()
        self.special_response = self.build_special_response()
        self.special_response.status = status_code
        self.set_status(status_code)

    def prepare(self) -> None:
        pass

    def check_xsrf_cookie(self) -> None:
        pass
