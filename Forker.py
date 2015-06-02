#!/usr/local/bin/python
import sys
import socket
import os
import datetime
import time
import glob
import stat
import re
import datetime

class Forker(object):
    def __init__(self,onAccept,port=8080):
        self.listener = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        self.listener.bind(('',port))
        self.listener.listen(128)
        self.onAccept = onAccept
    def fileno(self):
        return self.listener.fileno()
    def __call__(self):
        newSock, addr = self.listener.accept()
        cpid = os.fork()
        if cpid: # in parent
            newSock.close()
        else:
            self.onAccept(newSock,addr)
            os._exit(0)

class NotFound(Exception): pass

def translate(onReq):
    """ returns acceptor(soc,addr) that calls onReq(path,method,fields,body) """
    def onAccept(soc,addr):
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
        try:
            print repr([str(datetime.datetime.now()),addr[0],path])
            #print "%s,%s,%s" % (datetime.datetime.now(),addr[0],path)
            soc.sendall(onReq(path,method,fields,body))
        except NotFound,e:
            soc.sendall("HTTP/1.0 404 Not Found\r\n\r\n404 Not Found %s" % e)
        except Exception,e:
            sys.stderr.write("problem:\n%s<=>%s\n" % (type(e),e))
            msg = "Exception caught by Forker:\n%s" % e
            soc.sendall("HTTP/1.0 500 Internal Server Error\r\n\r\n%s" % msg)
    return onAccept

def report(path,method,fields,body):
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
    if relative:
        if ".." in path:
            raise Exception("up listing now allowed")
        if not re.match(r"^[0-9a-zA-Z_\-/.]+$",path):
            raise Exception("invalid path: %s" % path)
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

def serve(path,method,fields,body):
    #print "serve(%r,%r,%r,%r)" % (path,method,fields,body)
    ok = "HTTP/1.0 200 OK\r\n"
    eol = "\r\n"
    things = path.split("?",1)
    rel = things[0]
    resolved = resolve(rel,os.getcwd())
    if not readable(resolved): raise Exception("not readable")
    if os.path.isdir(resolved): return getListing(resolved,rel)
    if not executable(resolved): 
        if method == "POST": return report(path,method,fields,body)
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
    from subprocess import Popen,PIPE
    child = Popen(resolved,stdin=PIPE,stdout=PIPE,stderr=PIPE)
    out,err = child.communicate(body or "")
    if False and child.returncode != 0:
        out = "HTTP/1.0 500 Error\r\n"
        out += "Content-type: text/plain\r\n\r\n"
        out += "non-zero return code\n\n"
        out += err
        return(out)
    if "\r\n\r\n" not in out:
        out = out.replace("\n\n","\r\n\r\n")
    if out.startswith("Location"):
        out = "HTTP/1.0 302 Found\r\n" + out
        return out
    else:
        return ok + out

if __name__ == "__main__":
    import util
    args = util.getArgs()
    port = args.get("port",8080)
    if len(args): 
        os.chdir(args[0])
        forker = Forker(translate(serve),port)
    else:
        forker = Forker(translate(report),port)
    try: util.loop([forker])
    except KeyboardInterrupt: pass
