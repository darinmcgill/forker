from setuptools import setup

setup(
    name='forker',
    version='0.1.3',
    description='A forking webserver and websocket server.',
    url='https://github.com/darinmcgill/forker',
    author='Darin McGill',
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',
    ],
    keywords='wsgi cgi websocket websockets forking http',
    packages=['forker'],
)
