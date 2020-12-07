#!/usr/bin/python3
# -*- coding: utf-8 -*-

import socket
import time
import errno

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
    except:
        pass
    end = time.time()
    ms = 1000*(end-start)
    return result, round(ms,2)
