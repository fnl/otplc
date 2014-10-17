"""
OTPL files must match the following specifications:

Segments (usually, sentences) must be separated by *empty* lines (containing no character at all).
Each row must have the same number of columns (except empty-line segment separators).
Linebreaks may be encoded as either ``\\n`` (UNIX), ``\\r`` (Mac) or ``\\r\\n`` (Windows).
The first line and segment (i.e., terminated by two line-breaks) can be a column specification
(colspec; see below).
Inline comments are not allowed; please prune your data first.
The overall column structure must be:

1. Any number of **identifier** columns:
   - any number of segment IDs (string),
   - zero or one *global* **enumeration** (integer), and
   - zero or one (segment-) *local* **enumeration** (integer).
2. Exactly one **token** (string) column.
3. Any number of **annotation** (string) or **reference** (to a [possibly implicit] local or
   global enumeration).

The *colspec* Header
--------------------

The first line in an OTPL file may be the OTPL *colspec* header.
For the list of valid header names, see the :py:class:`ColumnSpecification`.
A complete such **column specification header** example might be::

    SEGMENT_ID TOKEN POS_TAG LOCAL_REF RELATION ENTITY LOCAL_REF:5 LOCAL_REF:9 EVENT

In this case, the event trigger points to the relation, not to the entity,
and the first (and only) argument points at the event itself.
(Without those redirections, the event references would be pointing at the entity.)
It is important to realize that these redirections require their manual specification and
therefore such colspecs should be included as the first line of the file, followed by an empty
line.

To make **references** and **relations** point to other columns (than the first tag column to
their left), including to other association columns, a special syntax for the column specification
(colspec) can be used:
By appending a colon and a (one-based) count of the target column, it is possible to declare that
that reference column points to that target.
This target may be either a tag or association column.
For example, ``GLOBAL_REF:10`` declares that this global reference points at column 10
(and column 10 must be either a tag or association).

OTPL Column Types
-----------------

**Identifier** columns are all optional.
**Enumeration** columns are optional and provide unique integer IDs with respect to the
whole file (global enums) or the current segment/sequence (local enums).
An optional **SEMGENT_ID** column can be used to identify a segement/sequence, but these IDs
have no corresponding element in the brat format.

The required **token** is the (byte-level) exact representation of the token as found in the text
file.

**Annotation** columns are classified into the following groups:

- **Tag** (POS_TAG, ENTITY [tag]),
- **Association** (RELATION, EVENT), and
- **Property** (NORMALIZATION, ATTRIBUTE) columns.

All columns need to follow any specific rules documented in :py:class:`.ColumnSpecification`.
In addition, the following rules must be obeyed:

* SEGMENT_ID columns can be placed in any position before the token.
* Undefined values in *annotation* columns should contain the string ``NULL``.
* Undefined pointers in *reference* columns should contain the integer ``0``.
* *Associations* by default relate to the first *tag* [column] to their left. By default, they
  require an (entity or PoS-) tag somewhere to their left, and therefore a tag can have multiple
  associations (requiring one extra column [set] per association). On the other hand, associations
  cannot relate to the token itself directly; Only tags can do that.
* *Properties* always relate to the first *tag* or *association* to their left. E.g., an
  ATTRIBUTE annotating an ATTRIBUTE is not supported; But having multiple properties per tag
  or association is (requiring an extra column per property). Therefore, it is illegal to annotate
  the token itself with a property, just as it is for associations, too.

For **relations**, the *source* tag's row always is the (first) tag (to the left) found
in the same row as the relationship itself, while the *target* tag's row is identified by the
relationship's reference column.

**Events** by default also reference the first tag to their left, but they are only linked to the
tag via their two or more reference columns.
The first column represents the event **trigger**,
while *each (optional) argument* requires one additional reference column;
Therefore, least one argument column must be defined per event.
Event arguments can be optional (by setting the reference to ``0``).
But unlike relations, they do not imply an implicit reference to the *current* tag;
I.e., the event does not implicitly refer to the tag in the same row as the event.
"""
from functools import partial
from logging import getLogger

__author__ = 'Florian Leitner <florian.leitner@gmail.com>'
L = getLogger('otplc.colspec')


class ColumnSpecificationMetaClass(type):

    """
    This metaclass populates the column NAMES (to integers) and INTEGERS (to names) dictionaries
    that can be accessed as class attributes of :py:class:`.ColumnSpecification`.
    """

    def __init__(cls, name, bases, namespace):
        super(ColumnSpecificationMetaClass, cls).__init__(name, bases, namespace)

    @property
    def NAMES(cls):
        """A column name-to-integer dictionary."""
        if not hasattr(cls, '_NAMES'):
            cls._NAMES = ColumnSpecificationMetaClass._getMapping(cls)

        return cls._NAMES

    @property
    def INTEGERS(cls):
        """A column integer-to-name dictionary."""
        if not hasattr(cls, '_INTEGERS'):
            cls._INTEGERS = ColumnSpecificationMetaClass._getMapping(cls, reverse=True)

        return cls._INTEGERS

    @staticmethod
    def _getMapping(cls, reverse=False):
        makeKeyValuePair = (lambda k, v: (v, k)) if reverse else (lambda k, v: (k, v))
        return dict([makeKeyValuePair(name, getattr(cls, name)) for name in vars(cls)
                     if name.isupper() and isinstance(getattr(cls, name), int)])


class ColumnSpecification(object):

    """
    The specification of column types and facilities to instantiate a spec
    from a *colspec header* (in the OTPL file) using :py:meth:`.from_string`
    or a list of integers using :py:meth:`.from_integers` .
    """

    __metaclass__ = ColumnSpecificationMetaClass

    _ANNOTATION = 99
    "*Internal*: A (yet) unspecific *annotation* (for internal use only)."

    _UNKNOWN = 0
    "*Internal*: A (yet) undetermined column type (for internal use only)."

    LOCAL_ENUM = 4
    "*Enumeration*: A segment-locally unique integer ID (except 0)."

    GLOBAL_ENUM = 3
    "*Enumeration*: A globally unique integer ID (except 0)."

    SEGMENT_ID = 2
    "SEGMENT_ID: A segment ID (a string that is equal on all rows of a segment)."

    TOKEN = 1
    "*Token*: The word itself (a string); **required**."

    POS_TAG = 5
    "*Annotation/Tag*: The PoS tag (a string); must be placed *immediately* after the token."

    ENTITY = 6
    "*Annotation/Tag*: An entity (all values must start with 'B-', 'E-', or 'I-', or be == 'O')."

    NORMALIZATION = 7
    "*Annotation/Property*: A normalization (string with format 'NS:ID')."

    RELATION = 8
    "*Annotation/Association*: A binary 'relation' (string) with a preceding reference column."

    EVENT = 9
    "Annotation/Association: An 'event' (string) with two or more preceding reference columns."

    ATTRIBUTE = 10
    "*Annotation/Property*: Attributes (string) following any annotation."

    LOCAL_REF = 11
    "*Reference*: A pointer to a local enumeration ID (integer) or 0."

    GLOBAL_REF = 12
    "*Reference*: A pointer to a global enumeration ID (integer) or 0."

    _ENTITY_COLUMNS = frozenset((POS_TAG, ENTITY))
    "All entity columns."

    _ENUM_COLUMNS = frozenset((LOCAL_ENUM, GLOBAL_ENUM))
    "All enumeration columns."

    _REFERENCE_COLUMNS = frozenset((LOCAL_ENUM, GLOBAL_ENUM))
    "All reference columns."

    _ANNOTATION_COLUMNS = frozenset((POS_TAG, ENTITY, RELATION, EVENT, NORMALIZATION, ATTRIBUTE))
    "All annotation columns."

    _SKIPPED_COLUMNS = frozenset((GLOBAL_REF, LOCAL_REF, ATTRIBUTE, NORMALIZATION, EVENT, RELATION))
    "All columns that may be (skipped) between an association and the tag it annotates."

    _PROPERTY_TARGET_COLUMNS = frozenset((POS_TAG, ENTITY, RELATION, EVENT))
    "All columns that a property and re-targeted references/relations may annotate."

    @classmethod
    def from_string(cls, header):
        """
        Create a ColumnSpecification instance from a column specification header.

        :param header: a colspec header string
        :return: a :py:class:`.ColumnSpecification` instance
        :raises ValueError: if the colspec header is invalid
        """
        colspec = cls.parse_colspec(header)
        return cls(colspec, header.split())

    @classmethod
    def from_integers(cls, colspec):
        """
        Create a ColumnSpecification instance from a list of integers.

        :param colspec: an integer list of column types
        :return: a :py:class:`.ColumnSpecification` instance
        :raises ValueError: if the colspec list is invalid
        """
        header = cls.to_string(colspec)
        return cls(colspec, header.split())

    @classmethod
    def to_string(cls, colspec):
        """Convert a colspec integer list to a colspec header string."""
        try:
            # noinspection PyUnresolvedReferences
            return ' '.join(cls.INTEGERS.get(c, u'_TYPE_') for c in colspec)
        except TypeError:
            raise TypeError(u'colspec not a list')

    @classmethod
    def parse_colspec(cls, header):
        """
        Convert a column specification header into a list of integers.

        For example::

            >>> ColumnSpecification.parse_colspec(
            ...     u'SEGMENT_ID LOCAL_ENUM TOKEN POS_TAG LOCAL_REF RELATION'
            ... )
            [2, 4, 1, 5, 11, 8]

        :raises ValueError: if a column type name is not known
        """
        try:
            names = header.split()
        except AttributeError:
            raise TypeError(u'header not a string')

        colspec = [cls._UNKNOWN] * len(names)
        known_names = cls.NAMES

        for idx, name in enumerate(names):
            cls.__getValue(colspec, idx, name, known_names)

        return colspec

    @classmethod
    def __getValue(cls, colspec, idx, name, known_names):
        if name.startswith('_'):
            L.warning(u'using an internal colspec type; probably a Bad Idea')
        if u':' in name:
            name = name[:name.index(u':')]
        if name in known_names:
            colspec[idx] = getattr(cls, name)
        else:
            raise ValueError(u'illegal "%s" in column %s' % (name, idx + 1))

    def __init__(self, colspec, headers):
        assert len(colspec) > 1, u'single-column colspec'
        assert len(colspec) == len(headers)
        self._width = len(colspec)
        self._token = None
        self._global_enum = None
        self._local_enum = None
        self._pos_tag = None
        self._segment_ids = set()
        self._entities = set()
        self._events = dict()
        self._relations = dict()
        self._global_refs = dict()
        self._local_refs = dict()
        self._normalizations = dict()
        self._attributes = dict()
        self._ref_targets = dict()

        setUp = {
            ColumnSpecification.TOKEN: self.set_token,
            ColumnSpecification.GLOBAL_ENUM: self.set_global_enum,
            ColumnSpecification.LOCAL_ENUM: self.set_local_enum,
            ColumnSpecification.POS_TAG: self.set_pos_tag,
            ColumnSpecification.SEGMENT_ID: self._segment_ids.add,
            ColumnSpecification.ENTITY: self._entities.add,
            ColumnSpecification.EVENT:
                lambda col: self._events.setdefault(col, None),
            ColumnSpecification.RELATION:
                partial(self._addRelation, headers, self._relations, colspec),
            ColumnSpecification.GLOBAL_REF:
                partial(self._addReference, headers, self._global_refs, colspec),
            ColumnSpecification.LOCAL_REF:
                partial(self._addReference, headers, self._local_refs, colspec),
            ColumnSpecification.NORMALIZATION:
                partial(self._addProperty, self._normalizations, colspec),
            ColumnSpecification.ATTRIBUTE:
                partial(self._addProperty, self._attributes, colspec),
            ColumnSpecification._UNKNOWN:
                lambda col: L.info(u'ignoring _UNKNOWN column %s', col + 1),
        }

        for idx, coltype in enumerate(colspec):
            try:
                # noinspection PyCallingNonCallable
                setUp[coltype](idx)
            except KeyError:
                raise ValueError(
                    u'unknown %s (%d) column %d' % (headers[idx], coltype, idx + 1)
                )

        self.__initEvents(colspec)

    def __initEvents(self, colspec):
        for col in self._events:
            ref_cols = tuple(reversed(tuple(self.__getReferencesBefore(colspec, col))))
            self._events[col] = (ref_cols[0], ref_cols[1:])

            if len(self._events[col][1]) < 1:
                raise ValueError(u'EVENT column %d has less than two references' % (col + 1))

    def __eq__(self, other):
        if not isinstance(other, ColumnSpecification):
            return False

        for attr in ['_width', '_token', '_global_enum', '_local_enum', '_pos_tag',
                     '_segment_ids', '_entities', '_events', '_relations', '_global_refs',
                     '_local_refs', '_normalizations', '_attributes', '_ref_targets', ]:
            if getattr(self, attr) != getattr(other, attr):
                return False

        return True

    def __str__(self):
        """ Return the colspec header string for this instance. """
        col = 0
        names = []
        coltype = self.get_type(col)

        while coltype is not None and col < self._width:
            # noinspection PyUnresolvedReferences
            names.append(ColumnSpecification.INTEGERS[coltype])
            col += 1
            coltype = self.get_type(col)

        return u' '.join(names)

    def get_type(self, col):
        """ Return the column type integer for this column or ``None``. """
        if self._token == col:
            return self.TOKEN
        elif self._global_enum == col:
            return self.GLOBAL_ENUM
        elif self._local_enum == col:
            return self.LOCAL_ENUM
        elif self._pos_tag == col:
            return self.POS_TAG
        elif col in self._segment_ids:
            return self.SEGMENT_ID
        elif col in self._entities:
            return self.ENTITY
        elif col in self._events:
            return self.EVENT
        elif col in self._relations:
            return self.RELATION
        elif col in self._normalizations:
            return self.NORMALIZATION
        elif col in self._attributes:
            return self.ATTRIBUTE
        elif col in self._global_refs:
            return self.GLOBAL_REF
        elif col in self._local_refs:
            return self.LOCAL_REF
        else:
            return None

    def __getReferencesBefore(self, colspec, col):
        for idx in xrange(col - 1, 0, -1):
            if colspec[idx] in (ColumnSpecification.LOCAL_REF, ColumnSpecification.GLOBAL_REF):
                yield idx
            else:
                break

    @property
    def global_enum(self):
        return self._global_enum

    @property
    def local_enum(self):
        return self._local_enum

    @property
    def token(self):
        return self._token

    @property
    def pos_tag(self):
        return self._pos_tag

    def get_attribute_target(self, att):
        return self._attributes[att]

    def get_event_targets(self, event):
        """ Return a 2-tuple of (trigger column, reference columns tuple). """
        return self._events[event]

    def get_normalization_target(self, norm):
        return self._normalizations[norm]

    def get_reference_target(self, ref):
        if ref in self._global_refs:
            return self._global_refs[ref]
        else:
            return self._local_refs[ref]

    def get_relation_target(self, rel):
        return self._relations[rel]

    def has_global_refs(self):
        return 0 != len(self._global_refs)

    def is_entity(self, col):
        return col in self._entities

    def is_pos_tag(self, col):
        return col == self.pos_tag

    def is_event(self, col):
        return col in self._events

    def is_global_ref(self, col):
        return col in self._global_refs

    # def isLocalRef(self, col):
    #     return col in self._local_refs

    def is_relation(self, col):
        return col in self._relations

    def iter_segment_ids(self):
        return iter(self._segment_ids)

    def iter_entities(self):
        return iter(self._entities)

    def iter_relations(self):
        return self._relations.keys()

    def iter_events(self):
        return self._events.keys()

    def iter_normalizations(self):
        return self._normalizations.keys()

    def iter_attributes(self):
        return self._attributes.keys()

    def get_property_target_column_type(self, col):
        if self.is_entity(col):
            return ColumnSpecification.ENTITY
        elif self.is_pos_tag(col):
            return ColumnSpecification.POS_TAG
        elif self.is_relation(col):
            return ColumnSpecification.RELATION
        elif self.is_event(col):
            return ColumnSpecification.EVENT
        else:
            raise ValueError(u'column %d not a valid property target' % (col + 1))

    def set_global_enum(self, val):
        self._setColumn('global_enum', val)

    def set_local_enum(self, val):
        self._setColumn('local_enum', val)

    def set_token(self, val):
        self._setColumn('token', val)

    def set_pos_tag(self, val):
        self._setColumn('pos_tag', val)

    def _setColumn(self, name, val):
        attr = '_%s' % name
        old = getattr(self, attr)

        if old is None:
            setattr(self, attr, int(val))
        else:
            raise ValueError(u'%s already assigned to column %d' % (name.upper(), old + 1))

    def _addRelation(self, headers, collection, colspec, col):
        if not colspec[col - 1] in (ColumnSpecification.LOCAL_REF, ColumnSpecification.GLOBAL_REF):
            raise ValueError(u'RELATION column %d has no reference' % (col + 1))

        self.__ensureUndefined(collection, colspec, col)
        self.__setTargetFromHeader(headers, collection, colspec, col)

    def _addReference(self, headers, collection, colspec, col):
        self.__ensureUndefined(collection, colspec, col)
        self.__setTargetFromHeader(headers, collection, colspec, col)

    def _addProperty(self, collection, colspec, col):
        self.__ensureUndefined(collection, colspec, col)
        self.__setTarget(collection, colspec, col, ColumnSpecification._PROPERTY_TARGET_COLUMNS)

    def __ensureUndefined(self, collection, colspec, col):
        if col in collection:
            # noinspection PyUnresolvedReferences
            raise ValueError(u'%s column %d already mapped' %
                             (ColumnSpecification.INTEGERS[colspec[col]], col + 1))

    def __setTargetFromHeader(self, headers, collection, colspec, col):
        header = headers[col]

        if u':' in header:
            target = int(header[header.index(u':') + 1:]) - 1

            # named references can point to any property, not just entities
            if colspec[target] in ColumnSpecification._PROPERTY_TARGET_COLUMNS:
                collection[col] = target
            else:
                # noinspection PyUnresolvedReferences
                raise ValueError(u'target (%s) of %s column %d invalid' %
                                 (ColumnSpecification.INTEGERS[colspec[target]], header, col + 1))
        else:
            self.__setTarget(collection, colspec, col, ColumnSpecification._ENTITY_COLUMNS)

    def __setTarget(self, collection, colspec, col, targets):
        # noinspection PyUnresolvedReferences
        source = ColumnSpecification.INTEGERS[colspec[col]]

        for target in range(col - 1, 0, -1):
            if colspec[target] in targets:
                collection[col] = target
                break
            elif colspec[target] not in ColumnSpecification._SKIPPED_COLUMNS:
                raise ValueError(u'%s column %d has no target' %
                                 (source, col + 1))
        else:
            raise ValueError(u'%s column %s with no target' % (source, col + 1))
