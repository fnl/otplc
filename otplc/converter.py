"""
Transform a OTPL file to and from brat annotations.
"""
from itertools import count
from logging import getLogger
from collections import defaultdict
import os
from re import compile
from os.path import exists, splitext, dirname, join
from otplc import brat
from otplc.colspec import ColumnSpecification
from otplc.reader import guess_colspec, configure_reader, DataFormatError
from otplc.settings import Configuration


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'
L = getLogger('otplc.converter')
A_VALID_NAME = compile(r'^[\w-]+$')


class OtplBratConverter:

    """
    A class that, given a column specification, can convert a OTPL standoff annotation file
    and write a brat standoff annotation file given the (underlying) text file.

    To use this class, you first initialize an instance and pass it a OTPL column specification
    (colspec) using :meth:`.set_colspec`.
    That colspec is then used for the conversion with :meth:`.convert`.
    For each text file, :meth:`convert` directly reads the OTPL file and writes the brat
    annotation file.
    After all files have been converted, :meth:`.write_config_file` can be used to write
    the brat annotation configuration setup using the detected names ("brat annotation types").
    """

    NORMALIZATION_LINE = u'# %s\t<URL>:http://example.com/, <URLBASE>:http://example.com/%%s\n'
    "The config file line used for normalization database names (should be moved to tools.conf)"

    def __init__(self):
        self._colspec = None  # the column specification instance
        self._annotation_file = None  # the output file handle
        self._config_file = None  # the configuration file handle
        self._text = None  # the unicode text string that is being annotated
        self._name_dict = {}  # a remapping of annotation names

        self._resetStates()  # states for OTPL parsing

        # capture a few names to write a rudimentary brat config file:
        self._entities = dict()  # {name: None}
        self._relations = defaultdict(set)  # {name: {column}}
        # only the argument position is used in the list of events;
        # the Boolean value indicates if the argument is required;
        # that is, if the argument (a reference in its column) was observed for all events:
        self._events = dict()  # will be: {name: [(column, bool)]}
        # only stored as reference (normalizations have to be configured in tools.conf):
        self._normalizations = set()  # {namespace}
        # the default modifier added (if absent) is ``True``:
        self._attributes = defaultdict(lambda: (set(), set()))  # {name: ({modifier}, {column})}

    def set_name_dict(self, name_dict):
        """
        Define a name-to-labels mapping to avoid illegal brat names.

        In brat, names must follow the pattern ``/^[\w-]+$/``.
        If not, the annotation is ignored by the system and this conversion process skips the
        annotation.
        Therefore, with this mapping, such problematic names can be re-mapped to valid brat
        names, while the original name still can be shown in the interface if the same mapping
        is defined in the labels_ section of the brat ``visual.conf`` file.
        (Therefore, the command-line tool knows how to extract any such mapping from
        ``visual.conf``.)

        .. _labels: http://brat.nlplab.org/configuration.html#visual-configuration

        :type name_dict: dict
        """
        self._name_dict = name_dict

    def set_colspec(self, otpl_colspec):
        """
        Define the :class:`otplc.colspec.ColumnSpecification` the OTPL input files follow.

        :type otpl_colspec: otplc.colspec.ColumnSpecification
        """
        self._colspec = otpl_colspec

    def convert(self, segments, text_file, brat_file=None):
        """
        Read an input `OTPL file` and write a `brat file` for a given `text file`.

        :param segments: a :class:`OtplReader` instance
        :param text_file: the path to the annotated (plain-) text file
        :param brat_file: the path to the brat file (by default determined by suffix replacement)
        :return: True if successful, False otherwise
        """
        if self._colspec is None:
            L.warning(u'cannot run without a colspec - specify one manually')
            return False

        if brat_file is None:
            brat_file = _make_path_to(text_file, Configuration.BRAT_SUFFIX)

        L.info(u'"%s" to "%s" using "%s"', segments.path, brat_file, text_file)
        self._text = open(text_file, mode='rt').read().decode('utf-8')
        self._resetStates()

        # NB: processing order is significant to resolve references
        try:
            if self._colspec.has_global_refs():
                self._convertWithGlobals(segments, brat_file)
            else:
                self._convertLocal(segments, brat_file)
        except Exception as e:
            L.warning(u'failed - %s', e.message)
            return False

        return True

    def write_config_file(self, file_path):
        """ Write the annotation.conf file in the given location. """
        with open(file_path, 'wb') as self._config_file:
            if self._entities:
                self._writeConfigFor(u'entities', self._entities.items(), self._writeEntityType)

            if self._relations:
                self._writeConfigFor(u'relations', self._relations.items(), self._writeRelationType)

            if self._events:
                self._writeConfigFor(u'events', self._events.items(), self._writeEventType)

            if self._attributes:
                self._writeConfigFor(u'attributes', self._attributes.items(),
                                     self._writeAttributeType)

            if self._normalizations:
                self._storeDatabaseNames()

    def _resetStates(self):
        """ Per-file parse states. """
        # brat ID counters
        self._entity_counter = count(1)
        self._relation_counter = count(1)
        self._event_counter = count(1)
        self._normalization_counter = count(1)
        self._attribute_counter = count(1)

        # OTPL enum <-> brat ID mapping helpers
        self._global_map = None
        self.__global_count = 0
        self.__line_count = 1
        self._local_map = dict()

    def _convertLocal(self, segments, brat_file):
        offset = 0

        with open(brat_file, 'wt') as self._annotation_file:
            for seg in segments:
                unused, offset = self._convertTokensAndEntities(seg, offset)
                self._convertAnnotations(seg)
                self.__global_count += len(seg)
                self.__line_count += len(seg) + 1

    def _convertWithGlobals(self, segments, brat_file):
        """
        If global references are present, they might point to entities in the future
        (that is, after the end of the current segment),
        so this approach iteratively creates the targets for the whole OTPL file
        by reading it twice (once for entities, and once for the other types).
        In other words, a OTPL file with global references is more expensive to convert.
        """
        self._global_map = defaultdict(dict)
        offset = 0
        local_maps = []

        with open(brat_file, 'wt+') as self._annotation_file:
            for seg in segments:
                lmap, offset = self._convertTokensAndEntities(seg, offset)
                local_maps.append(lmap)
                self.__global_count += len(seg)
                self.__line_count += len(seg) + 1

            self.__global_count = 0
            self.__line_count = 1
            local_maps = reversed(local_maps)

            for seg in segments:
                self._local_map = next(local_maps)
                self._convertAnnotations(seg)
                self.__global_count += len(seg)
                self.__line_count += len(seg) + 1

    def _convertTokensAndEntities(self, segment, start):
        """ Convert the `segment` annotating the text starting at `offset`. """
        L.debug(u'global_count=%d line_count=%d', self.__global_count, self.__line_count)
        L.debug(u'text at offset=%s:\n%s...', start,
                self._text[start:start + 75].replace('\n', ' ').strip())
        L.debug(u'segment:\n%s', '\n'.join('\t'.join(row) for row in segment))
        self._local_map = defaultdict(dict)
        offsets = list(self._yieldOffsets(start, segment))
        assert len(offsets) == len(segment)
        self._processPoS(segment, offsets)
        self._processEntities(segment, offsets)
        return self._local_map, offsets[-1][-1]

    def _convertAnnotations(self, segment):
        for columns, makerMethod in [
            (self._colspec.iter_relations(), self._makeRelation),
            (self._colspec.iter_events(), self._makeEvent),
            (self._colspec.iter_normalizations(), self._makeNormalization),
            (self._colspec.iter_attributes(), self._makeAttribute),
        ]:
            self._processColumnsWith(segment, columns, makerMethod)

    def _yieldOffsets(self, start, segment):
        c = self._colspec.token

        for idx, row in enumerate(segment):
            token = row[c]
            length = len(token)

            try:
                update = self._text.index(token, start)

                if update - start > 1000:
                    L.warning(u'"%s" found %d chars after "%s..."',
                              token, update - start, self._text[start:start + len(token) + 10])

                start = update
            except ValueError:
                content = self._text[start:start + len(token) + 10].replace('\n', '\\n')
                raise ValueError(u'token "%s" from line %d not found at "%s" (%d)' % (
                    token, self.__line_count + idx, content, start
                ))

            yield (start, start + length)
            start += length

    def _processPoS(self, segment, offsets):
        col = self._colspec.pos_tag

        if col is not None:
            for idx, data in enumerate(segment):
                val = data[col]

                if val and val != u'NULL':
                    self._makeEntity([data], idx + 1, col, *offsets[idx])

    def _processEntities(self, segment, offsets):
        for col in self._colspec.iter_entities():
            rows, start = self._parseBIEO(segment, col, offsets)

            if rows:
                self._makeEntity(rows, len(segment) - len(rows), col, start, offsets[-1][-1])

    def _processColumnsWith(self, segment, column_iter, makeAnnotation):
        for col in column_iter:
            for row, data in enumerate(segment, 1):
                makeAnnotation(data, row, col)

    def _parseBIEO(self, segment, col, offsets):
        start, data_rows = 0, []
        row_num = lambda: idx + 1 - len(data_rows)

        for idx, data in enumerate(segment):
            val = data[col]

            if val.startswith(u'B-'):
                if data_rows:
                    self._makeEntity(data_rows, row_num(), col, start, offsets[idx - 1][-1])

                start = offsets[idx][0]
                data_rows = [data]
            elif val.startswith(u'E-'):
                if data_rows:
                    data_rows.append(data)
                    self._makeEntity(data_rows, row_num(), col, start, offsets[idx][-1])
                    data_rows = []
                else:
                    self._makeEntity([data], row_num(), col, *offsets[idx])
            elif val.startswith(u'I-'):
                if not data_rows:  # start of IEO tags
                    start = offsets[idx][0]
                    data_rows = []

                data_rows.append(data)
            elif val == u'O':
                if data_rows:
                    self._makeEntity(data_rows, row_num(), col, start, offsets[idx - 1][-1])
                    data_rows = []
            else:
                L.warning(u'bad BIO entity tag: "%s"', val)

        return data_rows, start

    def _makeEntity(self, rows, row_num, col, start, end):
        pos_col = self._colspec.pos_tag
        off = 0 if col == pos_col else 2

        try:
            name = self._validateName(rows[0][col][off:])
        except IndexError:
            L.error(u'could not detect the entity name at col=%s, off=%s in %s', col, off, rows)
            return
        except DataFormatError:
            L.error(u'brat cannot cope with entity name "%s" in column %d',
                    rows[0][col][off:], col + 1)
            return

        if col != pos_col:
            assert all(r[col][2:] == name for r in rows), [r[col] for r in rows]

        uid = self._register(col, u'T', self._entity_counter, row_num, *rows)

        if name not in self._entities:
            self._entities[name] = None

        self._storeAnnotation(brat.Entity(uid, name, start, end, self._text[start:end]))

    def _makeNormalization(self, data, row_num, col):
        ns_id = data[col]

        if ns_id and ns_id != u'NULL':
            target_col = self._colspec.get_normalization_target(col)
            target_id = self._getLocalTargetID(target_col, data, row_num)
            uid = self._register(col, u'N', self._normalization_counter, row_num, data)
            string = ns_id

            if u' ' in ns_id:
                ns_id, string = ns_id.split(u' ', 1)

            name = ns_id.split(u':', 1)[0]

            try:
                self._validateName(name)
            except DataFormatError:
                L.error(u'brat cannot cope with database name "%s" in column %d', name, col + 1)
                return

            self._normalizations.add(name)  # namespace only
            self._storeAnnotation(brat.Normalization(uid, u'Reference', target_id, ns_id, string))

    def _makeRelation(self, data, row_num, col):
        name = data[col]
        ref_col = col - 1

        if data[ref_col] and name and data[ref_col] != u'0' and name != u'NULL':
            try:
                name = self._validateName(name)
            except DataFormatError:
                L.error(u'brat cannot cope with relation name "%s" in column %d', name, col + 1)
                return

            uid = self._register(col, u'R', self._relation_counter, row_num, data)
            source_col = self._colspec.get_relation_target(col)
            source_id = self._getLocalTargetID(source_col, data, row_num)
            target_id = self._getReferencedID(data, ref_col)
            self._relations[name].add(col)
            self._storeAnnotation(brat.Relation(uid, name, source_id, target_id))

    def _makeEvent(self, data, row_num, col):
        name = data[col]
        trigger_col, ref_cols = self._colspec.get_event_targets(col)

        if name and name != u'NULL' and data[trigger_col] and data[trigger_col] != u'0':
            try:
                name = self._validateName(name)
            except DataFormatError:
                L.error(u'brat cannot cope with event name "%s" in column %d', name, col + 1)
                return

            uid = self._register(col, u'E', self._event_counter, row_num, data)
            trigger_id = self._getReferencedID(data, trigger_col)
            ref_ids = [None if data[c] == u'0' else self._getReferencedID(data, c)
                       for c in ref_cols]
            references = [u"Arg%d:%s" % (num, rid)
                          for num, rid in enumerate(ref_ids, 1) if rid is not None]
            self._storeEventArguments(name, zip(ref_cols, [i is not None for i in ref_ids]))
            self._storeAnnotation(brat.Event(uid, name, trigger_id, references))

    def _storeEventArguments(self, name, col_req_pairs):
        if name in self._events:
            existing_pairs = self._events[name]
            is_required = 1  # the second element in the pair; for readability

            for idx, new_pair in enumerate(col_req_pairs):
                if not new_pair[is_required] and existing_pairs[idx][is_required]:
                    existing_pairs[idx] = (new_pair[0], False)
        else:
            self._events[name] = col_req_pairs

    def _makeAttribute(self, data, row_num, col):
        name = data[col]

        if name and name != u'NULL':
            try:
                name = self._validateName(name)
            except DataFormatError:
                L.error(u'brat cannot cope with attribute name "%s" in column %d', name, col + 1)
                return

            uid = u'A', + self._attribute_counter.next()
            target_col = self._colspec.get_attribute_target(col)
            target = self._getLocalTargetID(target_col, data, row_num)
            modifier = ''

            if u' ' in name:
                idx = name.index(u' ')
                name, modifier = name[:idx], name[idx:]

            mods, cols = self._attributes[name]
            mods.add(modifier.rstrip(u' ') if modifier else True)
            cols.add(col)
            self._storeAnnotation(brat.Attribute(uid, name, target, modifier))

    def _storeAnnotation(self, ann):
        self._annotation_file.write(str(ann))
        self._annotation_file.write(os.linesep)

    def _register(self, col, letter, counter, num, *data_items):
        uid = letter + str(counter.next())  # the uid for this brat annotation
        global_enum = self._colspec.global_enum
        local_enum = self._colspec.local_enum
        base_num = self.__global_count + num

        for idx, data in enumerate(data_items):  # register the uid to each data row
            if self._global_map is not None:
                global_id = str(base_num + idx) if global_enum is None else data[global_enum]
                self._global_map[col].setdefault(global_id, uid)

            local_id = str(num + idx) if local_enum is None else data[local_enum]
            self._local_map[col].setdefault(local_id, uid)

        return uid

    def _getReferencedID(self, data, ref_col):
        target_col = self._colspec.get_reference_target(ref_col)

        try:
            if self._colspec.is_global_ref(ref_col):
                return self._getGlobalID(target_col, data[ref_col])
            else:
                return self._getLocalID(target_col, data[ref_col])
        except RuntimeError as e:
            raise ValueError(u'unresolved reference %d->%d with number %s' % (
                ref_col + 1, target_col + 1, data[ref_col]
            ))

    def _getLocalTargetID(self, target_col, data, row_num):
        row = str(row_num) if self._colspec.local_enum is None else data[self._colspec.local_enum]

        try:
            return self._getLocalID(target_col, row)
        except RuntimeError as e:
            raise ValueError(
                u'unresolved local target column %d with number %s' % (target_col + 1, row)
            )

    def _getLocalID(self, col, num):
        return self.__getID(col, num, self._local_map)

    def _getGlobalID(self, col, num):
        return self.__getID(col, num, self._global_map)

    def __getID(self, col, num, mapping):
        if num in mapping[col]:
            return mapping[col][num]
        else:
            raise RuntimeError(u'unknown num=%s in column=%s' % (num, col))

    def _writeConfigFor(self, section, collection, writeConfig):
        """ Write the collection of names for a section to the configuration file. """
        self._storeConfiguration(u'\n[%s]\n\n' % section)

        for name, data in sorted(collection):
            writeConfig(name, data)

    def _writeEntityType(self, name, unused):
        """ Write the entity name, None pair to the configuration file. """
        self._storeConfiguration(u'%s\n' % name)

    def _writeRelationType(self, name, columns):
        """ Write the relation name, columns pair to the configuration file. """
        self._storeConfiguration(u'%s\t' % name)

        target1 = self._elicitShortcutFor(
            columns, self._colspec.get_relation_target
        )
        target2 = self._elicitShortcutFor(
            columns, lambda c: self._colspec.get_reference_target(c - 1)
        )
        self._storeConfiguration(u'Arg1:%s, Arg2:%s\n' % (target1, target2))

    def _writeEventType(self, name, pairs):
        """ Write the event name, pairs pair to the configuration file. """
        self._storeConfiguration(u'%s\t' % name)
        arguments = []

        for col, req in pairs:
            shortcut = self._elicitShortcutFor([col], self._colspec.get_reference_target)
            arguments.append(u'Col%d%s:%s' % (
                col + 1, u'' if req else u'?', shortcut
            ))

        self._storeConfiguration(u', '.join(arguments))
        self._storeConfiguration(u'\n')

    def _writeAttributeType(self, name, values):
        """ Write the attribute name, values pair to the configuration file. """
        modifiers = u'' if len(values[0]) == 1 else u', Value:%s' % u'|'.join(values[0])
        shortcut = self._elicitShortcutFor(values[1], self._colspec.get_attribute_target)
        self._storeConfiguration(u'%s\tArg:%s%s\n' % (name, shortcut, modifiers))

    def _storeDatabaseNames(self):
        self._storeConfiguration(u'\n# [normalization]\n')

        for name in self._normalizations:
            try:
                name = self._validateName(name)
                self._storeConfiguration(OtplBratConverter.NORMALIZATION_LINE % name)
            except DataFormatError:
                L.warning(u'database name "%s" has illegal characters', name)
                self._storeConfiguration(u'# %s\n' % name)

    def _storeConfiguration(self, string):
        self._config_file.write(string.encode('utf-8'))

    def _elicitShortcutFor(self, cols, targetColumn):
        """ Establish the best shortcut name for the configuration file. """
        coltype = None

        for c in cols:
            update = self._colspec.get_property_target_column_type(targetColumn(c))

            if coltype is None:
                coltype = update
            elif coltype != update:
                coltype = ColumnSpecification._ANNOTATION
                break

        if coltype == ColumnSpecification._ANNOTATION:
            return u'<ANY>'
        elif coltype in ColumnSpecification._ENTITY_COLUMNS:
            return u'<ENTITY>'
        elif coltype == ColumnSpecification.RELATION:
            return u'<RELATION>'
        elif coltype == ColumnSpecification.EVENT:
            return u'<EVENT>'
        else:
            raise ValueError(
                u'illegal shortcut %s for %s' % (str(coltype), str(cols))
            )

    def _validateName(self, name):
        if name in self._name_dict:
            name = self._name_dict[name]

        if not A_VALID_NAME.match(name):
            raise DataFormatError('illegal name=%s' % name)

        return name


def otpl_to_brat(configuration):
    """
    For a list of `text_files` (paths), read the associated OTPL files and write the converted
    brat files.

    :type configuration: Configuration
    :return: the error count (number of failed conversions)
    """
    converter = OtplBratConverter()
    converter.set_colspec(configuration.colspec)
    errors = 0

    if configuration.name_labels is not None:
        converter.set_name_dict(configuration.name_labels)

    for text_file in configuration.text_files:
        otpl_file = _make_path_to(text_file, configuration.otpl_suffix)
        brat_file = _make_path_to(text_file, configuration.brat_suffix)

        if exists(otpl_file):
            segments = configure_reader(otpl_file, configuration.filter, configuration.separator)

            if segments is None:
                errors += 1
                continue

            if configuration.colspec is None:
                configuration.colspec = guess_colspec(segments)
                converter.set_colspec(configuration.colspec)

            if not converter.convert(segments, text_file, brat_file):
                L.error(u'conversion for "%s" failed', text_file)
                errors += 1
        else:
            L.error(u'could not locate OTPL file "%s" for "%s"', otpl_file, text_file)
            errors += 1

    if not errors:
        brat_config_file = join(dirname(configuration.text_files[-1]), configuration.config)

        if not exists(brat_config_file):
            converter.write_config_file(brat_config_file)

    if errors:
        L.debug(u'conversion of %s file%s failed', errors, u'' if errors == 1 else u's')

    return errors


def _make_path_to(text_file, suffix):
    """Replace the `text_file` suffix with `suffix."""
    base, ext = splitext(text_file)
    return u'%s%s' % (base, suffix)
