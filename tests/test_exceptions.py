#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: Contains classes that tests the exceptions thrown by the mock server.
"""

import pytest
from jsonschema.exceptions import ValidationError

from chupeta import Definition, get_schema
from chupeta.exceptions import UnrecognizedConfigFileFormat, UnsupportedTemplateEngine
from chupeta.templating import TemplateRenderer
from utilities import get_config_path

schema = get_schema()


class TestExceptions():

    def test_file_not_found_error(self):
        config = 'configs/not_existing_file'
        with pytest.raises(FileNotFoundError, match=r"No such file or directory:"):
            Definition(get_config_path(config), schema)

    @pytest.mark.parametrize(('config'), [
        'configs/empty.json',
        'configs/empty.yaml'
    ])
    def test_json_schema_validation_error(self, config):
        with pytest.raises(ValidationError, match=r".*"):
            Definition(get_config_path(config), schema)

    def test_unrecognized_config_file_format_error(self):
        config = 'configs/invalid'
        with pytest.raises(
            UnrecognizedConfigFileFormat,
            match=r"Configuration file is neither a JSON file nor a YAML file!"
        ):
            Definition(get_config_path(config), schema)

    def test_unsupported_template_engine_error(self):
        engine = 'not existing engine'
        with pytest.raises(
            UnsupportedTemplateEngine,
            match=r"Unsupported template engine"
        ):
            TemplateRenderer(engine, '')
