# coding=utf-8
import logging
from os import remove
from otplc import Configuration
from tempfile import NamedTemporaryFile
from unittest import TestCase
from otplc.loggertest import LoggingTestHandler

__author__ = 'Florian Leitner <florian.leitner@gmail.com>'


class OtplTestBase(TestCase):

    """ This test setup might not work on Windows NT (see tempfile docs). """

    def setUp(self):
        self.text_file = NamedTemporaryFile(suffix=Configuration.TEXT_SUFFIX, mode='w+t', delete=False, encoding=Configuration.ENCODING)
        self.otpl_file = NamedTemporaryFile(suffix=Configuration.OTPL_SUFFIX, mode='w+t', delete=False, encoding=Configuration.ENCODING)
        self.brat_file = NamedTemporaryFile(suffix=Configuration.BRAT_SUFFIX, mode='w+t', delete=False, encoding=Configuration.ENCODING)
        self.test_log = LoggingTestHandler(self)
        # logging.getLogger().addHandler(logging.StreamHandler())  # might spam your console...

    def interceptLogs(self, logger_name):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(self.test_log)

    def tearDown(self):
        for file in (self.text_file, self.otpl_file, self.brat_file):
            if not file.closed:
                file.close()

            remove(file.name)

        self.test_log.close()
