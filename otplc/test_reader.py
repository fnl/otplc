# coding=utf-8
from otplc import ColumnSpecification
from otplc.reader import SPACES, TAB, DataFormatError, configure_reader, guess_colspec
from otplc.test_base import OtplTestBase

__author__ = 'Florian Leitner <florian.leitner@gmail.com>'


class TestReader(OtplTestBase):

    def setUp(self):
        super(TestReader, self).setUp()
        self.segments = configure_reader(self.otpl_file.name, sep_regex=r'\s+')

    def testVariableColumnNumbers(self):
        self.otpl_file.write(u"1\t2\t3\n1\t2\n".encode('utf-8'))
        self.otpl_file.close()
        self.assertRaisesRegexp(DataFormatError, u'line 2 has 2 columns, but expected 3',
                                list, self.segments)

    def testReadingDefaultOtpl(self):
        self.otpl_file.write((
            u"1 seg1 1 tok1 tag1 2 rel1 0 0 null\n"
            u"2 seg1 2 tok2 tag2 0 null 2 1 ent1\n\n"
            u"3 seg2 1 tok3 tag3 0 null 3 1 ent2\n"
            u"4 seg2 2 tok4 tag4 1 rel2 0 0 null\n\n"
        ).encode('utf-8'))
        self.otpl_file.close()
        expected_segments = [
            [[u'1', u'seg1', u'1', u'tok1', u'tag1', u'2', u'rel1', u'0', u'0', u'null'],
             [u'2', u'seg1', u'2', u'tok2', u'tag2', u'0', u'null', u'2', u'1', u'ent1'], ],
            [[u'3', u'seg2', u'1', u'tok3', u'tag3', u'0', u'null', u'3', u'1', u'ent2'],
             [u'4', u'seg2', u'2', u'tok4', u'tag4', u'1', u'rel2', u'0', u'0', u'null'], ],
        ]
        actual_segments = list(self.segments)
        self.assertEqual(len(expected_segments), len(actual_segments))

        for expected, actual in zip(expected_segments, actual_segments):
            self.assertListEqual(expected, actual)

    def testGuessSepSpaces(self):
        self.otpl_file.write((u"1 tok1\ttag1\n2 tok2\ttag2\n\n"
                              u"1 tok3\ttag3\n2 tok4\ttag4\n\n").encode('utf-8'))
        self.otpl_file.close()
        self.assertTrue(self.segments.detect_separator())
        self.assertEqual(SPACES.pattern, self.segments.separator)

    def testGuessSepTab(self):
        self.otpl_file.write((u"1\ttok 1\ttag 1\n2\ttok2\ttag 2\n\n"
                              u"1\ttok 3\ttag 3\n2\ttok4\ttag 4\n\n").encode('utf-8'))
        self.otpl_file.close()
        self.assertTrue(self.segments.detect_separator())
        self.assertEqual(TAB.pattern, self.segments.separator)

    def testGuessColspecDefault(self):
        header = u"GLOBAL_ENUM SEGMENT_ID LOCAL_ENUM TOKEN POS_TAG ENTITY NORMALIZATION "\
            u"LOCAL_REF RELATION GLOBAL_REF LOCAL_REF EVENT ENTITY ATTRIBUTE"
        self.guessColspec(
            u"1 seg1 1 tok1 pos1 B-tag1 ns:id1 2 rel1 0 0 null O att1\n"
            u"2 seg1 2 tok2 pos2 I-tag2 ns:id2 0 null 2 1 ent1 E-tag att2\n\n"
            u"3 seg2 1 tok3 pos3 B-tag3 ns:id3 0 null 3 1 ent2 I-tag att3\n"
            u"4 seg2 2 tok4 pos4 I-tag4 ns:id4 1 rel2 0 0 null E-tag att4\n\n",
            header)

    def testColspecHeader(self):
        # note that normally, the first ENTITY would be guessed as a POS_TAG
        header = u"SEGMENT_ID TOKEN ENTITY ENTITY LOCAL_REF:4 LOCAL_REF:7 EVENT"
        self.guessColspec(
            u"%s\n\n"
            u"1 tok1 ent1 ent5 2 2 event1\n"
            u"1 tok2 ent2 ent6 3 1 event2\n"
            u"1 tok3 ent3 ent7 1 3 event3\n\n"
            u"2 tok4 ent4 ent8 1 1 event4\n\n" % (header),
            header
        )

    def testColspecPoSDepNorm(self):
        self.guessColspec(
            u"This    DT  6 nsubj B-NP NULL\n"
            u"is      VBZ 6 cop   B-VP NULL\n"
            u"Florian NNP 6 nn    B-NP NULL\n"
            u"ʼs      POS 3 pos   I-NP mailto:florian.leitner@gmail.com\n"
            u"weird   JJ  6 amod  I-NP NULL\n"
            u"test    NN  0 root  I-NP NULL\n"
            u".       .   6 punct O    NULL\n\n",
            u"TOKEN POS_TAG LOCAL_REF RELATION ENTITY NORMALIZATION"
        )

    def testGuessColspecThreeEnums(self):
        self.interceptLogs('otplc.reader')
        self.guessColspec(
            u"1 1 1 token1\n"
            u"2 2 2 token2\n"
            u"3 3 3 token3\n\n"
            u"4 1 1 token4\n"
            u"5 2 2 token5\n\n",
            u"GLOBAL_ENUM _UNKNOWN LOCAL_ENUM TOKEN"
        )
        # assert count == 2 because of the "one last round" guess:
        self.test_log.assertMatches(u'at column %s: already detected two enumeration columns',
                                    args=(3,), count=2)

    def testGuessColspecDependecy(self):
        self.guessColspec(
            u"1 This DT B-NP NULL 6 nsubj\n"
            u"2 is VBZ B-VP NULL 6 cop\n"
            u"3 Florian NNP B-NP mailto:florian.leitner@gmail.com 6 nn\n"
            u"4 ʼs POS I-NP NULL 3 pos\n"
            u"5 weird JJ I-NP NULL 6 amod\n"
            u"6 test NN I-NP NULL 0 root\n"
            u"7 . . O NULL 6 punct\n\n",
            u"LOCAL_ENUM TOKEN POS_TAG ENTITY NORMALIZATION LOCAL_REF RELATION"
        )

    def testGuessGlobalRef(self):
        self.guessColspec(
            u"tok1 pos1 3 rel1\n"
            u"tok2 pos2 1 rel1\n\n"
            u"tok3 pos3 2 rel1\n"
            u"tok4 pos4 5 rel1\n\n"
            u"tok5 pos5 6 rel1\n"
            u"tok6 pos6 4 rel1\n\n",
            u"TOKEN POS_TAG GLOBAL_REF RELATION"
        )

    def testGuessLocalRef(self):
        self.guessColspec(
            u"tok1 pos1 2 rel1\n"
            u"tok2 pos2 1 rel1\n\n"
            u"tok3 pos3 2 rel1\n"
            u"tok4 pos4 1 rel1\n\n"
            u"tok5 pos5 0 NULL\n"
            u"tok6 pos6 0 NULL\n\n",
            u"TOKEN POS_TAG LOCAL_REF RELATION"
        )

    def guessColspec(self, otpl_unicode, header):
        self.otpl_file.write(otpl_unicode.encode('utf-8'))
        self.otpl_file.close()
        expected = ColumnSpecification.from_string(header)
        result = guess_colspec(self.segments)
        self.assertSequenceEqual(str(expected), str(result))
        self.assertEqual(expected, result)
