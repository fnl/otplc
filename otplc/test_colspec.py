# coding=utf-8
from otplc.colspec import ColumnSpecification as C
from otplc.test_base import OtplTestBase

__author__ = 'Florian Leitner <florian.leitner@gmail.com>'


class TestColspec(OtplTestBase):

    def testParseColspec(self):
        self.interceptLogs('otplc.colspec')
        # noinspection PyUnresolvedReferences
        names, values = zip(*C.NAMES.items())
        self.assertSequenceEqual(values, C.parse_colspec(' '.join(names)))
        self.test_log.assertMatches(
            u'using an internal colspec type; probably a Bad Idea', levelname='WARNING', count=2
        )

    def testInitialization(self):
        colspec = [
            C.SEGMENT_ID, C.GLOBAL_ENUM, C.LOCAL_ENUM, C.TOKEN,
            C.POS_TAG, C.LOCAL_REF, C.RELATION,
            C.ENTITY, C.GLOBAL_REF, C.GLOBAL_REF, C.EVENT, C.ATTRIBUTE, C.NORMALIZATION,
            C.LOCAL_REF, C.LOCAL_REF, C.EVENT,
        ]
        converter = C.from_integers(colspec)
        self.assertEqual(1, converter._global_enum)
        self.assertEqual(2, converter._local_enum)
        self.assertEqual(3, converter._token)
        self.assertEqual(4, converter._pos_tag)
        self.assertEqual({7, }, converter._entities)
        self.assertEqual({8: 7, 9: 7}, converter._global_refs)
        self.assertEqual({6: 4}, converter._relations)
        self.assertEqual({10: (8, (9,)), 15: (13, (14,))}, converter._events)
        self.assertEqual({12: 10}, converter._normalizations)  # important: norm of event!
        self.assertEqual({11: 10}, converter._attributes)

    def testUndefinedColumn(self):
        colspec = [1, 2, 3, 4, 50]
        self.assertRaisesRegexp(ValueError, u'unknown _TYPE_ \(50\) column 5',
                                C.from_integers, colspec)

    def testUnassignedReferences(self):
        colspec = [C.LOCAL_ENUM, C.TOKEN, C.LOCAL_REF, C.LOCAL_REF, C.POS_TAG]
        self.assertRaisesRegexp(ValueError, u'LOCAL_REF column 3 has no target',
                                C.from_integers, colspec)

    def testUnknownColumn(self):
        self.interceptLogs('otplc.colspec')
        colspec = [C._UNKNOWN, C.TOKEN]
        C.from_integers(colspec)
        self.test_log.assertMatches(
            u'ignoring _UNKNOWN column %s', args=(1,), levelname='INFO'
        )

    def testAnnotationColumn(self):
        colspec = [C.TOKEN, C._ANNOTATION]
        self.assertRaisesRegexp(ValueError, u'unknown _ANNOTATION \(99\) column 2',
                                C.from_integers, colspec)

    def testMissingColspec(self):
        self.assertRaises(TypeError, C.from_integers, None)

    def testMissingHeader(self):
        self.assertRaises(TypeError, C.from_string, None)

    def testMissingRelationReference(self):
        colspec = [C.TOKEN, C.POS_TAG, C.RELATION]
        self.assertRaisesRegexp(ValueError, u'RELATION column 3 has no reference',
                                C.from_integers, colspec)

    def testMissingEventReference(self):
        colspec = [C.LOCAL_ENUM, C.TOKEN, C.POS_TAG, C.LOCAL_REF, C.EVENT]
        self.assertRaisesRegexp(ValueError, u'EVENT column 5 has less than two references',
                                C.from_integers, colspec)

    def testMissingTargetColumn(self):
        colspec = [C.GLOBAL_ENUM, C.TOKEN, C.NORMALIZATION]
        self.assertRaisesRegexp(ValueError, u'NORMALIZATION column 3 has no target',
                                C.from_integers, colspec)

    def testMissingAnyTargetColumns(self):
        colspec = [C.TOKEN, C.NORMALIZATION]
        self.assertRaisesRegexp(ValueError, u'NORMALIZATION column 2 with no target',
                                C.from_integers, colspec)
