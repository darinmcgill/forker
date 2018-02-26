# forker

Copyright Darin McGill, 2015 
License: GPL v 3.0

The module forker.py is a simple synchronous forking web server.
It's written in pure python 2.7 and has no external dependencies other than 
the standard python library.  It includes a web socket server and an 
implementation of CGI.  It's primarily intended to be used behind a reverse 
proxy such as nginx, but can also be used for testing/development in a pinch.

This project was inspired by difficulties encountered using thttpd, 
specifically the limitation that sim links could not point outside the
web-server's document root.  Allowing links to point outside the root
allows you to create a "facade" of stable URLs, while changing the 
name/location/extension of the actual file to be served or run.

Run by:

    python forker.py 
    or
    python -m forker

By default the document root is the current directory, and the port is 8080.
You can specify the document root and/or the port by adding them as arguments:

    python forker.py /tmp
    or
    python forker.py 80
    or
    python forker.py /tmp 80

Specify "nofork" as an additional command line parameter to disable forking
and serve one request at time.  (This somewhat defeats the purpose of the
module, but makes debugging easier.)

On Windows:
    Basic file serving works, but CGI does not.  Also, "nofork" is implied.

TODO:

* implment CGI on windows
* add WSGI adapter
* make compatible with Python 3
