#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :platform: Unix
    :synopsis: End-to-end tests related to mock server's itself.
.. moduleauthor:: M. Mert Yildiran <mehmet@up9.com>
"""

import sys
import unittest
import time
import signal
import subprocess
import pytest
from os import path
from unittest.mock import patch
from multiprocessing import Process

from chupeta import initiate
from utilities import signal_handler, tcping

PROGRAM = 'chupeta'

templates = [
    'templates/template.json.j2'
]
test_parameters = []
for template in templates:
    test_parameters.append(('default', template))
    test_parameters.append(('docker', template))

@pytest.mark.parametrize(('mode', 'template'), test_parameters)
class TestFeatures:
    def setup_method(self):
        mode = self._item.callspec.getparam('mode')
        template = self._item.callspec.getparam('template')

        self.mock_server_process = None
        __location__ = path.abspath(path.dirname(__file__))
        template_path = path.join(__location__, template)

        mode = 'default'  # TODO: Remove this line
        if mode == 'default':
            testargs = [PROGRAM, template_path]
            with patch.object(sys, 'argv', testargs):
                self.mock_server_process = Process(target=initiate, args=())
                self.mock_server_process.start()
        elif mode == 'docker':
            template_filename = template_path.split('/')[-1]
            cmd = [
                'docker',
                'run',
                '--init',
                '--network',
                'host',
                '-v',
                '%s:/%s' % (template_path, template_filename),
                PROGRAM,
                '/%s' % template_filename
            ]
            self.mock_server_process = subprocess.run(cmd)

        signal.signal(signal.SIGUSR1, signal_handler)
        signal.pause()

    def teardown_method(self):
        self.mock_server_process.terminate()

    def test_ping_ports(self, mode, template):
        ports = (8001, 8002)
        for port in ports:
            result, _ = tcping('localhost', port)
            if not result:
                raise AssertionError("Port %d is closed!" % port)
