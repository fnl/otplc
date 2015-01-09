#!/usr/bin/env python
"""Segment a large OTPL file into smaller pieces."""
# The MIT License (MIT)
#
# Copyright (c) 2014 Florian Leitner <florian.leitner@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
import logging
from os.path import splitext
import os
import sys
from argparse import ArgumentParser
from otplc import Configuration


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'


# Argument parser setup
parser = ArgumentParser(usage='%(prog)s [options] FILE [FILE ...]',
                        description=__doc__, prog=os.path.basename(sys.argv[0]))
parser.add_argument('files', metavar='FILE', nargs='+',
                    help='the OTPL file(s)')
parser.add_argument('--factor', metavar='FACTOR', type=int, default=20,
                    help='split into files after every FACTOR segments [%(default)d]')

# Logging
parser.add_argument('--verbose', '-v', action='count', default=0,
                    help='increase log level [WARN]')
parser.add_argument('--quiet', '-q', action='count', default=0,
                    help='decrease log level [WARN]')

args = parser.parse_args()

# Logging setup
log_adjust = max(min(args.quiet - args.verbose, 2), -2) * 10
logging.basicConfig(level=logging.WARNING + log_adjust,
                    format='%(levelname)-8s %(module) 10s: %(funcName)s %(message)s')
logging.info('verbosity increased')
logging.debug('verbosity increased')

for in_file in args.files:
    base, ext = splitext(in_file)
    filecount = 0
    segments = 0
    out_stream = None

    with open(in_file, encoding=Configuration.ENCODING) as in_stream:
        for lno, raw in enumerate(in_stream, 1):
            if segments % args.factor == 0:
                if out_stream is not None:
                    out_stream.close()

                filecount += 1
                out_file = "%s-%i%s" % (base, filecount, ext)
                out_stream = open(out_file, encoding=Configuration.ENCODING, mode='wt')

            line = raw.strip()

            if not line:
                segments += 1
                print('', file=out_stream)
            else:
                print(line, file=out_stream)

    if out_stream is not None:
        out_stream.close()
