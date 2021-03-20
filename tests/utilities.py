#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import socket
import time
import signal
import io
import uuid
from os import path
from unittest.mock import patch
from multiprocessing import Process
import contextlib

from mockintosh.constants import PROGRAM
from mockintosh import initiate

__location__ = path.abspath(path.dirname(__file__))


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


def run_mock_server(*args, wait=10):
    mock_server_process = None

    testargs = [PROGRAM, *args]
    with patch.object(sys, 'argv', testargs):
        mock_server_process = Process(target=initiate, args=())
        mock_server_process.start()

    signal.signal(signal.SIGALRM, signal_handler)
    signal.sigtimedwait([signal.SIGALRM], wait)

    return mock_server_process


def get_config_path(config):
    return path.join(__location__, config)


@contextlib.contextmanager
def nostdout():
    """Method to suppress the standard output. (use it with `with` statements)
    """

    save_stdout = sys.stdout
    sys.stdout = io.StringIO()
    yield
    sys.stdout = save_stdout


@contextlib.contextmanager
def nostderr():
    """Method to suppress the standard error. (use it with `with` statements)
    """
    save_stderr = sys.stderr
    sys.stderr = io.StringIO()
    yield
    sys.stderr = save_stderr


def is_valid_uuid(val, version=4):
    try:
        uuid.UUID(str(val), version=version)
        return True
    except ValueError:
        return False


def is_ascii(s):
    return all(ord(c) < 128 for c in s)
