from setuptools import setup, find_packages

setup(
    name='forker',
    version='0.1.1',
    description='A forking webserver and websocket server.',
    url='https://github.com/darinmcgill/forker',
    author='Darin McGill',
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='wsgi cgi websocket websockets forking http',
    packages='forker',  
)
