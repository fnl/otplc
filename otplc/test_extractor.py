import logging
from mock import patch
from otplc import Configuration
from otplc.converter import make_path_to
from otplc.extractor import otpl_to_text
from otplc.test_base import OtplTestBase


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'

class TestOtplToText(OtplTestBase):

    def setUp(self):
        super(TestOtplToText, self).setUp()
        config = Configuration([__file__])
        config.separator = r'\s+'

    def testDefault(self):
        logging.getLogger().addHandler(logging.StreamHandler())  # might spam your console...
        self.interceptLogs('otplc.extractor')
        self.otpl_file.write(
            "This    DT  6 nsubj B-NP NULL\n"
            "is      VBZ 6 cop   B-VP NULL\n"
            "Florian NNP 6 nn    B-NP NULL\n"
            "ʼs      POS 3 pos   I-NP db:id\n"
            "weird   JJ  6 amod  I-NP NULL\n"
            "test    NN  0 root  I-NP NULL\n"
            ".       DOT 6 punct O    NULL\n\n"
            "And    DT  6 nsubj B-NP NULL\n"
            "another      VBZ 6 cop   B-VP NULL\n"
            "one    NN  0 root  I-NP NULL\n"
            ".       DOT 6 punct O    NULL\n\n"
        )
        self.otpl_file.close()
        expected = 'This is Florian ʼs weird test .\nAnd another one .\n'
        self.assertEqual(0, otpl_to_text(Configuration([self.otpl_file.name])))
        self.assertEqual(expected, open(make_path_to(self.otpl_file.name, Configuration.TEXT_SUFFIX)).read())
