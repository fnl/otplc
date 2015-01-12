"""
OTPL-brat conversion process configuration settings.
"""
from os.path import exists


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'


class Configuration(object):

    """A single configuration parameter object to pass to the conversion functions."""

    OTPL_SUFFIX = '.lst'
    "The default OTPL file suffix."

    BRAT_SUFFIX = '.ann'
    "The default brat annotation file suffix."

    TEXT_SUFFIX = '.txt'
    "The default text file suffix."

    CONFIG = 'annotation.conf'
    "The default name of the brat annotation configuration file."

    ENCODING = 'UTF-8'
    "The default encoding used by all files."

    def __init__(self, input_files):
        for path in input_files:
            assert exists(path), 'file "%s" does not exist' % path

        assert input_files, 'no input files'
        self.input_files = input_files # input files
        self.brat_suffix = Configuration.BRAT_SUFFIX
        self.otpl_suffix = Configuration.OTPL_SUFFIX
        self.text_suffix = Configuration.TEXT_SUFFIX
        self.config = Configuration.CONFIG # configuation file name
        self.encoding = Configuration.ENCODING # character encoding of all files
        self.filter = None # filter regex (skip matching lines)
        self.colspec = None # column specification for OTPL files
        self.separator = None # column separator for OTPL files
        self.name_labels = None  # translations for annotations in the conversion process
