# coding=utf-8
from io import TextIOWrapper
import os
from mock import MagicMock, patch, sentinel, call
from unittest import TestCase
from otplc.brat import Entity, Event, Relation, Attribute, Normalization, Equiv, Note, read, write


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'


class TestAnnotation(TestCase):
    STRING = None

    def assertStringify(self, Klass):
        ann = Klass.from_string(self.STRING)
        self.assertEqual(self.STRING, str(ann))
        self.assertAttributes(ann)
        return ann

    def assertAttributes(self, ann):
        self.assertEqual('ID', ann.uid)

        if isinstance(ann, Normalization):
            self.assertEqual('Reference', ann.name)
        else:
            self.assertEqual('name', ann.name)

    def assertIsEqual(self, ann, getAttrs=lambda ann: vars(ann)):
        other = ann.__class__(**getAttrs(ann))
        self.assertEqual(ann, other, '%s != %s' % (str(ann), str(other)))
        self.assertFalse(ann != other)
        other.uid = 'ANOTHER'
        self.assertNotEqual(ann, other)
        self.assertFalse(ann == other)


class TestText(TestAnnotation):

    def assertAttributes(self, ann):
        super(TestText, self).assertAttributes(ann)
        self.assertEqual('text', ann.text)


class TestAssociation(TestAnnotation):
    ARGS = None

    def assertAttributes(self, ann):
        super(TestAssociation, self).assertAttributes(ann)
        self.assertEqual(self.ARGS, ann.args)


class TestEntity(TestText):
    STRING = 'ID\tname 1 5\ttext'

    def test_from_string(self):
        ann = self.assertStringify(Entity)
        self.assertEqual(1, ann.start)
        self.assertEqual(5, ann.end)

    def test_equality(self):
        self.assertIsEqual(Entity.from_string(self.STRING))


class TestNormalization(TestText):
    STRING = 'ID\tReference target db:xref\ttext'

    def test_from_string(self):
        ann = self.assertStringify(Normalization)
        self.assertEqual('target', ann.target)
        self.assertEqual('db', ann.db)
        self.assertEqual('xref', ann.xref)

    def test_equality(self):
        def getAttr(ann):
            attrs = dict(vars(ann))
            del attrs['name']
            return attrs

        self.assertIsEqual(Normalization.from_string(self.STRING), getAttr)


class TestNote(TestText):
    STRING = 'ID\tname target\ttext'

    def test_from_string(self):
        ann = self.assertStringify(Note)
        self.assertEqual('target', ann.target)

    def test_equality(self):
        self.assertIsEqual(Note.from_string(self.STRING))


class TestRelation(TestAssociation):
    STRING = 'ID\tname Arg1:arg1 Arg2:arg2'
    ARGS = {'Arg1': 'arg1', 'Arg2': 'arg2'}

    def test_from_string(self):
        self.assertStringify(Relation)

    def test_add_arguments(self):
        ann = Relation.from_string('ID\tname arg1 arg2')
        self.assertEqual(TestRelation.ARGS, ann.args)

    def test_equality(self):
        def getAttrs(ann):
            attrs = dict(vars(ann))
            attrs['target1'] = attrs['args']['Arg1']
            attrs['target2'] = attrs['args']['Arg2']
            del attrs['args']
            return attrs

        self.assertIsEqual(Relation.from_string(self.STRING), getAttrs)


class TestEvent(TestAssociation):
    STRING = 'ID\tname:trigger Arg1:arg1 Arg2:arg2 Arg3:arg3'
    ARGS = {'Arg1': 'arg1', 'Arg2': 'arg2', 'Arg3': 'arg3'}

    def test_from_string(self):
        ann = self.assertStringify(Event)
        self.assertEqual('trigger', ann.trigger)

    def test_equality(self):
        self.assertIsEqual(Event.from_string(self.STRING))


class TestEquiv(TestAnnotation):
    STRING = 'ID\tname T1 T2 T3'
    TARGETS = ('T1', 'T2', 'T3')

    def test_from_string(self):
        ann = self.assertStringify(Equiv)
        self.assertEqual(TestEquiv.TARGETS, ann.targets)

    def test_str(self):
        case = 'the\tuni\U00011111code test'
        ann = Equiv.from_string(case)
        self.assertSequenceEqual(case, str(ann))

    def test_equality(self):
        self.assertIsEqual(Equiv.from_string(self.STRING))


class TestAttribute(TestAnnotation):
    STRING = 'ID\tname target'

    def test_from_string(self):
        ann = self.assertStringify(Attribute)
        self.assertEqual('target', ann.target)
        self.assertEqual(None, ann.modifier)

    def test_with_value(self):
        ann = Attribute.from_string('ID\tname target modifier')
        self.assertEqual('modifier', ann.modifier)

    def test_equality(self):
        self.assertIsEqual(Attribute.from_string(self.STRING))


class TestRead(TestCase):

    def assertRead(self, expected_anns, string_anns):
        expected_anns = list(reversed(expected_anns))

        with patch('builtins.open', create=True) as open_mock:
            open_mock.return_value = MagicMock(spec=TextIOWrapper)
            handle = open_mock.return_value.__enter__.return_value
            handle.__iter__.return_value = string_anns

            for ann in read(sentinel.file_path):
                self.assertEqual(expected_anns.pop(), ann)

        self.assertEqual(0, len(expected_anns), ', '.join(ann.uid for ann in expected_anns))

    def test_normal(self):
        cases = [Entity('T1', 'name', 0, 4, 'text'), Attribute('A1', 'name', 'target')]
        raw = ['%s%s' % (str(c), os.linesep) for c in cases]
        self.assertRead(cases, raw)


class TestWrite(TestCase):

    def assertWrite(self, expected_lines, annotations):
        file_mock = MagicMock(spec=TextIOWrapper)
        expected_lines = [(l, os.linesep) for l in expected_lines]
        expected_lines = [item for pair in expected_lines for item in pair]

        with patch('builtins.open', create=True) as open_mock:
            open_mock.return_value.__enter__.return_value = file_mock
            write(sentinel.file_path, annotations)

        for expected, real in zip(expected_lines, file_mock.write.call_args_list):
            self.assertEqual(call(expected), real)

        self.assertEqual(len(expected_lines), len(file_mock.write.call_args_list))

    def test_normal(self):
        cases = [Entity('T1', 'Entity', 0, 3, 'txt'), Attribute('A1', 'Attribute', 'T1')]
        raw = ['%s' % str(c) for c in cases]
        self.assertWrite(raw, cases)
