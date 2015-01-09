"""
Functionality for reading and working with OTPL files.
"""
from collections import defaultdict
from logging import getLogger
from re import compile

from otplc.colspec import ColumnSpecification as C


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'
L = getLogger('otplc.reader')

# ====================== #
# OTPL FILE READING CODE #
# ====================== #

TAB = compile('\t')
SPACES = compile(r'\s+')
NORM = compile(r'^(?:\S+:\S+|NULL)$')
DEFAULT_ENCODING = 'utf-8'


class DataFormatError(Exception):
    """An exception that is raised when illegal content is parsed from the OTPL file."""
    pass


def configure_reader(file_path, config):
    """
    Create a new :class:`OtplReader`, optionally with a filter regex and a pre-defined column
    separator regex.

    :param file_path: to the OTPL file
    :param config: a :class:`otplc.settings.Configuation` object
    :return: a :class:`OtplReader` instance
    """
    reader = OtplReader(file_path, encoding=config.encoding)

    if config.filter is not None:
        reader.filter = config.filter

    if config.separator is not None:
        reader.separator = config.separator
    elif not reader.detect_separator():
        L.error(u'for "%s" failed: not field separator detected', file_path)
        reader = None

    return reader


class OtplReader(object):

    """
    While possible to use directly, a reader instance should be created from its builder function,
    :func:`configure_reader`.

    Iterating over a reader instance will yield its *segments*.
    Segments simply are lists (token rows) of lists (the columns), with each row having an equal
    number of columns.
    If not using the builder function, ensure that the field/column :attr:`.separator` has been
    properly defined before iterating.
    """

    def __init__(self, file_path, **open_args):
        """
        Create a new reader instance.

        :param file_path: the OTPL file location
        :param open_args: `open` keyword arguments other than the defaults
        """
        self._file_path = file_path
        self._open_args = open_args
        self._separator = None
        self._filter = compile(r'^$')  # skip lines matching "self._filter.search(line)"

    def __iter__(self):
        """
        Yield OTLP segments as lists of rows with equal number of columns.

        Requires that the separator regex property has been defined.

        :raises DataFormatError: when the column numbers vary
        :raises IOError: when the I/O operation fails
        :raises UnicodeDecodeError: when the input isn't in UTF-8 encoding
        :raises AttributeError: if the separator property is undefined
        """
        column_count = 0
        segment = []

        for lno, line in enumerate(self._open(), 1):
            if line:
                column_count = self._parseLine(line, lno, segment, column_count)
            elif segment:
                yield segment
                segment = []

        if segment:
            yield segment

    def detect_separator(self):
        """
        Try to guess the separator - either /\t/ or /\s+/ - from the first ten non-empty lines.

        :return: ``True`` if a decision could be made and the separator has been set
        """
        separator = None
        spaces_fields, tab_fields = self._countFields()

        if len(spaces_fields) == 1 or len(tab_fields) == 1:
            separator = _choose_separator(spaces_fields, tab_fields)
        elif len(spaces_fields) == 0 and len(tab_fields) == 0:
            L.warning(u'either "%s" is empty or all lines were filtered' % self._file_path)

        if separator is None:
            L.warning(u'failed because "%s" has no stable column-count' % self._file_path)
        else:
            self.separator = separator.pattern

        return separator is not None

    def _countFields(self):
        spaces_fields = defaultdict(int)
        tab_fields = defaultdict(int)
        count = 0

        try:
            for line in self._open():
                if line and not self._filter.match(line):
                    spaces_fields[len(SPACES.split(line))] += 1
                    tab_fields[len(TAB.split(line))] += 1
                    count += 1

                    if count > 9 or (len(spaces_fields) > 1 and len(tab_fields) > 1):
                        break
        except IOError as e:
            L.error(str(e))

        return spaces_fields, tab_fields

    def _extractFields(self, line, lno, column_count):
        fields = self._separator.split(line)

        if column_count != 0 and column_count != len(fields):
            raise DataFormatError(
                'line %d has %d columns, but expected %d' % (lno, len(fields), column_count)
            )

        return fields

    def _open(self):
        for raw_line in open(self._file_path, **self._open_args):
            yield raw_line.rstrip('\r\n')

    def _parseLine(self, line, lno, segment, column_count):
        if not self._filter.search(line):
            segment.append(self._extractFields(line, lno, column_count))
            column_count = len(segment[0]) if column_count == 0 else column_count

        return column_count

    @property
    def path(self):
        """The file path of this reader."""
        return self._file_path

    @property
    def filter(self):
        """A regex that defines which lines are ignored."""
        return self._filter.pattern

    @filter.setter
    def filter(self, regex):
        """:type regex: str """
        L.info(u'= /%s/', regex)
        self._filter = compile(regex)

    @property
    def separator(self):
        """A regex that defines how lines are split into fields."""
        return self._separator.pattern

    @separator.setter
    def separator(self, regex):
        """:type regex: str """
        L.info(u'= /%s/', regex)
        self._separator = compile(regex)


def _choose_separator(spaces_fields, tab_fields):
    """Use the most stable, maximum field number to choose the more likely separator."""
    # *_fields: {num_fields: num_observed}
    moreThanOne = lambda f: max(f.keys()) > 1

    if len(spaces_fields) == 1 and len(tab_fields) != 1:
        return SPACES if moreThanOne(spaces_fields) else None
    elif len(tab_fields) == 1 and len(spaces_fields) != 1:
        return TAB if moreThanOne(tab_fields) else None
    elif len(tab_fields) == 1 and len(spaces_fields) == 1:
        tab = sorted([(v, k) for k, v in tab_fields.items()])[0][1]
        spaces = sorted([(v, k) for k, v in spaces_fields.items()])[0][1]

        if tab != 1 or spaces != 1:
            return TAB if tab >= spaces else SPACES
        else:
            return None
    else:
        return None


# ========================= #
# COLUMN TYPE GUESSING CODE #
# ========================= #

def guess_colspec(otpl_reader):
    """
    Note that for guessing to work, the optionally present global enumeration column must be
    placed *before* the (also optional) local enumeration column.

    If the input file has a colspec header, that header is used instead of any guessing.

    :param otpl_reader: a reader instance
    :type otpl_reader: OtplReader
    :raises AttributeError: if the reader has an undefined separator property
    :returns: a :class:`ColumnSpecification` or ``None`` if the guessing fails
    """
    try:
        guess = _make_guess(otpl_reader)
    except (IOError, UnicodeDecodeError, DataFormatError) as e:
        L.warning(str(e))
        guess = []

    if isinstance(guess, C):
        L.info(u'from header: %s', str(guess))
        return guess
    elif len(guess) < 2:
        L.warning(u'failed for "%s"', otpl_reader.path)
        L.debug(u'discarded guess was: %s', C.to_string(guess))
        return None
    else:
        L.debug(u'as: %s', C.to_string(guess))
        return C.from_integers(guess)


def _make_guess(segments):
    guess = None
    last_round = False

    for idx, segment in enumerate(segments):
        if not guess:
            # noinspection PyUnresolvedReferences
            if len(segment) == 1 and all(n.split(u':')[0] in C.NAMES for n in segment[0]):
                return C.from_string(' '.join(segment[0]))

            guess = Guess(segment)
        else:
            guess.update(segment)

        if idx > 4 or last_round:
            break
        elif guess.complete():
            last_round = True

    return guess.guess


class Guess(object):

    def __init__(self, segment):
        self.columns = len(segment[0])
        self.guess = [C._UNKNOWN] * self.columns
        self._segment = segment
        self._analyze()
        self._assignAnnotationTypes()

    def __len__(self):
        return self.columns

    def complete(self):
        return all(g != C._UNKNOWN for g in self.guess)

    def update(self, segment):
        self._segment = segment
        self._analyze()
        self._assignAnnotationTypes()

    def _analyze(self):
        self.__token_seen = False

        for col in range(self.columns):
            self._analyzeColumn(col)

    def _analyzeColumn(self, column):
        if self.guess[column] == C._UNKNOWN:
            if not self.__token_seen:
                self._guessIdOrToken(column)
            else:
                self._guessAnnotationOrReference(column)
        elif self.guess[column] in (C.LOCAL_REF, C.GLOBAL_REF):
            # re-test refs on every round, to be as sure as possible they work
            self._ensureReference(column)

    def _guessIdOrToken(self, column):
        val = self._segment[0][column]

        if all(row[column] == val for row in self._segment) and len(self._segment) > 1:
            self.guess[column] = C.SEGMENT_ID
        elif all(row[column].isdigit() for row in self._segment):
            if column == 0:
                self.guess[column] = C.LOCAL_ENUM
            else:
                self._ensureEnumColumns(column)
        else:
            # was neither a segment ID or a numeric column, so it must be the token column
            self._guessUnique(column, C.TOKEN)
            self.__token_seen = True

    def _ensureEnumColumns(self, this_column):
        """Ensure there are no more than two (global, then local) enumerations."""
        global_set = False
        this_coltype = C.LOCAL_ENUM

        for idx, coltype in self._iterColumns(C._ENUM_COLUMNS):
            if this_column == idx:
                pass
            elif not global_set:
                if idx < this_column:
                    self.guess[idx] = C.GLOBAL_ENUM
                elif idx > this_column:
                    self.guess[idx] = C.LOCAL_ENUM
                    this_coltype = C.GLOBAL_ENUM

                global_set = True
            else:
                L.warning(u'at column %s: already detected two enumeration columns',
                          this_column + 1)
                self.guess[idx] = C._UNKNOWN

        self.guess[this_column] = this_coltype

    def _iterColumns(self, choices):
        """Yield (column, coltype) pairs for a collection of coltype `choices`."""
        return filter(lambda g: g[1] in choices, enumerate(self.guess))

    def _guessUnique(self, column, coltype):
        """ Ensure this col is the only column of its kind. """
        for idx in range(column):
            if self.guess[idx] == coltype:
                self.guess[idx] = C._UNKNOWN

        self.guess[column] = coltype

    def _guessAnnotationOrReference(self, column):
        """Decide if a tag or reference column."""
        if all(row[column].isdigit() for row in self._segment):
            self._guessLocalOrGlobalReference(column)
        else:
            # was not a numeric column, so it must be an annotation
            self.guess[column] = C._ANNOTATION  # NB: annotations will be resolved separately

    def _ensureReference(self, column):
        """Ensure the guessed reference column "still works"."""
        if all(row[column].isdigit() for row in self._segment):
            self._guessLocalOrGlobalReference(column)
        else:
            self.guess[column] = C._UNKNOWN

    def _guessLocalOrGlobalReference(self, column):
        """For a known integers-only column, detect its reference scope."""
        references = {int(row[column]) for row in self._segment if row[column] != u'0'}
        enums = list(self._iterColumns((C.LOCAL_ENUM,)))

        if max(references) > len(self._segment):
            self.guess[column] = C.GLOBAL_REF
        else:
            for idx, unused in enums:
                try:
                    if references.issubset(set([int(row[idx]) for row in self._segment])):
                        self.guess[column] = C.LOCAL_REF
                        return
                except ValueError:
                    self.guess[idx] = C._UNKNOWN
            else:
                L.info(u'fallback guess to local reference scope for column %s', column)
                self.guess[column] = C.LOCAL_REF

    def _assignAnnotationTypes(self):
        for col, guess in enumerate(self.guess):
            if guess == C._ANNOTATION:
                if self.guess[col - 1] not in (C._UNKNOWN, C.GLOBAL_REF, C.LOCAL_REF):
                    self._guessTagOrProperty(col)
            elif guess in (C.LOCAL_REF, C.GLOBAL_REF):
                self._guessEventOrRelation(col)

    def _hasATagToTheLeft(self, column):
        for idx in range(column - 1, 0, -1):
            if self.guess[idx] in (C.POS_TAG, C.ENTITY):
                return True

        return False

    def _guessTagOrProperty(self, column):
        vals = [row[column] for row in self._segment]
        tagged = self._hasATagToTheLeft(column)
        matchesPrefix = lambda val: any(val.startswith(pre) for pre in (u'B-', u'E-', u'I-'))

        if tagged and all(NORM.match(v) is not None for v in vals if v != u'NULL'):
            self.guess[column] = C.NORMALIZATION
        elif all(matchesPrefix(v) or v == u'O' for v in vals):
            self.guess[column] = C.ENTITY
        elif tagged:
            self.guess[column] = C.ATTRIBUTE
        elif self.guess[column - 1] == C.TOKEN:
            self.guess[column] = C.POS_TAG
        else:
            L.debug(u'no guess (yet?) for column %s with values %s', column + 1, vals)
            self.guess[column] = C._UNKNOWN

    def _guessEventOrRelation(self, column):
        for next in range(column + 1, self.columns):
            coltype = self.guess[next]

            if coltype in (C.LOCAL_REF, C.GLOBAL_REF):
                continue
            elif coltype in (C.RELATION, C.EVENT, C._UNKNOWN):
                # already done or undetectable
                break
            elif coltype == C._ANNOTATION:
                self.guess[next] = _disambiguate_event_or_relation(next, column)
                break
            else:
                # noinspection PyUnresolvedReferences
                name = C.VALUES[coltype]
                raise DataFormatError(
                    'found %s column %d, expected an association' % (name, column + 1)
                )


def _disambiguate_event_or_relation(col, first_ref_col):
    return C.EVENT if col - first_ref_col > 1 else C.RELATION
