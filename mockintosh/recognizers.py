#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains config recognizer classes.
"""

import re

from mockintosh.constants import SUPPORTED_ENGINES, PYBARS, JINJA
from mockintosh.exceptions import UnsupportedTemplateEngine
from mockintosh.templating import TemplateRenderer
from mockintosh.params import PathParam, HeaderParam, QueryStringParam, BodyParam
from mockintosh.methods import _safe_path_split


class PathRecognizer():

    def __init__(self, path, params, all_contexts, engine):
        self.path = path
        self.params = params
        self.all_contexts = all_contexts
        self.engine = engine

    def recognize(self):
        priority = 0
        segments = _safe_path_split(self.path)
        new_segments = []
        for index, segment in enumerate(segments):
            var, new_segment, context = self.render_segment(segment)
            if var is not None:
                param = PathParam(var, index)
                self.params[var] = param
                priority = 2
            if priority == 0 and new_segment != segment:
                priority = 1
            new_segments.append(new_segment)
            self.all_contexts.update(context)

        return '/'.join(new_segments), priority

    def render_segment(self, text):
        var = None

        if self.engine == PYBARS:
            from mockintosh.hbs.methods import reg_ex
        elif self.engine == JINJA:
            from mockintosh.j2.methods import reg_ex
        else:
            raise UnsupportedTemplateEngine(self.engine, SUPPORTED_ENGINES)

        renderer = TemplateRenderer(
            self.engine,
            text,
            inject_objects={'scope': 'path'},
            inject_methods=[reg_ex]
        )
        compiled, context = renderer.render()
        if self.engine == PYBARS:
            del context['scope']

        if not compiled:
            match = re.search(r'{{(.*)}}', text)
            if match is not None:
                name = match.group(1).strip()
                compiled = '.*'
                var = name
            else:
                compiled = text
        return var, compiled, context


class HeadersRecognizer():

    def __init__(self, headers, params, all_contexts, engine):
        self.headers = headers
        self.params = params
        self.all_contexts = all_contexts
        self.engine = engine

    def recognize(self):
        new_headers = {}
        for key, value in self.headers.items():
            var, new_header, context = self.render_header(key, value)
            if var is not None:
                param = HeaderParam(key, var)
                self.params[var] = param
            new_headers[key] = new_header
            self.all_contexts.update(context)

        return new_headers

    def render_header(self, key, text):
        var = None

        if self.engine == PYBARS:
            from mockintosh.hbs.methods import reg_ex
        elif self.engine == JINJA:
            from mockintosh.j2.methods import reg_ex
        else:
            raise UnsupportedTemplateEngine(self.engine, SUPPORTED_ENGINES)

        renderer = TemplateRenderer(
            self.engine,
            text,
            inject_objects={'scope': 'headers', 'key': key},
            inject_methods=[reg_ex]
        )
        compiled, context = renderer.render()
        if self.engine == PYBARS:
            del context['scope']
            del context['key']

        if not compiled:
            match = re.search(r'{{(.*)}}', text)
            if match is not None:
                name = match.group(1).strip()
                compiled = '.*'
                var = name
            else:
                compiled = text
        return var, compiled, context


class QueryStringRecognizer():

    def __init__(self, query_string, params, all_contexts, engine):
        self.query_string = query_string
        self.params = params
        self.all_contexts = all_contexts
        self.engine = engine

    def recognize(self):
        new_headers = {}
        for key, value in self.query_string.items():
            var, new_header, context = self.render_query_element(key, value)
            if var is not None:
                param = QueryStringParam(key, var)
                self.params[var] = param
            new_headers[key] = new_header
            self.all_contexts.update(context)

        return new_headers

    def render_query_element(self, key, text):
        var = None

        if self.engine == PYBARS:
            from mockintosh.hbs.methods import reg_ex
        elif self.engine == JINJA:
            from mockintosh.j2.methods import reg_ex
        else:
            raise UnsupportedTemplateEngine(self.engine, SUPPORTED_ENGINES)

        renderer = TemplateRenderer(
            self.engine,
            text,
            inject_objects={'scope': 'queryString', 'key': key},
            inject_methods=[reg_ex]
        )
        compiled, context = renderer.render()
        if self.engine == PYBARS:
            del context['scope']
            del context['key']

        if not compiled:
            match = re.search(r'{{(.*)}}', text)
            if match is not None:
                name = match.group(1).strip()
                compiled = '.*'
                var = name
            else:
                compiled = text
        return var, compiled, context


class BodyRecognizer():

    def __init__(self, body_text, params, all_contexts, engine):
        self.body_text = body_text
        self.params = params
        self.all_contexts = all_contexts
        self.engine = engine

    def recognize(self):
        key = 'bodyText'
        var, compiled, context = self.render_body(key, self.body_text)
        if var is not None:
            param = BodyParam(key, var)
            self.params[var] = param
        self.all_contexts.update(context)

        return compiled

    def render_body(self, key, text):
        var = None

        if self.engine == PYBARS:
            from mockintosh.hbs.methods import reg_ex
        elif self.engine == JINJA:
            from mockintosh.j2.methods import reg_ex
        else:
            raise UnsupportedTemplateEngine(self.engine, SUPPORTED_ENGINES)

        renderer = TemplateRenderer(
            self.engine,
            text,
            inject_objects={'scope': 'bodyText', 'key': 'bodyText'},
            inject_methods=[reg_ex]
        )
        compiled, context = renderer.render()
        if self.engine == PYBARS:
            del context['scope']
            del context['key']

        if not compiled:
            match = re.search(r'{{(.*)}}', text)
            if match is not None:
                name = match.group(1).strip()
                compiled = '.*'
                var = name
            else:
                compiled = text
        return var, compiled, context
