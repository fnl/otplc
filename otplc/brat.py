"""
A clear and Unicode-aware implementation of the brat annotation type system.
All annotation types provide a class-method ``from_string`` to parse a Unicode string and
return the corresponding type object.
And all types can be transformed to Unicode strings (:func:`str`) or be serialized to bytes
(:func:`bytes`) in UTF-8 encoding.
"""
from logging import getLogger
import os


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'
L = getLogger('otplc.brat')


class _Annotation:

    """
    All annotation types are guaranteed to provide a ``uid`` and ``name`` attribute.
    """

    @classmethod
    def _parse(cls, line):
        """
        uid``\\t``name`` ``...

        Uniform annotation de-serialization.
        """
        uid, rest = line.split('\t', 1)
        name, rest = rest.split(' ', 1)
        return uid, name, rest

    def __init__(self, uid, name):
        self.uid = uid
        self.name = name

    def __bytes__(self):
        """Uniform UTF-8 annotation serialization."""
        return str(self).encode('utf-8')

    def __eq__(self, other):
        return vars(self) == vars(other)

    def __ne__(self, other):
        return not self.__eq__(other)


class _Text(_Annotation):

    """
    All text types in addition to ``uid`` and ``name`` have a ``text`` attribute.
    """

    @classmethod
    def _parse(cls, line):
        """uid``\\t``name`` ``...``\\t``text"""
        uid, name, rest = super(_Text, cls)._parse(line)
        rest, text = rest.split('\t', 1)
        return uid, name, rest, text

    def __init__(self, uid, name, text):
        super(_Text, self).__init__(uid, name)
        self.text = text


class _Association(_Annotation):

    """
    All association types in addition to ``uid`` and ``name`` have an ``args`` attribute.

    These arguments are dictionaries holding argument type to target ID mappings.
    """

    @classmethod
    def _parse(cls, line):
        """uid``\\t``name[`` ``arg]+"""
        uid, name, rest = super(_Association, cls)._parse(line)
        return uid, name, tuple(rest.split(' '))

    def __init__(self, uid, name, **args):
        super(_Association, self).__init__(uid, name)
        self.args = dict(args['args']) if len(args) == 1 and 'args' in args else args

    @property
    def _args_str(self):
        # sorted arg:target string (to ensure equal reproducibility)
        return ' '.join('%s:%s' % arg_target for arg_target in sorted(self.args.items()))


class Entity(_Text):

    """
    A text type with ``start`` and ``end`` integer offset values.
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\t``name`` ``start`` ``end``\\t``text"""
        uid, name, offset, text = super(Entity, cls)._parse(line)
        start, end = offset.split(' ', 1)
        return Entity(uid, name, start, end, text)

    def __init__(self, uid, name, start, end, text):
        super(Entity, self).__init__(uid, name, text)
        self.start = int(start)
        self.end = int(end)
        assert len(text) == self.end - self.start, 'text and offsets mismatch'

    def __str__(self):
        return "%s\t%s %d %d\t%s" % (self.uid, self.name, self.start, self.end, self.text)

    def __eq__(self, other):
        return isinstance(other, Entity) and super(Entity, self).__eq__(other)


class Normalization(_Text):

    """
    A text type with ``xref`` and (entity or association) ``target`` values.
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\tReference ``target`` ``db``:``xref``\\t``text"""
        uid, name, target_ref, text = super(Normalization, cls)._parse(line)

        if name != 'Reference':
            raise ValueError('illegal normalization name="%s"' % name)

        target, xref = target_ref.split(' ', 1)
        db, xref = xref.split(':', 1)
        return Normalization(uid, target, db, xref, text)

    def __init__(self, uid, target, db, xref, text=None):
        super(Normalization, self).__init__(uid, 'Reference', text if text else xref)
        self.db = db
        self.xref = xref
        self.target = target

    def __str__(self):
        return "%s\tReference %s %s:%s\t%s" % (self.uid, self.target,
                                               self.db, self.xref, self.text)

    def __eq__(self, other):
        return isinstance(other, Normalization) and super(Normalization, self).__eq__(other)


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

    def __str__(self):
        return "%s\t%s %s\t%s" % (self.uid, self.name, self.target, self.text)

    def __eq__(self, other):
        return isinstance(other, Note) and super(Note, self).__eq__(other)


class Relation(_Association):

    """
    An association type with exactly two (entity or association) ``args``.

    The ``"Arg1:"`` and ``"Arg2:"`` prefixes do not have to be part of `target1` and `target2`;
    The argument type specifiers are automatically prepended.
    If any other prefixes are used, they are removed.
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\t``name`` Arg1:``target1`` Arg2:``target2"""
        uid, name, args = super(Relation, cls)._parse(line)
        target1, target2 = args  # ensure there's two and only two args
        return Relation(uid, name, target1, target2)

    def __init__(self, uid, name, target1, target2):
        target1 = target1[target1.find(':') + 1:]
        target2 = target2[target2.find(':') + 1:]
        super(Relation, self).__init__(uid, name, Arg1=target1, Arg2=target2)

    def __str__(self):
        return "%s\t%s %s" % (self.uid, self.name, self._args_str)

    def __eq__(self, other):
        return isinstance(other, Relation) and super(Relation, self).__eq__(other)


class Event(_Association):

    """
    An association type with an (entity) ``trigger``.

    Arguments should be argument type, target pairs, like {Argument='T2')
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\t``name:trigger[`` ``arg``:``target]+"""
        uid, named_trigger, args = super(Event, cls)._parse(line)
        name, trigger = named_trigger.split(':', 1)
        args = dict(a_t.split(':') for a_t in args)
        return Event(uid, name, trigger, **args)

    def __init__(self, uid, name, trigger, **args):
        super(Event, self).__init__(uid, name, **args)
        self.trigger = trigger

    def __str__(self):
        return "%s\t%s:%s %s" % (self.uid, self.name, self.trigger, self._args_str)

    def __eq__(self, other):
        return isinstance(other, Event) and super(Event, self).__eq__(other)


class Equiv(_Annotation):

    """
    A plain association type.
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\t``name[`` ``target]+"""
        uid, name, rest = super(Equiv, cls)._parse(line)
        return Equiv(uid, name, rest.split())

    def __init__(self, uid, name, targets):
        super(Equiv, self).__init__(uid, name)
        self.targets = tuple(targets)

    def __str__(self):
        return "%s\t%s %s" % (self.uid, self.name, ' '.join(self.targets))

    def __eq__(self, other):
        return isinstance(other, Equiv) and super(Equiv, self).__eq__(other)


class Attribute(_Annotation):

    """
    An annotation type with an (annotation) ``target`` and ``value``.
    """

    @classmethod
    def from_string(cls, line):
        """uid``\\t``name`` ``target[`` ``modifier]"""
        uid, name, target = super(Attribute, cls)._parse(line)
        # split off the value if there is one, otherwise use ``None`` as value:
        target, modifier = target.split(' ', 1) if ' ' in target else (target, None)
        return Attribute(uid, name, target, modifier)

    def __init__(self, uid, name, target, modifier=None):
        super(Attribute, self).__init__(uid, name)
        self.target = target
        self.modifier = modifier

    def __str__(self):
        value = ' %s' % self.modifier if self.modifier else ''
        return "%s\t%s %s%s" % (self.uid, self.name, self.target, value)

    def __eq__(self, other):
        return isinstance(other, Attribute) and super(Attribute, self).__eq__(other)


_PARSE = {
    'T': Entity.from_string,
    'N': Normalization.from_string,
    '#': Note.from_string,
    'R': Relation.from_string,
    'E': Event.from_string,
    '*': Equiv.from_string,
    'A': Attribute.from_string,
    'M': Attribute.from_string,  # legacy support (is this still needed?)
}

_ERROR_MSG = '%s on line %d in %s: "%s"'

_ERROR_REASON = {
    ValueError: 'format error',
    TypeError: 'illegal attribute type',
    KeyError: 'unknown annotation',
}


def read(file_path, filter=None, strict=False, encoding='utf-8', **open_args):
    """
    Yield annotation instances by parse a brat annotation file.

    Any lines that cannot be parsed are skipped (see `strict`).

    :param file_path: the file to read
    :param filter: a compiled regex pattern; any input line that matches is skipped
    :param strict: re-raise errors instead of skipping annotations that cannot be parsed
    :param encoding: for :func:`open`
    :param open_args: for :func:`open`
    :return: a generator for :class:`_Annotation` instances
    :raises IOError: if there is a "technical" problem opening/reading the file
    """
    skip = _makeFilterFunction(filter)

    with open(file_path, encoding=encoding, **open_args) as file:
        for lno, raw in enumerate(file, 1):
            line = raw.strip()

            if line and not skip(line):
                annotation_type = line[0]

                try:
                    # noinspection PyCallingNonCallable
                    yield _PARSE[annotation_type](line)
                except (ValueError, TypeError, KeyError, Exception) as error:
                    _handleError(error, file_path, line, lno, strict)


def _handleError(error, file_path, line, lno, strict):
    error_args = (lno, file_path, line)

    try:
        L.error(_ERROR_MSG, _ERROR_REASON[type(error)], *error_args)
    except KeyError:
        L.error(_ERROR_MSG, str(error), *error_args)

    if strict:
        raise error


def _makeFilterFunction(filter):
    return (
        lambda line: False
    ) if filter is None else (
        lambda line: filter.search(line)
    )


def write(file_path, annotations, mode='wb', **open_args):
    """A helper to quickly write a list of annotations to a file."""
    if annotations:
        with open(file_path, mode=mode, **open_args) as file:
            for ann in annotations:
                file.write(str(ann))
                file.write(os.linesep)
