#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Import from the Standard Library
from optparse import OptionParser
from time import sleep
from subprocess import Popen, PIPE
import sys
from os.path import dirname, join, realpath

# Import from itools
import itools


def start(parser, options, target):
    script_path = dirname(realpath(sys.argv[0]))
    # Detach
    if options.detach:
        stdin = stdout = stderr = PIPE
    else:
        stdin = stdout = stderr = None

    # Start Server
    path_icms_start_server = join(script_path, 'icms-start-server.py')
    args = [path_icms_start_server, target]
    if options.debug:
        args.append('--debug')
    if options.port:
        args.append('--port=%s' % options.port)
    if options.address:
        args.append('--address=%s' % options.address)
    args = ' '.join(args)
    p_server = Popen(args, 0, None, stdin, stdout, stderr, shell=True)
    # Detach (FIXME Output from the child is lost)
    if options.detach:
        p_server.stdin.close()
        p_server.stdout.close()
        p_server.stderr.close()

    # Start the Mail Spool
    path_icms_start_spool = join(script_path, 'icms-start-spool.py')
    args = '%s %s' % (path_icms_start_spool, target)
    p_spool = Popen(args, 0, None, stdin, stdout, stderr, shell=True)
    # Detach (FIXME Output from the child is lost)
    if options.detach:
        p_spool.stdin.close()
        p_spool.stdout.close()
        p_spool.stderr.close()

    # Debugging mode
    if options.detach is False:
        try:
            p_server.wait()
        except KeyboardInterrupt:
            print "Terminated by user."
        except:
            pass



if __name__ == '__main__':
    # The command line parser
    usage = ('%prog [OPTIONS] TARGET\n'
             '       %prog TARGET [TARGET]*')
    version = 'itools %s' % itools.__version__
    description = ('Starts a web server that publishes the TARGET itools.cms'
                   ' instance to the world. If several TARGETs are given, one'
                   ' server will be started for each one (in this mode no'
                   ' options are available).')
    parser = OptionParser(usage, version=version, description=description)
    parser.add_option(
        '-a', '--address', help='listen to IP ADDRESS')
    parser.add_option(
        '', '--debug', action="store_true", default=False,
        help="Start the server on debug mode.")
    parser.add_option(
        '-d', '--detach', action="store_true", default=False,
        help="Detach from the console.")
    parser.add_option(
        '-p', '--port', type='int', help='listen to PORT number')

    options, args = parser.parse_args()
    n_args = len(args)
    if n_args == 0:
        parser.error('The TARGET argument is missing.')
    elif n_args == 1:
        pass
    elif options.address or options.debug or options.detach or options.port:
        parser.error(
            'Options are not available when starting several servers at once.')

    # Action!
    for target in args:
        start(parser, options, target)
