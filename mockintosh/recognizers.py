#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains config recognizer classes.
"""

import re
from collections import OrderedDict

from mockintosh.constants import SUPPORTED_ENGINES, PYBARS, JINJA
from mockintosh.exceptions import UnsupportedTemplateEngine
from mockintosh.templating import TemplateRenderer
from mockintosh.params import PathParam
from mockintosh.methods import _safe_path_split


class PathRecognizer():

    def __init__(self, path, params, engine):
        self.path = path
        self.params = params
        self.engine = engine

    def recognize(self):
        priority = 0
        segments = _safe_path_split(self.path)
        new_segments = []
        all_contexts = OrderedDict()
        for index, segment in enumerate(segments):
            var, new_segment, context = self.render_segment(segment, index)
            if var is not None:
                param = PathParam(var, index)
                self.params[var] = param
                priority = 2
            if priority == 0 and new_segment != segment:
                priority = 1
            new_segments.append(new_segment)
            all_contexts.update(context)

        return '/'.join(new_segments), priority, all_contexts

    def render_segment(self, text, index):
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
            inject_methods=[reg_ex]
        )
        compiled, context = renderer.render()

        if not compiled:
            match = re.match(r'{{(.*)}}', text)
            if match is not None:
                name = match.group(1).strip()
                compiled = '.*'
                var = name
            else:
                compiled = text
        return var, compiled, context
