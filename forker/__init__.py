#!/usr/bin/env python3
from __future__ import print_function
from __future__ import absolute_import
from .Request import Request
from .listen import listen, Address, Socket
from .WebSocketServer import WebSocketServer, TEXT, BIN


WEB_MIN = 0x10000000000000
WEB_MAX = 0x1fffffffffffff


__all__ = ["Request", "Socket", "listen", "WebSocketServer", "TEXT", "BIN", "WEB_MIN", "WEB_MAX"]

