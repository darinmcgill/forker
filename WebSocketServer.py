#!/usr/local/bin/python
import sys
import socket
import os
import datetime
import time
import hashlib
import base64
import struct

_magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_sha1 = lambda x: hashlib.sha1(x).digest()
_sign = lambda x: base64.encodestring(_sha1(x + _magic)).strip()

CONT  = 0
TEXT  = 1
BIN   = 2
CLOSE = 8
PING  = 9
PONG  = 10

def _unmask(payload,mask):
    indv = list()
    abcd = map(ord,mask)
    for i in range(len(payload)):
        j = i % 4
        indv.append(chr(abcd[j] ^ ord(payload[i])))
    return "".join(indv)

class Pong(Exception): pass
class Ping(Exception): pass
class Close(Exception): pass

class WebSocketServer(object):

    def __init__(self,soc,addr=None,verbose=False,cb=None):
        assert isinstance(soc,socket.socket),type(soc)
        self.soc = soc
        self.addr = addr
        self.verbose = verbose
        self.handshake()
        self.data = ""
        self.closed = False
        self.cb = cb

    def fileno(self):
        return self.soc.fileno()

    def handshake(self):
        buff = ""
        while "\r\n\r\n" not in buff:
            buff += self.soc.recv(4096)
        lines = buff.split("\r\n")
        first = lines.pop(0)
        method,loc,prot = first.split()
        self.fields = dict()
        for line in lines:
            if line == "": continue
            k,v = line.split(":",1)
            k,v = k.strip().lower(),v.strip()
            self.fields[k] = v
            if self.verbose:
                sys.stdout.write("=>%s<=>%s<=" % (k,v))
                print
        sig = _sign(self.fields["sec-websocket-key"])
        out = ""
        out += "HTTP/1.1 101 Switching Protocols\r\n"
        out += "Upgrade: websocket\r\n"
        out += "Connection: Upgrade\r\n"
        out += "Sec-WebSocket-Accept: %s\r\n" % sig
        #out += "Sec-WebSocket-Protocol: chat\r\n"
        out += "\r\n"
        self.soc.sendall(out)
        if self.verbose: print "=>%s<=" % out 

    def recvall(self):
        # and one or more frames available to be read
        if self.closed:
            raise Exception("WebSocketServer closed!")
        assert self.data == "", self.data
        out = list()
        self.data = self.soc.recv(4096)
        if self.data == "":
            self.soc.close()
            self.closed = True
            return out
        while self.data != "":
            try:
                out.append(self.recv1())
            except Pong:
                if self.verbose: print "Pong!"
            except Close:
                self.data = ""
                self.close()
            except Ping:
                if self.verbose: print "Ping!"
        return out

    def __call__(self):
        for msg in self.recvall():
            if self.cb:
                self.cb(msg)
        if self.closed:
            raise StopIteration()

    def close(self):
        if self.closed: return
        msg = chr(128 | 8) + chr(0)
        self.soc.sendall(msg)
        self.soc.close()
        self.closed = True

    def send(self,payload,kind=TEXT):
        msg = chr(128 | kind)
        length = len(payload)
        if length <= 125:
            msg += chr(length)
        else:
            if length <= 65535:
                msg += chr(126)
                msg += struct.pack(">H",length)
            else:
                msg += chr(127)
                msg += struct.pack(">Q",length)
        msg += payload
        self.soc.sendall(msg)

    def recv1(self):
        assert self.data, "WebSocketServer.recv1: no data?"
        first = ord(self.data[0])
        fin = bool(first & 128)
        opcode = first & 15
        rsv1 = bool(first & 64)
        rsv2 = bool(first & 32)
        rsv3 = bool(first & 16)
        second = ord(self.data[1])
        masking = bool(second & 128)
        len0 = second & 127
        offset = 2
        if len0 <= 125:
            length = len0
        if len0 == 126:
            length = struct.unpack("!H",self.data[2:4])[0]
            offset += 2
        if len0 == 127:
            length = struct.unpack("!Q",self.data[2:10])[0]
            offset += 8
        if masking:
            mask = self.data[offset:(offset+4)]
            offset += 4
        if self.verbose:
            print "-------------"
            print "fin=",fin
            print "rsv1=",rsv1
            print "rsv2=",rsv2
            print "rsv3=",rsv3
            print "opcode=",opcode
            print "masking=",masking
            print "length=",length
        while len(self.data) < offset + length:
            self.data += self.soc.recv(4096)
            if self.verbose: print "reading more..."
        payload = self.data[offset:(offset+length)]
        if len(self.data) == offset + length:
            if self.verbose: print "perfect length"
            self.data = ""
        else:
            if self.verbose: print "extra stuff"
            self.data = self.data[(offset+length):len(self.data)]
        if masking:
            payload = _unmask(payload,mask)
        if self.verbose: print "payload=>%s<=" % payload
        if opcode == PONG: raise Pong()
        if opcode == CLOSE: raise Close(payload)
        if opcode == PING:
            self.send(payload,PONG)
            raise Ping()
        if not fin:
            if self.data == "":
                self.data = self.soc.recv(4096)
            payload += self.recv1()
        return payload
        
        
if __name__ == "__main__":
    if True:
        from Forker import Forker
        forker = Forker(WebSocketServer)
        import util
        try: util.loop([forker])
        except KeyboardInterrupt: pass
