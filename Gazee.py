#  This file is part of Gazee.
#
#  Gazee is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Gazee is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mylar.  If not, see <http://www.gnu.org/licenses/>.

import os, sys
import string
import time
import threading
import signal
import argparse
import logging
import threading

from pathlib import Path

import cherrypy
from cherrypy.process.plugins import Daemonizer, PIDFile

import gazee
from gazee import *

gazee.FULL_PATH = os.path.abspath(__file__)
# Verify our app is working out of the install directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if ( sys.platform == 'win32' and sys.executable.split( '\\' )[-1] == 'pythonw.exe'):
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

def daemonize():

    logging.basicConfig(level=logging.DEBUG,filename='data/gazee.log')
    logger = logging.getLogger(__name__) 

    if threading.activeCount() != 1:
        logger.warn('There are %r active threads. Daemonizing may cause \
                        strange behavior.' % threading.enumerate())

    sys.stdout.flush()
    sys.stderr.flush()

    # Do first fork
    try: 
        pid = os.fork()
        if pid == 0:
            pass 
        else:
            # Exit the parent process
            logger.debug('Forking once...')
            os._exit(0)
    except OSError as e:
        sys.exit("1st fork failed: %s [%d]" % (e.strerror, e.errno))

    os.setsid()

    # Make sure I can read my own files and shut out others
    prev = os.umask(0)  # @UndefinedVariable - only available in UNIX
    os.umask(prev and int('077', 8))

    # Do second fork
    try: 
        pid = os.fork()
        if pid > 0: 
            logger.debug('Forking twice...')
            os._exit(0) # Exit second parent process
    except OSError as e:
        sys.exit("2nd fork failed: %s [%d]" % (e.strerror, e.errno))

    with open('/dev/null', 'r') as dev_null:
        os.dup2(dev_null.fileno(), sys.stdin.fileno())

    si = open('/dev/null', "r") 
    so = open('/dev/null', "a+")
    se = open('/dev/null', "a+")

    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    pid = os.getpid()
    logger.info('Daemonized to PID: %s' % pid)
    logger.info("Writing PID %d to %s", pid, gazee.PIDFILE)
    with open(gazee.PIDFILE, 'w') as fp:
        fp.write("%s\n" % pid)

def main():
    logging.basicConfig(level=logging.DEBUG,filename='data/gazee.log')
    logger = logging.getLogger(__name__) 

    parser = argparse.ArgumentParser(description='Gazee - Open Comic Book Reader')

    parser.add_argument('-d', '--daemon', action='store_true', help='Run as a daemon')

    args = parser.parse_args()

    if args.daemon:
        if sys.platform == 'win32':
            print("Daemonize not supported under Windows, starting normally")
            DAEMON = False
        else:
            DAEMON = True

            # If the pidfile already exists, Gazee may still be running, so exit
            if os.path.exists(gazee.PIDFILE):
                sys.exit("PID file '" + gazee.PIDFILE + "' already exists. Exiting.")

            # The pidfile is only useful in daemon mode, make sure we can write the file properly
            try:
                PIDFile(cherrypy.engine, gazee.PIDFILE).subscribe()
            except IOError as e:
                raise SystemExit("Unable to write PID file: %s [%d]" % (e.strerror, e.errno))
            Daemonizer(cherrypy.engine).subscribe()

    conf = {
            '/' : {
                'tools.gzip.on': True,
                'tools.sessions.on': True,
                'tools.sessions.storage_class': cherrypy.lib.sessions.FileSession,
                'tools.sessions.storage_path': "data/sessions",
                'tools.staticdir.root': os.path.abspath(os.getcwd()),
                'tools.basic_auth.on': True,
                'tools.basic_auth.realm': 'Gazee',
                'tools.basic_auth.users': gazee.authmech.getPassword,
                'tools.basic_auth.encrypt': gazee.authmech.hashPass
                },
            '/static' : {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': "public"
                },
            '/data' : {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': "data"
                },
            '/tmp' : {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': "tmp"
                },
            '/favicon.ico' : {
                'tools.staticfile.on': True,
                'tools.staticfile.filename': os.path.join(os.getcwd(), "public/images/favicon.ico")
                }
            }

    if (gazee.SSL_KEY == '') and (gazee.SSL_CERT == ''):
        options_dict = {
        'server.socket_port': gazee.PORT,
        'server.socket_host': '0.0.0.0',
        'server.thread_pool': 10,
        'log.screen': False,
        'engine.autoreload.on': False,
        }
    else:
        options_dict = {
        'server.socket_port': gazee.PORT,
        'server.socket_host': '0.0.0.0',
        'server.thread_pool': 10,
        'server.ssl_module': 'builtin',
        'server.ssl_certificate': gazee.SSL_CERT,
        'server.ssl_private_key': gazee.SSL_KEY,
        'log.screen': False,
        'engine.autoreload.on': False,
        }

    cherrypy.config.update(options_dict)

    cherrypy.engine.timeout_monitor.on: False
    cherrypy.tree.mount(Gazee(), '/', config=conf)

    logging.info("Gazee Started")

    cherrypy.engine.start()
    cherrypy.engine.block()

    return

if __name__ == '__main__':
    main()
