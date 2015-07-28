#!/usr/local/bin/python
import sys
import socket
import select
import os
import datetime
import time
import glob
import stat
import re
import datetime
import copy
import base64
import hashlib
import uuid
import random
import struct
import random


def listen(port=8081,forking=True):
    listener = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind(('',port))
    listener.listen(128)
    nextId = int(time.time())
    children = set()
    while True:
        try:
            while nextId >= int(time.time()): time.sleep(0.1)
            r,w,e = select.select([listener],[],[],1)
            if r: newSock, addr = listener.accept()
            else: 
                for child in list(children):
                    pid,status = os.waitpid(child,os.WNOHANG)
                    if pid: children.remove(child)
                continue
        except KeyboardInterrupt:
            sys.exit(0)
        isParent = forking and os.fork()
        random.seed()
        if isParent:
            children.add(isParent)
            newSock.close()
            nextId += 1
        else:
            listener.close()
            break
    return (newSock,addr,(port << 32) + nextId)

class NotFound(Exception): pass

def translate(soc,addr,forkId):
    buff = ""
    while "\r\n\r\n" not in buff:
        buff += soc.recv(4096)
    header,body = buff.split("\r\n\r\n")
    lines = header.split("\r\n")
    first = lines.pop(0)
    method,path,prot = first.split()
    fields = dict()
    for line in lines:
        a,b = line.split(":",1)
        fields[a.strip().lower()] = b.strip()
    if "content-length" in fields:
        while len(body) < int(fields["content-length"]):
            body += soc.recv(4096)
    return (path,method,fields,body,addr[0])

def report(path,method,fields,body,ip):
    out = "HTTP/1.0 200 OK\r\n"
    out += "Content-type: text/plain\r\n\r\n"
    out += str(datetime.datetime.now())
    out += "\n\npath=%s\n" % path 
    out += "method=%s\n" % method
    for k,v in fields.items():
        out += ">%s<=>%s<\n" % (k,v)
    out += "body=>%s<=\n" % body
    out += "len = %d" % len(body)
    return out

def resolve(path,relative=None):
    #print "resolve(%r,%r)" % (path,relative)
    if path.endswith("/") and path != "/":
        path = path[0:(len(path)-1)]
    if relative:
        if ".." in path:
            raise NotFound("up listing not allowed")
        if not re.match(r"^[0-9a-zA-Z_\-/.]+$",path):
            raise NotFound("invalid path: %s" % path)
        path = relative + "/" + path
    if not os.path.exists(path):
        print "doesn't exist: %s" % path
        if path.endswith("/"): raise NotFound("ABC")
        matches = glob.glob(path + ".*")
        if not matches: raise NotFound("XYZ")
        if len(matches) > 1: raise NotFound("resolve ambiguous")
        path = matches[0]
    if os.path.islink(path):
        path = os.path.realpath(path)
        if not os.path.exists(path): raise NotFound("MNQ")
    if os.path.isdir(path):
        for index in [path+"/index.html",path+"/index"]:
            if os.path.exists(index): return resolve(index)
    if not readable(path): 
        raise NotFound("%s not readable" % path)
    return path

def executable(path):
    mode = os.stat(path).st_mode
    return bool(stat.S_IXOTH & mode)

def readable(path):
    mode = os.stat(path).st_mode
    return bool(stat.S_IROTH & mode)

def getListing(resolved,raw):
    #print "getListing(%r,%r)" % (resolved,raw)
    assert os.path.isdir(resolved)
    out = "HTTP/1.0 200 OK\r\n"
    out += "Content-type: text/html\r\n\r\n"
    out += """
    <html><head><title>directory listing</title>
    <style>
    pre {font-size: x-large;}
    </style>
    </head><body>
    <pre>Contents:
    """
    if not raw.endswith("/"): raw += "/"
    for thing in glob.glob(resolved + "/*"):
        if os.path.isdir(thing): d = "/"
        elif os.path.islink(thing): d = "@"
        elif executable(thing): d = "*"
        else: d = ""
        last = thing.split("/")[-1]
        out += "\t<a href='%s%s'>%s</a>%s\n" % (raw,last,last,d)
    out += "</pre></font></body></html>"
    return out

def serve(path,method,fields,body,ip):
    print repr([str(datetime.datetime.now()),path,method,ip])
    ok = "HTTP/1.0 200 OK\r\n"
    eol = "\r\n"
    things = path.split("?",1)
    rel = things[0]
    try: resolved = resolve(rel,os.getcwd())
    except NotFound: return "HTTP/1.0 404 Not Found\r\n\r\n404 Not Found"
    if os.path.isdir(resolved): return getListing(resolved,rel)
    if not executable(resolved): 
        if method == "POST": 
            return "HTTP/1.0 500 Not Executable\r\n\r\n500 Not Executable"
            #return report(path,method,fields,body,ip)
        else: return ok + eol + open(resolved).read()
    if things[1:]: os.environ["QUERY_STRING"] = things[1]
    os.environ["REQUEST_METHOD"] = method
    os.environ["SCRIPT_NAME"] = rel
    os.environ["HTTP_USER_AGENT"] = fields.get("user-agent","")
    os.environ["HTTP_ACCEPT_LANGUAGE"] = fields.get("accept-language","")
    os.environ["HTTP_COOKIE"] = fields.get("cookie","")
    os.environ["HTTP_REFERER"] = fields.get("referer","")
    os.environ["CONTENT_TYPE"] = fields.get("content-type","")
    os.environ["HTTP_HOST"] = fields.get("host","")
    os.environ["REMOTE_ADDR"] = ip
    from subprocess import Popen,PIPE
    child = Popen(resolved,stdin=PIPE,stdout=PIPE)
    out,err = child.communicate(body or "")
    if child.returncode != 0:
        out = "HTTP/1.0 500 Error\r\n"
        out += "Content-type: text/plain\r\n\r\n"
        out += "non-zero return code\n\n"
        return(out)
    m = re.match(r"^(.*?)\n\r?\n(.*)$",out,re.S)
    if not m: 
        return "HTTP/1.0 500 Bad Header\r\n\r\n500 Bad Header"
    header = m.group(1)
    body = m.group(2)
    lines = re.split("\r?\n",header)
    status = ok
    header = ""
    for line in lines:
        if re.match(r"^status:\s*\d\d\d.*$",line,re.I):
            status = "HTTP/1.0 " + line.split(":")[1] + "\r\n"
        else:
            header += line + "\r\n"
    return status + header + "\r\n" + body

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
class Closed(Exception): pass

countWebSocketServer = 0

class WebSocketServer(object):

    def __init__(self,soc):
        assert isinstance(soc,socket.socket),type(soc)
        self.soc = soc
        self.fd = soc.fileno()
        self.verbose = False
        self.closed  = False
        self.data = ""
        self.handshake()
        global countWebSocketServer
        countWebSocketServer += 1
        self.instance = countWebSocketServer

    def __hash__(self):
        return id(self)

    def fileno(self):
        return self.fd

    def handshake(self):
        buff = ""
        while "\r\n\r\n" not in buff:
            buff += self.soc.recv(4096)
        self.lastRecv = time.time()
        lines = buff.split("\r\n")
        first = lines.pop(0)
        self.method,self.loc,self.prot = first.split()
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
        out += "\r\n"
        self.soc.sendall(out)
        self.lastSend = time.time()
        if self.verbose: print "=>%s<=" % out 

    def recvall(self):
        # returns a list of strings
        if self.closed: raise Closed()
        assert self.data == "", self.data
        out = list()
        self.data = self.soc.recv(4096)
        self.lastRecv = time.time()
        if self.data == "":
            self.soc.close()
            self.closed = True
            return out
        while self.data != "":
            try:
                out.append(self._recv1())
            except Pong:
                if self.verbose: print "Pong!"
            except Close:
                self.data = ""
                self.close()
            except Ping:
                if self.verbose: print "Ping!"
        return out

    def close(self):
        if self.closed: return
        msg = chr(128 | 8) + chr(0)
        try:
            self.soc.sendall(msg)
        except:
            pass
        finally:
            self.soc.close()
            self.closed = True

    def ping(self,payload=""):
        self.send(payload,kind=PING)

    def send(self,payload,kind=TEXT):
        if self.closed: raise Closed()
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
        msg += str(payload)
        self.soc.sendall(msg)
        self.lastSend = time.time()

    def _recv1(self):
        assert self.data, "WebSocketServer._recv1: no data?"
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
            self.lastRecv = time.time()
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
                self.lastRecv = time.time()
            payload += self._recv1()
        if opcode == BIN:
            return bytearray(payload)
        if opcode == TEXT:
            return payload
        raise Exception("bad opcode")
        

if __name__ == "__main__":
    port = 8080
    forking = (os.name == 'posix')
    reporting = False
    ws = False
    for arg in copy.copy(sys.argv[1:]):
        if re.match(r"^\d+$",arg):
            port = int(arg)
            sys.argv.remove(arg)
    if "once" in sys.argv:
        forking = False
        sys.argv.remove("once")
    if "report" in sys.argv:
        reporting = True
        sys.argv.remove("report")
    if "ws" in sys.argv:
        ws = True
        sys.argv.remove("ws")
    if sys.argv[1:]:
        assert os.path.exists(sys.argv[1])
        os.chdir(sys.argv[1])
    sock,addr,forkId = listen(port=port,forking=forking)
    if reporting:
        sock.sendall(report(*translate(sock,addr,forkId)))
    elif ws:
        print "running WebSocketServer in echo mode"
        ws = WebSocketServer(sock)
        while True:
            for thing in ws.recvall():
                print "echoing: %r" % thing
                how = BIN if isinstance(thing,bytearray) else TEXT
                ws.send(thing,how)
    else:
        sock.sendall(serve(*translate(sock,addr,forkId)))
