# coding=utf-8
from unittest import TestCase
from otplc.brat import Entity, Event, Relation, Attribute, Normalization, Equiv, Note

__author__ = 'Florian Leitner <florian.leitner@gmail.com>'


class TestAnnotation(TestCase):

    STRING = None

    def assertStringify(self, Klass):
        ann = Klass.from_string(self.STRING)
        self.assertEqual(self.STRING, str(ann))
        self.assertAttributes(ann)
        return ann

    def assertAttributes(self, ann):
        self.assertEqual(u'ID', ann.uid)
        self.assertEqual(u'name', ann.name)


class TestText(TestAnnotation):

    def assertAttributes(self, ann):
        super(TestText, self).assertAttributes(ann)
        self.assertEqual(u'text', ann.text)


class TestAssociation(TestAnnotation):

    ARGS = None

    def assertAttributes(self, ann):
        super(TestAssociation, self).assertAttributes(ann)
        self.assertEqual(self.ARGS, ann.args)


class TestEntity(TestText):

    STRING = 'ID\tname 1 2\ttext'

    def test_from_string(self):
        ann = self.assertStringify(Entity)
        self.assertEqual(1, ann.start)
        self.assertEqual(2, ann.end)


class TestNormalization(TestText):

    STRING = 'ID\tname target xref\ttext'

    def test_from_string(self):
        ann = self.assertStringify(Normalization)
        self.assertEqual(u'target', ann.target)
        self.assertEqual(u'xref', ann.xref)


class TestNote(TestText):

    STRING = 'ID\tname target\ttext'

    def test_from_string(self):
        ann = self.assertStringify(Note)
        self.assertEqual(u'target', ann.target)


class TestRelation(TestAssociation):

    STRING = 'ID\tname Arg1:arg1 Arg2:arg2'
    ARGS = (u'Arg1:arg1', u'Arg2:arg2')

    def test_from_string(self):
        self.assertStringify(Relation)

    def test_add_arguments(self):
        ann = Relation.from_string(u'ID\tname arg1 arg2')
        self.assertEqual(TestRelation.ARGS, ann.args)


class TestEvent(TestAssociation):

    STRING = 'ID\tname:trigger arg1 arg2 arg3'
    ARGS = (u'arg1', u'arg2', u'arg3')

    def test_from_string(self):
        ann = self.assertStringify(Event)
        self.assertEqual(u'trigger', ann.trigger)


class TestEquiv(TestAssociation):

    STRING = 'ID\tname arg1 arg2 arg3'
    ARGS = (u'arg1', u'arg2', u'arg3')

    def test_from_string(self):
        self.assertStringify(Equiv)

    def test_unicode(self):
        case = u'the\tuni\U00011111code test'
        ann = Equiv.from_string(case.encode('UTF-8'))
        self.assertSequenceEqual(case, unicode(ann))


class TestAttribute(TestAnnotation):

    STRING = 'ID\tname target'

    def test_from_string(self):
        ann = self.assertStringify(Attribute)
        self.assertEqual(u'target', ann.target)
        self.assertEqual(None, ann.value)

    def test_with_value(self):
        ann = Attribute.from_string(u'ID\tname target value')
        self.assertEqual(u'value', ann.value)
