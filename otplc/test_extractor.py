import logging
from os import remove
from os.path import splitext
from tempfile import NamedTemporaryFile
from unittest import TestCase
from otplc import Configuration
from otplc.converter import make_path_to
from otplc.extractor import otpl_to_text, segment_otpl_file
from otplc.test_base import OtplTestBase


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'


class TestSegmentOtplFile(TestCase):

    def setUp(self):
        self.otpl_file = NamedTemporaryFile(suffix=Configuration.OTPL_SUFFIX, mode='w+t',
                                            delete=False, encoding=Configuration.ENCODING)

    def tearDown(self):
        if not self.otpl_file.closed:
            self.otpl_file.close()

        remove(self.otpl_file.name)

    def testSegmentation(self):
        self.otpl_file.write('1\n1\n\n2\n2\n2\n\n3\n\n4\n\n5\n5\n\n6\n\n7\n\n')
        self.otpl_file.close()
        basename, ext = splitext(self.otpl_file.name)
        expected = ["%s-%i%s" % (basename, i, ext) for i in range(4)]
        result = segment_otpl_file(self.otpl_file.name, 2, Configuration.ENCODING)
        self.assertEqual(expected, result)
        expected = ['1\n1\n\n2\n2\n2\n\n', '3\n\n4\n\n', '5\n5\n\n6\n\n', '7\n\n']

        for i, outfile in enumerate(result):
            content = open(outfile, encoding=Configuration.ENCODING).read()
            self.assertEqual(expected[i], content)
            remove(outfile)


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
        result = open(make_path_to(self.otpl_file.name, Configuration.TEXT_SUFFIX)).read()
        self.assertEqual(expected, result)