#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains config recognizer classes.
"""

import re

from pybars import Compiler

from chupeta.params import PathParam
from chupeta.methods import reg_ex, _ignore_first_arg, _safe_path_split


class PathRecognizer():
    def __init__(self, path, params):
        self.path = path
        self.params = params

    def recognize(self):
        segments = _safe_path_split(self.path)
        new_segments = []
        for index, segment in enumerate(segments):
            var, new_segment = self.render_segment(segment)
            if var is not None:
                param = PathParam(var, index)
                self.params[var] = param
            new_segments.append(new_segment)

        return '/'.join(new_segments)

    def render_segment(self, text):
        var = None
        context = {}
        helpers = {}
        helpers['regEx'] = _ignore_first_arg(reg_ex)
        compiler = Compiler()
        template = compiler.compile(text)
        compiled = template(context, helpers=helpers)
        if not compiled:
            match = re.match(r'{{(.*)}}', text)
            if match is not None:
                name = match.group(1).strip()
                context[name] = '.*'
                compiled = template(context, helpers=helpers)
                var = name
            else:
                compiled = text
        return var, compiled
