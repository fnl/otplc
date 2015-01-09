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
        self.text_files = input_files
        self.brat_suffix = Configuration.BRAT_SUFFIX
        self.otpl_suffix = Configuration.OTPL_SUFFIX
        self.text_suffix = Configuration.TEXT_SUFFIX
        self.config = Configuration.CONFIG
        self.encoding = Configuration.ENCODING
        self.filter = None
        self.colspec = None
        self.separator = None
        self.name_labels = None
