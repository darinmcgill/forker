from __future__ import print_function
import re
import sys
import datetime
import os
import socket
import base64
import glob
import stat
import select
from io import BytesIO, StringIO

if sys.version_info < (3, 3):

    class TimeoutError(Exception):
        pass

    class ConnectionAbortedError(Exception):
        pass

else:
    TimeoutError = TimeoutError
    ConnectionAbortedError = ConnectionAbortedError


Timeout = TimeoutError
Aborted = ConnectionAbortedError


class Request(object):
    __slots__ = ("request_id", "remote_ip", "protocol", "method",
                 "requested_path", "headers", "cookies", "body",
                 "query_string", "verbose", "listening_port", "raw")

    OK = b"HTTP/1.0 200 OK\r\n"

    def __init__(self, **kwargs):
        self.body = b""
        self.verbose = False
        self.headers = {}
        self.remote_ip = ""
        self.method = "GET"
        self.query_string = None
        self.raw = None
        for k, v in kwargs.items():
            if k == "sock":
                continue
            setattr(self, k, v)
        if "sock" in kwargs:
            sock = kwargs["sock"]
            self.raw = b""
            match = None
            while not match:
                selected = select.select([sock], [], [], 0.1)
                if not selected[0]:
                    raise Timeout(repr(self.raw))
                tmp = sock.recv(4096)
                if not tmp:
                    raise Aborted()
                self.raw += tmp
                match = re.match(br"(.*?)\r?\n\r?\n(.*)", self.raw, re.S)
            header_block = match.group(1)
            if not isinstance(header_block, str):
                header_block = header_block.decode()
            self.body = match.group(2)
            lines = re.split("\\r?\\n", header_block)
            first = lines.pop(0)
            self.method, request_string, self.protocol = first.split()
            self.requested_path = request_string.split("?")[0]
            self.query_string = request_string.split("?", 1)[1] if "?" in request_string else ""
            for line in lines:
                a, b = line.split(":", 1)
                self.headers[a.strip().lower()] = b.strip()
            self.cookies = dict()
            if "cookie" in self.headers:
                for cookie in re.split(";\s*", self.headers["cookie"]):
                    k, v = cookie.strip().split("=")
                    self.cookies[k] = v
            if "x-real-ip" in self.headers:
                self.remote_ip = self.headers["x-real-ip"]
            if "content-length" in self.headers:
                while len(self.body) < int(self.headers["content-length"]):
                    tmp = sock.recv(4096)
                    if not tmp:
                        break
                    self.body += tmp
                    self.raw += tmp

    def rdns(self):
        if self.remote_ip.startswith("127."):
            return None
        if self.remote_ip.startswith("192.168"):
            return None
        try:
            return socket.gethostbyaddr(self.remote_ip)[0]
        except Exception as e:
            sys.stderr.write("rdns: %s %s" % (type(e), e))
            return None

    def render(self, start, sep, end):
        out = start
        for key in self.__slots__:
            try:
                out += "%s=%r%s" % (key, getattr(self, key), sep)
            except AttributeError:
                pass
        out += end
        return out

    def __repr__(self):
        return self.render(sep=",", start="Request(", end=")")

    def __str__(self):
        target = self.requested_path
        if self.query_string:
                target = target + "?" + self.query_string
        return "Request('%s')" % target

    def __bytes__(self):
        return self.raw

    def log(self, file=sys.stdout):
        ts = str(datetime.datetime.now())
        print(repr([ts, self.requested_path, self.method, self.remote_ip]), file=file)

    def cgi(self, resolved):
        for k in list(os.environ.keys()):
            if k in ["PATH", "PYTHONPATH"]:
                continue
            del os.environ[k]
        if self.query_string:
            os.environ["QUERY_STRING"] = self.query_string
        os.environ["SERVER_SOFTWARE"] = "forker.py/20150821"
        os.environ["SERVER_NAME"] = socket.gethostname()
        # os.environ["SERVER_PORT"] = str(self.port)
        os.environ["SERVER_PROTOCOL"] = "HTTP/1.0"
        os.environ["CONTENT_LENGTH"] = str(len(self.body)) if self.body else ""
        os.environ["GATEWAY_INTERFACE"] = "CGI/1.1"
        os.environ["REQUEST_METHOD"] = self.method
        os.environ["SCRIPT_NAME"] = self.requested_path
        os.environ["HTTP_USER_AGENT"] = self.headers.get("user-agent", "")
        os.environ["HTTP_ACCEPT_LANGUAGE"] = self.headers.get("accept-language", "")
        os.environ["HTTP_COOKIE"] = self.headers.get("cookie", "")
        os.environ["HTTP_REFERER"] = self.headers.get("referer", "")
        os.environ["CONTENT_TYPE"] = self.headers.get("content-type", "")
        os.environ["HTTP_HOST"] = self.headers.get("host", "")
        os.environ["REMOTE_ADDR"] = self.remote_ip
        os.environ["HTTP_X_REAL_IP"] = self.headers.get("x-real-ip", "")
        os.environ["HTTP_X_FORWARDED_FOR"] = self.headers.get("x-forwarded-for", "")
        os.environ["HTTP_X_FORWARDED_HOST"] = self.headers.get("x-forwarded-host", "")
        os.environ["HTTP_X_FORWARDED_URI"] = self.headers.get("x-forwarded-uri", "")
        os.environ["HTTP_X_FORWARDED_REQUEST_URI"] = self.headers.get(
            "x-forwarded-request-uri", "")
        if "Basic" in self.headers.get("authorization", ""):
            second = self.headers["authorization"].split()[1]
            user = base64.decodestring(second.encode()).split(b":")[0]
            os.environ["HTTP_X_AUTH_USER"] = user.decode()
        from subprocess import Popen, PIPE
        child = Popen(resolved, stdin=PIPE, stdout=PIPE)
        out, err = child.communicate(self.body or b"")
        if child.returncode != 0:
            out = b"HTTP/1.0 500 Error\r\n"
            out += b"Content-type: text/plain\r\n\r\n"
            out += b"non-zero return code\n\n"
            return out
        m = re.match(b"^(.*?)\\n\\r?\\n(.*)$", out, re.S)
        if not m:
            return b"HTTP/1.0 500 Bad Header\r\n\r\n500 Bad Header"
        header = m.group(1)
        body = m.group(2)
        lines = re.split(b"\\r?\\n", header)
        status = Request.OK
        header = b""
        for line in lines:
            status_match = re.match(b"^status:\s*(.*)", line, re.I)
            if status_match:
                status = b"HTTP/1.0 " + status_match.group(1) + b"\r\n"
            else:
                header += line + b"\r\n"
        return status + header + b"\r\n" + body

    def serve(self, allow_cgi=False):
        try:
            resolved = self.resolve(self.requested_path, os.getcwd())
        except KeyError:
            return b"HTTP/1.0 404 Not Found\r\n\r\n404 Not Found"
        if os.path.isdir(resolved):
            if "x-forwarded-uri" in self.headers:
                self.requested_path = self.headers["x-forwarded-uri"]
            return self.get_listing(resolved, self.requested_path)
        if Request.is_executable(resolved) and allow_cgi:
            return self.cgi(resolved)
        if self.method == "GET":
            with open(resolved, "rb") as handle:
                contents = handle.read()
            return Request.OK + Request.type_line(resolved) + b"\r\n" + contents
        return b"HTTP/1.0 500 Unexpected\r\n\r\n500 Unexpected\n" + bytes(self)

    def get_listing(self, resolved, raw):
        if self.verbose:
            print("getListing(%r,%r)" % (resolved, raw))
        assert os.path.isdir(resolved)
        out = b"HTTP/1.0 200 OK\r\n"
        out += b"Content-type: text/html\r\n\r\n"
        out += b"""
        <html><head><title>directory listing</title>
        <style>
        pre {font-size: large;}
        </style>
        </head><body>
        <pre>Contents:"""
        if not raw.endswith("/"):
            raw += "/"
        for thing in glob.glob(resolved + "/*"):
            if os.path.isdir(thing):
                d = "/"
            elif os.path.islink(thing):
                d = "@"
            elif Request.is_executable(thing):
                d = "*"
            else:
                d = ""
            last = os.path.basename(thing)
            out += ("\n\t<a href='%s%s'>%s</a>%s" % (raw, last, last, d)).encode()
        out += b"</pre></font></body></html>"
        return out

    def resolve(self, path, relative):
        if self.verbose:
            print("resolve(%r,%r)" % (path, relative))
        if not isinstance(path, list):
            path = [p for p in path.split("/") if p]
        assert isinstance(path, list)
        assert os.path.exists(relative), relative
        if os.path.islink(relative):
            return self.resolve(path, os.path.realpath(relative))
        if os.path.isfile(relative):
            return relative
        assert os.path.isdir(relative), relative
        if len(path) == 0:
            try:
                return self.resolve(["index", "index.html"], relative)
            except KeyError:
                return relative
        name = path.pop(0)
        contents = os.listdir(relative)  # does not include ".." and "."
        if name in contents:
            return self.resolve(path, os.path.join(relative, name))
        matches = [x for x in contents if x.startswith(name + ".")]
        if len(matches) == 1:
            return self.resolve([], os.path.join(relative, matches[0]))
        if len(matches) > 1:
            raise KeyError("ambiguous:" + os.path.join(relative, name))
        raise KeyError(os.path.join(relative, name))

    @staticmethod
    def is_executable(path):
        mode = os.stat(path).st_mode
        return bool(stat.S_IXOTH & mode)

    @staticmethod
    def is_readable(path):
        mode = os.stat(path).st_mode
        return bool(stat.S_IROTH & mode)

    type_map = dict(
        html=b"text/html",
        htm=b"text/html",
        css=b"text/css",
        txt=b"text/plain",
        xml=b"text/xml",
        manifest=b"text/cache-manifest",
        appcache=b"text/cache-manifest",
        pdf=b"application/pdf",
    )

    @staticmethod
    def type_line(fn):
        for k, v in Request.type_map.items():
            if fn.endswith("." + k):
                return b"Content-type: " + v + b"\r\n"
        return b""  # let the browser guess

    def wsgi(self, application):
        """
        Passes the request to a wsgi application for processing.
        :param application: A callable object as per the wsgi spec.
        :return: A "bytes" object which can be sent to the client.
        """
        written = list()
        error_io = StringIO()
        environ = dict()
        for k, v in self.headers.items():
            if k == "content-type":
                continue
            new_key = "HTTP_" + k.replace("-", "_").upper()
            environ[new_key] = v
        environ["CONTENT_TYPE"] = self.headers.get("content-type")
        environ["REQUEST_METHOD"] = self.method
        environ["PATH_INFO"] = self.requested_path
        environ["QUERY_STRING"] = self.query_string
        environ["CONTENT_TYPE"] = self.headers.get("content-type")
        environ["CONTENT_LENGTH"] = str(len(self.body))
        environ["SERVER_PROTOCOL"] = self.protocol
        environ['SERVER_SOFTWARE'] = 'forker'
        environ["SERVER_NAME"] = socket.gethostname()
        environ["REMOTE_ADDR"] = self.remote_ip
        environ['GATEWAY_INTERFACE'] = 'CGI/1.1'
        environ['wsgi.input'] = BytesIO(self.body)
        environ['wsgi.errors'] = error_io
        environ['wsgi.version'] = (1, 0)
        environ['wsgi.multithread'] = True
        environ['wsgi.multiprocess'] = True
        environ['wsgi.run_once'] = False

        if environ.get('HTTPS', 'off') in ('on', '1'):
            environ['wsgi.url_scheme'] = 'https'
        else:
            environ['wsgi.url_scheme'] = 'http'

        headers_set = []
        headers_sent = []

        def write(data):
            if not headers_set:
                raise AssertionError("write() before start_response()")

            if not headers_sent:
                # Before the first output, send the stored headers
                status, response_headers = headers_sent[:] = headers_set
                written.append(('HTTP/1.0 %s\r\n' % status).encode())
                for header in response_headers:
                    written.append(('%s: %s\r\n' % header).encode())
                written.append(b'\r\n')

            written.append(data)

        def start_response(status, response_headers, exc_info=None):
            if exc_info:
                try:
                    error_io.write(str(exc_info))
                finally:
                    exc_info = None     # avoid dangling circular ref
            elif headers_set:
                raise AssertionError("Headers already set!")

            headers_set[:] = [status, response_headers]
            return exc_info or write

        result = application(environ, start_response)
        try:
            for blob in result:
                assert isinstance(blob, bytes), ("invalid bytestring:" + repr(blob))
                if blob:    # don't send headers until body appears
                    write(blob)
            if not headers_sent:
                write(b'')   # send headers now if body was empty
        finally:
            if hasattr(result, 'close'):
                result.close()

        error_msg = error_io.getvalue().encode()
        if error_msg:
            return b'Status: 500 WTF\r\n\r\n' + error_msg
        return b''.join(written)
