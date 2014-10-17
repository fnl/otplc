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

    CONFIG = 'annotation.conf'
    "The default name of the brat annotation configuration file."

    def __init__(self, text_files):
        for path in text_files:
            assert exists(path), 'file "%s" does not exist' % path

        assert text_files, 'no text files'
        self.text_files = text_files
        self.brat_suffix = Configuration.BRAT_SUFFIX
        self.otpl_suffix = Configuration.OTPL_SUFFIX
        self.config = Configuration.CONFIG
        self.filter = None
        self.colspec = None
        self.separator = None
        self.name_labels = None
