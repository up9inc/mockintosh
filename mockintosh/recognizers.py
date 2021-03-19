#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains config recognizer classes.
"""

import re

from mockintosh.constants import PYBARS, JINJA
from mockintosh.methods import _safe_path_split
from mockintosh.params import (
    PathParam,
    HeaderParam,
    QueryStringParam,
    BodyTextParam,
    BodyUrlencodedParam,
    BodyMultipartParam
)
from mockintosh.templating import TemplateRenderer


class RecognizerBase():

    def __init__(self, payload, params, all_contexts, engine, scope):
        self.payload = payload
        self.params = params
        self.all_contexts = all_contexts
        self.engine = engine
        self.scope = scope

    def recognize(self):
        if self.scope == 'bodyText':
            key = self.scope
            var, compiled, context = self.render_part(key, self.payload)
            if var is not None:
                param = BodyTextParam(key, var)
                self.params[var] = param
            self.all_contexts.update(context)

            return compiled
        else:
            parts = None
            new_parts = None

            if self.scope == 'path':
                priority = 0
                parts = _safe_path_split(self.payload)
                parts = dict(enumerate(parts))
                new_parts = []
            elif self.scope == 'queryStringAsString':
                parts = {}  # TODO: satisfy logic here
            else:
                parts = self.payload
                new_parts = {}

            for key, value in parts.items():
                var, new_part, context = self.render_part(key, value)
                if var is not None:
                    param = None
                    if self.scope == 'path':
                        param = PathParam(key, var)
                    elif self.scope == 'headers':
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
                if self.scope == 'path':
                    if priority == 0 and new_part != value:
                        priority = 1
                    new_parts.append(new_part)
                else:
                    new_parts[key] = new_part
                self.all_contexts.update(context)

            if self.scope == 'path':
                return '/'.join(new_parts), priority
            else:
                return new_parts

    def render_part(self, key, text):
        text = self.auto_regex(text)
        var = None

        if self.engine == PYBARS:
            from mockintosh.hbs.methods import reg_ex
        elif self.engine == JINJA:
            from mockintosh.j2.methods import reg_ex

        inject_objects = {}
        if self.scope == 'path':
            inject_objects = {'scope': self.scope}
        else:
            inject_objects = {'scope': self.scope, 'key': key}

        renderer = TemplateRenderer(
            self.engine,
            text,
            inject_objects=inject_objects,
            inject_methods=[reg_ex]
        )
        compiled, context = renderer.render()
        if self.engine == PYBARS:
            del context['scope']
            if 'key' in inject_objects:
                del context['key']

        if not compiled:
            match = re.search(r'{{(.*?)}}', text)
            if match is not None:
                name = match.group(1).strip()
                if self.scope == 'path':
                    compiled = '[^/]+'
                else:
                    compiled = '.*'
                var = name
            else:
                compiled = text
        return var, compiled, context

    def auto_regex(self, text):
        if text.strip().startswith('{{') and text.strip().endswith('}}'):
            return text

        matches = re.findall(r'{{(.*?)}}', text)
        if not matches:
            return text

        regex = re.sub(r'\\{\\{(.*?)\\}\\}', '(.*)', re.escape(text))

        params = []
        for match in matches:
            if match.startswith('regEx'):
                return text

            params.append('\'%s\'' % match)

        if self.engine == PYBARS:
            return '{{regEx \'%s\' %s}}' % (regex, ' '.join(params))
        elif self.engine == JINJA:
            return '{{regEx(\'%s\', %s)}}' % (regex, ', '.join(params))


class PathRecognizer(RecognizerBase):

    def __init__(self, path, params, all_contexts, engine):
        super().__init__(path, params, all_contexts, engine, 'path')


class QueryStringAsStringRecognizer(RecognizerBase):
    def __init__(self, path, params, all_contexts, engine):
        super().__init__(path, params, all_contexts, engine, 'queryStringAsString')


class HeadersRecognizer(RecognizerBase):

    def __init__(self, headers, params, all_contexts, engine):
        super().__init__(headers, params, all_contexts, engine, 'headers')


class QueryStringRecognizer(RecognizerBase):

    def __init__(self, query_string, params, all_contexts, engine):
        super().__init__(query_string, params, all_contexts, engine, 'queryString')


class BodyTextRecognizer(RecognizerBase):

    def __init__(self, body_text, params, all_contexts, engine):
        super().__init__(body_text, params, all_contexts, engine, 'bodyText')


class BodyUrlencodedRecognizer(RecognizerBase):

    def __init__(self, urlencoded, params, all_contexts, engine):
        super().__init__(urlencoded, params, all_contexts, engine, 'bodyUrlencoded')


class BodyMultipartRecognizer(RecognizerBase):

    def __init__(self, multipart, params, all_contexts, engine):
        super().__init__(multipart, params, all_contexts, engine, 'bodyMultipart')
