#!/usr/bin/env python3
"""Extract the tokens of OTPL (one token per line) files into separate plain-text files."""
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
import os
import sys
from argparse import ArgumentParser
from otplc import Configuration, ColumnSpecification
from otplc.extractor import otpl_to_text, segment_otpl_file


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'


# Argument parser setup
comment = "One line per segment; one output (text) file per input (OTPL) file."
parser = ArgumentParser(usage='%(prog)s [options] FILE [FILE ...]',
                        description=__doc__, epilog=comment, prog=os.path.basename(sys.argv[0]))
parser.add_argument('files', metavar='FILE', nargs='+',
                    help='the OTPL file(s)')

parser.add_argument('--segment', metavar='FACTOR', type=int, default=0,
                    help='split OTPL files after every FACTOR segments before extracting '
                         '(generates new OTPL file)')

# Text output
parser.add_argument('--text-suffix', metavar='SUFFIX', default=Configuration.TEXT_SUFFIX,
                    help='output text file SUFFIX ["%(default)s"]')

# OTPL parsing
parser.add_argument('--filter', metavar='REGEX',
                    help='filter (skip) lines in input annotation file matching REGEX [none]')
parser.add_argument('--separator', metavar='REGEX',
                    help='OTPL field separator REGEX (without surrounding slashes; '
                         '/\\s+/ and /\\t/ are auto-detected)')
parser.add_argument('--colspec', metavar='SPEC',
                    help='provide an OTPL colspec string [auto-detected]')

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

try:
    config = Configuration(args.files)
except AssertionError as e:
    logging.error(str(e))
    sys.exit(-2)

if args.colspec:
    try:
        config.colspec = ColumnSpecification.from_string(args.colspec)
    except ValueError as e:
        logging.error("colspec parsing failed: %s", str(e))
        sys.exit(-3)

config.text_suffix = args.text_suffix
config.filter = args.filter
config.separator = args.separator

if args.segment > 0:
    segment_file_names = []

    for otpl_file in config.text_files:
        segment_file_names.extend(segment_otpl_file(otpl_file, args.segment, config.encoding))

    config.text_files = segment_file_names

sys.exit(otpl_to_text(config))
