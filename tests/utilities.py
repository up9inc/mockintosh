#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import socket
import time
import signal
from os import path
from unittest.mock import patch
from multiprocessing import Process

from chupeta.constants import PROGRAM
from chupeta import initiate


def signal_handler(sig, frame):
    pass


def tcping(host, port=65533, timeout=2):
    s = socket.socket()
    s.settimeout(timeout)
    result = False
    end = None
    try:
        start = time.time()
        s.connect((host, port))
        s.close()
        result = True
        end = time.time()
    except Exception:
        pass
    end = time.time()
    ms = 1000 * (end - start)
    return result, round(ms, 2)


def run_mock_server(*args):
    mock_server_process = None

    testargs = [PROGRAM, *args]
    with patch.object(sys, 'argv', testargs):
        mock_server_process = Process(target=initiate, args=())
        mock_server_process.start()

    signal.signal(signal.SIGALRM, signal_handler)
    signal.sigtimedwait([signal.SIGALRM], 5)

    return mock_server_process


def get_config_path(config):
    __location__ = path.abspath(path.dirname(__file__))
    return path.join(__location__, config)
