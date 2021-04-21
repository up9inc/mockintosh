#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains config recognizer classes.
"""

from mockintosh.constants import PYBARS, JINJA, SPECIAL_CONTEXT
from mockintosh.templating import TemplateRenderer
from mockintosh.params import (
    HeaderParam,
    QueryStringParam,
    BodyTextParam,
    BodyUrlencodedParam,
    BodyMultipartParam,
    AsyncValueParam,
    AsyncKeyParam,
    AsyncHeadersParam
)
from mockintosh.helpers import _safe_path_split


class RecognizerBase():

    def __init__(self, payload, params, all_contexts, engine, rendering_queue, scope):
        self.payload = payload
        self.params = params
        self.all_contexts = all_contexts
        self.engine = engine
        self.rendering_queue = rendering_queue
        self.scope = scope

    def update_all_contexts(self, context: dict):
        if not self.all_contexts:
            self.all_contexts.update(context)
        else:
            if SPECIAL_CONTEXT in self.all_contexts and SPECIAL_CONTEXT in context:
                self.all_contexts[SPECIAL_CONTEXT].update(context[SPECIAL_CONTEXT])

    def recognize(self):
        if self.scope == 'bodyText':
            key = self.scope
            var, compiled, context = self.render_part(key, self.payload)
            if var is not None:
                param = BodyTextParam(key, var)
                self.params[var] = param
            self.all_contexts.update(context)

            return compiled
        elif self.scope.startswith('async'):
            key = self.scope
            if isinstance(self.payload, dict) and self.scope == 'asyncHeaders':
                result = {}
                for _key, value in self.payload.items():
                    var, compiled, context = self.render_part(_key, value)
                    if var is not None:
                        param = None
                        param = AsyncHeadersParam(key, var)
                        self.params[var] = param
                    self.update_all_contexts(context)
                    result[_key] = compiled

                return result
            else:
                var, compiled, context = self.render_part(key, self.payload)
                if var is not None:
                    param = None
                    if self.scope == 'asyncValue':
                        param = AsyncValueParam(key, var)
                    elif self.scope == 'asyncKey':
                        param = AsyncKeyParam(key, var)
                    self.params[var] = param
                self.update_all_contexts(context)

                return compiled
        else:
            parts = None
            new_parts = None

            if self.scope == 'path':
                priority = 0
                parts = _safe_path_split(self.payload)
                parts = dict(enumerate(parts))
                new_parts = []
            else:
                parts = self.payload
                new_parts = {}

            for key, value in parts.items():
                if not isinstance(value, list):
                    value = [value]
                for el in value:
                    context = {}
                    if self.scope != 'path':
                        _var, key, context = self.render_part(key, key)
                    var, new_part, _context = self.render_part(key, el)
                    context.update(_context)
                    if var is not None:
                        param = None
                        if self.scope == 'headers':
                            param = HeaderParam(key, var)
                        elif self.scope == 'queryString':
                            param = QueryStringParam(key, var)
                        elif self.scope == 'bodyUrlencoded':
                            param = BodyUrlencodedParam(key, var)
                        elif self.scope == 'bodyMultipart':
                            param = BodyMultipartParam(key, var)
                        self.params[var] = param
                        if self.scope == 'path':
                            priority = 2
                    else:
                        if self.scope == 'queryString':
                            param = QueryStringParam(_var, key)
                            self.params[key] = param
                    if self.scope == 'path':
                        if priority == 0 and new_part != el:
                            priority = 1
                        new_parts.append(new_part)
                    else:
                        new_parts[key] = new_part
                    self.all_contexts.update(context)

            if self.scope == 'path':
                return '/'.join(new_parts), priority
            else:
                return new_parts

    def render_part(self, key: str, text: str):
        if self.engine == PYBARS:
            from mockintosh.hbs.methods import reg_ex, env
        elif self.engine == JINJA:
            from mockintosh.j2.methods import reg_ex, env

        inject_objects = {}
        if self.scope == 'path':
            inject_objects = {'scope': self.scope}
        else:
            inject_objects = {'scope': self.scope, 'key': key}

        renderer = TemplateRenderer()
        compiled, context = renderer.render(
            self.engine,
            text,
            self.rendering_queue,
            inject_objects=inject_objects,
            inject_methods=[
                reg_ex,
                env
            ],
            fill_undefineds_with='([^/]+)' if self.scope == 'path' else '(.*)'
        )
        if self.engine == PYBARS:
            del context['scope']
            if 'key' in inject_objects:
                del context['key']
        for key in renderer.keys_to_delete:
            context[key] = None

        return renderer.one_and_only_var, compiled, context


class PathRecognizer(RecognizerBase):

    def __init__(self, path, params, all_contexts, engine, rendering_queue):
        super().__init__(path, params, all_contexts, engine, rendering_queue, 'path')


class HeadersRecognizer(RecognizerBase):

    def __init__(self, headers, params, all_contexts, engine, rendering_queue):
        super().__init__(headers, params, all_contexts, engine, rendering_queue, 'headers')


class QueryStringRecognizer(RecognizerBase):

    def __init__(self, query_string, params, all_contexts, engine, rendering_queue):
        super().__init__(query_string, params, all_contexts, engine, rendering_queue, 'queryString')


class BodyTextRecognizer(RecognizerBase):

    def __init__(self, body_text, params, all_contexts, engine, rendering_queue):
        super().__init__(body_text, params, all_contexts, engine, rendering_queue, 'bodyText')


class BodyUrlencodedRecognizer(RecognizerBase):

    def __init__(self, urlencoded, params, all_contexts, engine, rendering_queue):
        super().__init__(urlencoded, params, all_contexts, engine, rendering_queue, 'bodyUrlencoded')


class BodyMultipartRecognizer(RecognizerBase):

    def __init__(self, multipart, params, all_contexts, engine, rendering_queue):
        super().__init__(multipart, params, all_contexts, engine, rendering_queue, 'bodyMultipart')


class AsyncProducerValueRecognizer(RecognizerBase):

    def __init__(self, value, params, all_contexts, engine, rendering_queue):
        super().__init__(value, params, all_contexts, engine, rendering_queue, 'asyncValue')


class AsyncProducerKeyRecognizer(RecognizerBase):

    def __init__(self, key, params, all_contexts, engine, rendering_queue):
        super().__init__(key, params, all_contexts, engine, rendering_queue, 'asyncKey')


class AsyncProducerHeadersRecognizer(RecognizerBase):

    def __init__(self, headers, params, all_contexts, engine, rendering_queue):
        super().__init__(headers, params, all_contexts, engine, rendering_queue, 'asyncHeaders')
