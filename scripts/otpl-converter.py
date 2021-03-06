#!/usr/bin/env python3
"""Convert between the brat and OTPL (one token per line) standoff formats."""
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

from otplc import ColumnSpecification, otpl_to_brat, Configuration, __version__


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'

# Command-line interface setup
# NB: positive exit values indicate the number of failed conversions
#     negative exit values reference some bad [exit] state defined here
# noinspection PyUnresolvedReferences
epilog = "colspec names: %s" % ' '.join(ColumnSpecification.NAMES.keys())
parser = ArgumentParser(usage='%(prog)s [options] TARGET FILE [FILE ...]',
                        description=__doc__, epilog=epilog, prog=os.path.basename(sys.argv[0]))
parser.add_argument('format', metavar='TARGET', choices=['otpl', 'brat'],
                    help='generate {otpl, brat} files from the other  (ann->lst, lst->ann)')
parser.add_argument('files', metavar='FILE', nargs='+',
                    help='the (annotated) UTF-8 plain-text file(s)')
parser.add_argument('--filter', metavar='REGEX',
                    help='filter (skip) lines in input annotation file matching REGEX [none]')
parser.add_argument('--name-labels', metavar='FILE',
                    help='mappings for labels (in brat\'s visual.conf format: '
                         '"brat_label | otpl_label"; see OTPLC\'s data directory for examples)')

# OTPL-specific options
parser.add_argument('--otpl-suffix', metavar='SUFFIX', default=Configuration.OTPL_SUFFIX,
                    help='OTPL annotation file SUFFIX (line-separated tokens) ["%(default)s"]')
parser.add_argument('--separator', metavar='REGEX',
                    help='OTPL field separator REGEX (without surrounding slashes; '
                         '/\\s+/ and /\\t/ are auto-detected)')
parser.add_argument('--colspec', metavar='SPEC',
                    help='provide an OTPL colspec string [auto-detected]')

# brat-specific options
parser.add_argument('--brat-suffix', metavar='SUFFIX', default=Configuration.BRAT_SUFFIX,
                    help='brat annotation file SUFFIX ["%(default)s"]')
parser.add_argument('--config', metavar='FILE', default=Configuration.CONFIG,
                    help='brat annotation configuration file ["%(default)s"]')

# logging/info options
parser.add_argument('--version', action='version', version='v%s' % __version__)
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

if args.name_labels:
    mappings = {}

    for line in open(args.name_labels, encoding=config.encoding):
        if " | " in line:
            name, label = line.split(' | ', 1)
            mappings[label.strip()] = name.strip()

    config.name_labels = mappings

config.brat_suffix = args.brat_suffix
config.otpl_suffix = args.otpl_suffix
config.config = args.config
config.filter = args.filter
config.separator = args.separator

if args.format == 'brat':
    # Convert OTPL annotations into brat files
    # Exit value: number of failed conversions
    sys.exit(otpl_to_brat(config))
else:
    logging.error('%s conversion not yet supported', args.format)
    sys.exit(-1)
