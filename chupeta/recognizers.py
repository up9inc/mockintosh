#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains config recognizer classes.
"""

import re

from chupeta.constants import SUPPORTED_ENGINES, PYBARS, JINJA
from chupeta.exceptions import UnsupportedTemplateEngine
from chupeta.templating import TemplateRenderer
from chupeta.params import PathParam
from chupeta.methods import _safe_path_split


class PathRecognizer():
    def __init__(self, path, params, engine):
        self.path = path
        self.params = params
        self.engine = engine

    def recognize(self):
        priority = 0
        segments = _safe_path_split(self.path)
        new_segments = []
        for index, segment in enumerate(segments):
            var, new_segment = self.render_segment(segment, index)
            if var is not None:
                param = PathParam(var, index)
                self.params[var] = param
                priority = 2
            if priority == 0 and new_segment != segment:
                priority = 1
            new_segments.append(new_segment)

        return '/'.join(new_segments), priority

    def render_segment(self, text, index):
        var = None

        if self.engine == PYBARS:
            from chupeta.hbs.methods import reg_ex
        elif self.engine == JINJA:
            from chupeta.j2.methods import reg_ex
        else:
            raise UnsupportedTemplateEngine(self.engine, SUPPORTED_ENGINES)

        renderer = TemplateRenderer(
            self.engine,
            text,
            inject_methods=[reg_ex]
        )
        compiled = renderer.render()

        if not compiled:
            match = re.match(r'{{(.*)}}', text)
            if match is not None:
                name = match.group(1).strip()
                compiled = '.*'
                var = name
            else:
                compiled = text
        return var, compiled
