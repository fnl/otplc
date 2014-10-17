"""
A clear and Unicode-aware implementation of the brat annotation type system.
All annotation types provide a class-method ``from_string`` to parse a binary string in UTF-8
that returns the corresponding type object.
And all types can be transformed to Unicode strings (:func:`unicode`) or be serialized to binary
strings (:func:`str`) in UTF-8 encoding.
"""
from logging import getLogger
import os


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'
L = getLogger('otplc.brat')


class _Annotation(object):

    """
    All annotation types are guaranteed to provide a ``uid`` and ``name`` attribute.
    """

    @classmethod
    def _parse(cls, line):
        """uid``\\t``name`` ``..."""
        uid, rest = line.decode('utf-8').split(u'\t', 1)
        name, rest = rest.split(u' ', 1)
        return uid, name, rest

    def __init__(self, uid, name):
        self.uid = uid
        self.name = name

    def __str__(self):
        return unicode(self).encode('utf-8')


class _Text(_Annotation):

    """
    All text types in addition to ``uid`` and ``name`` have a ``text`` attribute.
    """

    @classmethod
    def _parse(cls, line):
        """uid``\\t``name`` ``...``\\t``text"""
        uid, name, rest = super(_Text, cls)._parse(line)
        rest, text = rest.split(u'\t', 1)
        return uid, name, rest, text

    def __init__(self, uid, name, text):
        super(_Text, self).__init__(uid, name)
        self.text = text


class _Association(_Annotation):

    """
    All association types in addition to ``uid`` and ``name`` have an ``args`` attribute.
    """

    @classmethod
    def _parse(cls, line):
        """uid``\\t``name[`` ``arg]+"""
        uid, name, rest = super(_Association, cls)._parse(line)
        return uid, name, tuple(rest.split(u' '))

    def __init__(self, uid, name, args):
        super(_Association, self).__init__(uid, name)
        self.args = args


class Entity(_Text):

    """
    A text type with ``start`` and ``end`` integer offset values.
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\t``name`` ``start`` ``end``\\t``text"""
        uid, name, offset, text = super(Entity, cls)._parse(line)
        start, end = offset.split(u' ', 1)
        return Entity(uid, name, start, end, text)

    def __init__(self, uid, name, start, end, text):
        super(Entity, self).__init__(uid, name, text)
        self.start = int(start)
        self.end = int(end)

    def __unicode__(self):
        return u"%s\t%s %d %d\t%s" % (self.uid, self.name, self.start, self.end, self.text)


class Normalization(_Text):

    """
    A text type with ``xref`` and (entity or association) ``target`` values.
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\t``name`` ``target`` ``ref``\\t``text"""
        uid, name, target_ref, text = super(Normalization, cls)._parse(line)
        target, xref = target_ref.split(u' ', 1)
        return Normalization(uid, name, target, xref, text)

    def __init__(self, uid, name, target, xref, text=None):
        super(Normalization, self).__init__(uid, name, text if text else xref)
        self.xref = xref
        self.target = target

    def __unicode__(self):
        return u"%s\t%s %s %s\t%s" % (self.uid, self.name, self.target, self.xref, self.text)


class Note(_Text):

    """
    A text type with an additional (annotation) ``target`` value.
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\t``name`` ``target``\\t``text"""
        return Note(*super(Note, cls)._parse(line))

    def __init__(self, uid, name, target, text):
        super(Note, self).__init__(uid, name, text)
        self.target = target

    def __unicode__(self):
        return u"%s\t%s %s\t%s" % (self.uid, self.name, self.target, self.text)


class Relation(_Association):

    """
    An association type with exactly two (entity or association) ``args``.

    The ``"Arg1:"`` and ``"Arg2:"`` prefixes do not have to be provided;
    If these argument type specifiers are missing, they are automatically prepended.
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\t``name`` ``arg1`` ``arg2"""
        uid, name, args = super(Relation, cls)._parse(line)
        arg1, arg2 = args  # ensure there's two and only two args
        return Relation(uid, name, arg1, arg2)

    def __init__(self, uid, name, arg1, arg2):
        arg1 = arg1 if u':' in arg1 else u'Arg1:%s' % arg1
        arg2 = arg2 if u':' in arg2 else u'Arg2:%s' % arg2
        super(Relation, self).__init__(uid, name, (arg1, arg2))

    def __unicode__(self):
        return u"%s\t%s %s %s" % (self.uid, self.name, self.args[0], self.args[1])


class Event(_Association):

    """
    An association type with an (entity) ``trigger``.
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\t``name:trigger[`` ``arg]+"""
        uid, named_trigger, args = super(Event, cls)._parse(line)
        name, trigger = named_trigger.split(u':', 1)
        return Event(uid, name, trigger, args)

    def __init__(self, uid, name, trigger, args):
        super(Event, self).__init__(uid, name, args)
        self.trigger = trigger

    def __unicode__(self):
        return u"%s\t%s:%s %s" % (self.uid, self.name, self.trigger, ' '.join(self.args))


class Equiv(_Association):

    """
    A plain association type.
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\t``name[`` ``arg]+"""
        return Equiv(*super(Equiv, cls)._parse(line))

    def __init__(self, uid, name, args):
        super(Equiv, self).__init__(uid, name, args)

    def __unicode__(self):
        return u"%s\t%s %s" % (self.uid, self.name, ' '.join(self.args))


class Attribute(_Annotation):

    """
    An annotation type with an (annotation) ``target`` and ``value``.
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\t``name`` ``target[`` ``modifier]"""
        uid, name, target = super(Attribute, cls)._parse(line)
        # split off the value if there is one, otherwise use ``None`` as value:
        target, modifier = target.split(u' ', 1) if u' ' in target else (target, None)
        return Attribute(uid, name, target, modifier)

    def __init__(self, uid, name, target, modifier=None):
        super(Attribute, self).__init__(uid, name)
        self.target = target
        self.value = modifier

    def __unicode__(self):
        value = u' %s' % self.value if self.value else ''
        return u"%s\t%s %s%s" % (self.uid, self.name, self.target, value)


_PARSE = {
    'T': Entity.from_string,
    'R': Relation.from_string,
    'E': Event.from_string,
    'N': Normalization.from_string,
    'M': Attribute.from_string,
    'A': Attribute.from_string,
    '#': Note.from_string,
    '*': Equiv.from_string,
}

_ERROR_MSG = u'%s on line %d in %s: "%s"'


def read(file_path, filter=None, strict=False, mode='rU', **open_args):
    """
    Yield annotation instances by parse a brat annotation file.

    Any lines that cannot be parsed are skipped (see `strict`).

    :param file_path: the file to read
    :param filter: a compiled regex pattern; any input line that matches is skipped
    :param strict: re-raise errors instead of skipping annotations that cannot be parsed
    :param mode: for :func:`open`
    :param open_args: for :func:`open`
    :return: a generator for :class:`_Annotation` instances
    :raises IOError: if there is a "technical" problem opening/reading the file
    """
    skip = (
        lambda l: False
    ) if filter is None else (
        lambda l: filter.search(l.decode('utf-8'))
    )

    with open(file_path, mode=mode, **open_args) as file:
        for lno, line in enumerate(file, 1):
            line = line.strip()

            if line and not skip(line):
                annotation = line[0]
                error_args = (lno, file_path, line.decode('utf-8'))

                try:
                    # noinspection PyCallingNonCallable
                    yield _PARSE[annotation](line)
                except ValueError:
                    L.error(_ERROR_MSG, u'format error', *error_args)
                    if strict:
                        raise
                except TypeError:
                    L.error(_ERROR_MSG, u'illegal attribute type',
                            lno, file_path, line.decode('utf-8'))
                    if strict:
                        raise
                except KeyError:
                    desc = u"unknown annotation '%s'" % annotation.decode('utf-8')
                    L.error(_ERROR_MSG, desc, *error_args)
                    if strict:
                        raise
                except Exception:
                    L.exception(_ERROR_MSG, u'unexpected error', *error_args)
                    if strict:
                        raise


def write(file_path, annotations, mode='wb', **open_args):
    """A helper to quickly write a list of annotations to a file."""
    if annotations:
        with open(file_path, mode=mode, **open_args) as file:
            for ann in annotations:
                file.write(str(ann))
                file.write(os.linesep)
