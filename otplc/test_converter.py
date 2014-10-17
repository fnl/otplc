# coding=utf-8
import logging
from tempfile import NamedTemporaryFile
from os import remove
from otplc import guess_colspec, configure_reader
from otplc.converter import OtplBratConverter
from otplc.test_base import OtplTestBase

__author__ = 'Florian Leitner <florian.leitner@gmail.com>'


class TestConverter(OtplTestBase):

    def setUp(self):
        super(TestConverter, self).setUp()
        self.segments = configure_reader(self.otpl_file.name, sep_regex=r'\s+')

    def testDefault(self):
        logging.getLogger().addHandler(logging.StreamHandler())  # might spam your console...
        self.interceptLogs('otplc.converter')
        self.text_file.write(u'This is Florianʼs weird test.'.encode('utf-8'))
        self.text_file.close()
        self.segments.filter = r'^%'
        self.otpl_file.write(
            u"This    DT  6 nsubj B-NP NULL\n"
            u"is      VBZ 6 cop   B-VP NULL\n"
            u"% a comment line in %\n"
            u"Florian NNP 6 nn    B-NP NULL\n"
            u"ʼs      POS 3 pos   I-NP db:id\n"
            u"weird   JJ  6 amod  I-NP NULL\n"
            u"test    NN  0 root  I-NP NULL\n"
            u".       DOT 6 punct O    NULL\n\n".encode('utf-8')
        )
        expected = [
            u"T1	DT 0 4	This",
            u"T2	VBZ 5 7	is",
            u"T3	NNP 8 15	Florian",
            u"T4	POS 15 17	ʼs",
            u"T5	JJ 18 23	weird",
            u"T6	NN 24 28	test",
            u"T7	DOT 28 29	.",
            u"T8	NP 0 4	This",
            u"T9	VP 5 7	is",
            u"T10	NP 8 28	Florianʼs weird test",
            u"R1	nsubj Arg1:T1 Arg2:T6",
            u"R2	cop Arg1:T2 Arg2:T6",
            u"R3	nn Arg1:T3 Arg2:T6",
            u"R4	pos Arg1:T4 Arg2:T3",
            u"R5	amod Arg1:T5 Arg2:T6",
            u"R6	punct Arg1:T7 Arg2:T6",
            u"N1	Reference T10 db:id	db:id",
        ]
        self.otpl_file.close()
        self.brat_file.close()
        converter = OtplBratConverter()
        converter.set_colspec(guess_colspec(self.segments))
        self.assertTrue(converter.convert(
            self.segments, self.text_file.name, self.brat_file.name
        ))

        for lno, line in enumerate(open(self.brat_file.name, 'rt')):
            line = line.decode('UTF-8').strip('\r\n')
            self.assertEqual(expected[lno], line)

    def testUnmatchedTokens(self):
        self.interceptLogs('otplc.converter')
        self.text_file.write(u'This is Florianʼs weird test.'.encode('utf-8'))
        self.text_file.close()
        self.otpl_file.write(
            u"This DT 6 nsubj B-NP NULL\n"
            u"is VBZ 6 cop B-VP NULL\n"
            u"Florian NNP 6 nn B-NP NULL\n"
            u"ʼs POS 3 pos I-NP mailto:florian.leitner@gmail.com\n"
            u"weird JJ 6 amod I-NP NULL\n"
            u"anti-test NN 0 root I-NP NULL\n"
            u". . 6 punct O NULL\n\n".encode('utf-8')
        )
        self.otpl_file.close()
        self.brat_file.close()
        converter = OtplBratConverter()
        converter.set_colspec(guess_colspec(self.segments))
        self.assertFalse(converter.convert(
            self.segments, self.text_file.name, self.brat_file.name
        ))
        self.test_log.assertMatches(
            u'failed - %s', levelname='WARNING',
            args=(u'token "anti-test" from line 6 not found at " test." (23)',)
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
        self.test_log.assertMatches(u'cannot run without a colspec - specify one manually',
                                    levelname='WARNING')

    def testWriteConfigurationFile(self):
        self.text_file.write(u'T1 T2 T3 T4\nT1T2-T3\n'.encode('utf-8'))
        self.text_file.close()
        self.otpl_file.write(
            u"T1 ent1 att1 1 rel1 1 2 evt1 att1\n"
            u"T2 ent2 NULL 3 rel2 0 3 NULL NULL\n"
            u"T3 ent1 NULL 4 rel2 3 4 evt1 att2\n"
            u"T4 ent2 att1 3 rel3 4 2 evt2 att1\n\n"
            u"T1 ent3 NULL 1 rel1 3 1 evt1 att2\n"
            u"T2 ent1 NULL 3 rel1 3 2 evt2 NULL\n"
            u"T3 ent2 att1 2 rel3 3 0 evt2 att2\n\n".encode('utf-8')
        )
        self.otpl_file.close()
        config_file = NamedTemporaryFile(suffix=u'.conf', delete=False)
        config_file.close()
        converter = OtplBratConverter()
        converter.set_colspec(guess_colspec(self.segments))
        self.assertTrue(converter.convert(
            self.segments, self.text_file.name, self.brat_file.name
        ))
        converter.write_config_file(config_file.name)
        expected = [
            u'', u'[entities]', u'',
            u'ent1',
            u'ent2',
            u'ent3',
            u'', u'[relations]', u'',
            u'rel1\tArg1:<ENTITY>, Arg2:<ENTITY>',
            u'rel2\tArg1:<ENTITY>, Arg2:<ENTITY>',
            u'rel3\tArg1:<ENTITY>, Arg2:<ENTITY>',
            u'', u'[events]', u'',
            u'evt1\tCol7:<ENTITY>',
            u'evt2\tCol7?:<ENTITY>',
            u'', u'[attributes]', u'',
            u'att1\tArg:<ANY>',
            u'att2\tArg:<EVENT>',
        ]

        for lno, raw in enumerate(open(config_file.name, 'rb')):
            line = raw.decode('utf-8').strip()
            self.assertEqual(expected[lno], line)

        remove(config_file.name)
