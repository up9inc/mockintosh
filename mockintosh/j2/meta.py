#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: Source: https://github.com/jappeace/offertex/blob/master/jinmeta.py
"""

from jinja2 import nodes, meta


def find_undeclared_variables_in_order(ast):
    """
        Returns a list of undeclared variables **IN ORDER**,
        unlike the same function from  jinjia.meta
    """

    undeclared_set = meta.find_undeclared_variables(ast)  # undeclared, unordered
    ordered_nodes = [
        node
        for node in ast.find_all(nodes.Name)  # including declared, but in order
        if node.name in undeclared_set  # filter out declared
    ]

    result = []
    seen = set()

    # remove duplicates
    for node in ordered_nodes:
        name = node.name
        if name in seen:  # pragma: no cover
            continue
        seen.add(name)
        result.append(name)

    return result
