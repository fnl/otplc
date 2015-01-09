# coding=utf-8
import logging
from tempfile import NamedTemporaryFile
from os import remove
from otplc import guess_colspec, configure_reader, Configuration
from otplc.converter import OtplBratConverter
from otplc.test_base import OtplTestBase

__author__ = 'Florian Leitner <florian.leitner@gmail.com>'


class TestConverter(OtplTestBase):

    def setUp(self):
        super(TestConverter, self).setUp()
        config = Configuration([__file__])
        config.separator = r'\s+'
        self.segments = configure_reader(self.otpl_file.name, config)

    def testDefault(self):
        logging.getLogger().addHandler(logging.StreamHandler())  # might spam your console...
        self.interceptLogs('otplc.converter')
        self.text_file.write('This is Florianʼs weird test.')
        self.text_file.close()
        self.segments.filter = r'^%'
        self.otpl_file.write(
            "This    DT  6 nsubj B-NP NULL\n"
            "is      VBZ 6 cop   B-VP NULL\n"
            "% a comment line in %\n"
            "Florian NNP 6 nn    B-NP NULL\n"
            "ʼs      POS 3 pos   I-NP db:id\n"
            "weird   JJ  6 amod  I-NP NULL\n"
            "test    NN  0 root  I-NP NULL\n"
            ".       DOT 6 punct O    NULL\n\n"
        )
        expected = [
            "T1	DT 0 4	This",
            "T2	VBZ 5 7	is",
            "T3	NNP 8 15	Florian",
            "T4	POS 15 17	ʼs",
            "T5	JJ 18 23	weird",
            "T6	NN 24 28	test",
            "T7	DOT 28 29	.",
            "T8	NP 0 4	This",
            "T9	VP 5 7	is",
            "T10	NP 8 28	Florianʼs weird test",
            "R1	nsubj Arg1:T1 Arg2:T6",
            "R2	cop Arg1:T2 Arg2:T6",
            "R3	nn Arg1:T3 Arg2:T6",
            "R4	pos Arg1:T4 Arg2:T3",
            "R5	amod Arg1:T5 Arg2:T6",
            "R6	punct Arg1:T7 Arg2:T6",
            "N1	Reference T10 db:id	db:id",
        ]
        self.otpl_file.close()
        self.brat_file.close()
        converter = OtplBratConverter()
        converter.set_colspec(guess_colspec(self.segments))
        self.assertTrue(converter.convert(
            self.segments, self.text_file.name, self.brat_file.name
        ))

        for lno, line in enumerate(open(self.brat_file.name)):
            line = line.strip('\r\n')
            self.assertEqual(expected[lno], line)

    def testUnmatchedTokens(self):
        self.interceptLogs('otplc.converter')
        self.text_file.write('This is Florianʼs weird test.')
        self.text_file.close()
        self.otpl_file.write(
            "This DT 6 nsubj B-NP NULL\n"
            "is VBZ 6 cop B-VP NULL\n"
            "Florian NNP 6 nn B-NP NULL\n"
            "ʼs POS 3 pos I-NP mailto:florian.leitner@gmail.com\n"
            "weird JJ 6 amod I-NP NULL\n"
            "anti-test NN 0 root I-NP NULL\n"
            ". . 6 punct O NULL\n\n"
        )
        self.otpl_file.close()
        self.brat_file.close()
        converter = OtplBratConverter()
        converter.set_colspec(guess_colspec(self.segments))
        self.assertFalse(converter.convert(
            self.segments, self.text_file.name, self.brat_file.name
        ))
        self.test_log.assertMatches(
            'failed - %s', levelname='WARNING',
            args=('token "anti-test" from line 6 not found at " test." (23)',)
        )

    def testMissingColspec(self):
        self.interceptLogs('otplc.converter')
        self.text_file.close()
        self.otpl_file.close()
        self.brat_file.close()
        converter = OtplBratConverter()
        self.assertFalse(converter.convert(
            self.segments, self.text_file.name, self.brat_file.name
        ))
        self.test_log.assertMatches('cannot run without a colspec - specify one manually',
                                    levelname='WARNING')

    def testWriteConfigurationFile(self):
        self.text_file.write('T1 T2 T3 T4\nT1T2-T3\n')
        self.text_file.close()
        self.otpl_file.write(
            "T1 ent1 att1 1 rel1 1 2 evt1 att1\n"
            "T2 ent2 NULL 3 rel2 0 3 NULL NULL\n"
            "T3 ent1 NULL 4 rel2 3 4 evt1 att2\n"
            "T4 ent2 att1 3 rel3 4 2 evt2 att1\n\n"
            "T1 ent3 NULL 1 rel1 3 1 evt1 att2\n"
            "T2 ent1 NULL 3 rel1 3 2 evt2 NULL\n"
            "T3 ent2 att1 2 rel3 3 0 evt2 att2\n\n"
        )
        self.otpl_file.close()
        config_file = NamedTemporaryFile(suffix='.conf', delete=False)
        config_file.close()
        converter = OtplBratConverter()
        converter.set_colspec(guess_colspec(self.segments))
        self.assertTrue(converter.convert(
            self.segments, self.text_file.name, self.brat_file.name
        ))
        converter.write_config_file(config_file.name)
        expected = [
            '', '[entities]', '',
            'ent1',
            'ent2',
            'ent3',
            '', '[relations]', '',
            'rel1\tArg1:<ENTITY>, Arg2:<ENTITY>',
            'rel2\tArg1:<ENTITY>, Arg2:<ENTITY>',
            'rel3\tArg1:<ENTITY>, Arg2:<ENTITY>',
            '', '[events]', '',
            'evt1\tCol7:<ENTITY>',
            'evt2\tCol7?:<ENTITY>',
            '', '[attributes]', '',
            'att1\tArg:<ANY>',
            'att2\tArg:<EVENT>',
        ]

        for lno, raw in enumerate(open(config_file.name, 'rb')):
            line = raw.decode('utf-8').strip()
            self.assertEqual(expected[lno], line)

        remove(config_file.name)
