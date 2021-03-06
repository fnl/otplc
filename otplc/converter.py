"""
Transform a OTPL file to and from brat annotations.
"""
import os
from itertools import count
from logging import getLogger
from collections import defaultdict
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
    A class that, given a column specification, can convert a OTPL standoff
    annotation file and write a brat standoff annotation file given the
    (underlying) text file.

    To use this class, you first initialize an instance and pass it a OTPL
    column specification (colspec) using :meth:`.set_colspec`.
    That colspec is then used for the conversion with :meth:`.convert`.
    For each text file, :meth:`convert` directly reads the OTPL file and writes
    the brat annotation file.
    After all files have been converted, :meth:`.write_config_file` can be used
    to write the brat annotation configuration setup using the detected names
    ("brat annotation types").
    """

    NORMALIZATION_LINE = '# %s\t<URL>:http://example.com/, <URLBASE>:http://example.com/%%s\n'
    "The config file line used for normalization database names (should be moved to tools.conf)"

    def __init__(self):
        self._colspec = None  # the column specification instance
        self._annotation_file = None  # the output file handle
        self._config_file = None  # the configuration file handle
        self._text = None  # the str text string that is being annotated
        self._name_dict = {}  # a remapping of annotation names

        self._reset_states()  # states for OTPL parsing

        # capture a few names to write a rudimentary brat config file:
        self._entities = dict()  # {name: None}
        self._relations = defaultdict(set)  # {name: {column}}
        # only the argument position is used in the list of events;
        # the Boolean value indicates if the argument is required;
        # that is, if the argument (a reference in its column)
        # was observed for all events:
        self._events = dict()  # will be: {name: [(column, bool)]}
        # only stored as reference
        # (normalizations have to be configured in tools.conf):
        self._normalizations = set()  # {namespace}
        # the default modifier added (if absent) is ``True``:
        self._attributes = defaultdict(lambda: (set(), set()))
        # {name: ({modifier}, {column})}

    def set_name_dict(self, name_dict):
        """
        Define a name-to-labels mapping to avoid illegal brat names.

        In brat, names must follow the pattern ``/^[\w-]+$/``.
        If not, the annotation is ignored by the system and this conversion
        process skips the annotation.
        Therefore, with this mapping, such problematic names can be re-mapped
        to valid brat names, while the original name still can be shown in the
        interface if the same mapping is defined in the labels_ section of the
        brat ``visual.conf`` file.
        (Therefore, the command-line tool knows how to extract any such mapping
        from ``visual.conf``.)

        .. _labels: http://brat.nlplab.org/configuration.html#visual-configuration

        :type name_dict: dict
        """
        self._name_dict = name_dict

    def set_colspec(self, otpl_colspec):
        """
        Define the :class:`otplc.colspec.ColumnSpecification` the OTPL input
        files follow.

        :type otpl_colspec: otplc.colspec.ColumnSpecification
        """
        self._colspec = otpl_colspec

    def convert(self, segments, text_file, brat_file=None):
        """
        Read an input `OTPL file` and write a `brat file` for a given `text
        file`.

        Note that the whole text file will be read into memory.

        :param segments: a :class:`OtplReader` instance
        :param text_file: the path to the annotated (plain-) text file
        :param brat_file: the path to the brat file (by default determined by
                          suffix replacement)
        :return: True if successful, False otherwise
        """
        if self._colspec is None:
            L.warning('cannot run without a colspec - specify one manually')
            return False

        if brat_file is None:
            brat_file = make_path_to(text_file, Configuration.BRAT_SUFFIX)

        L.info('"%s" to "%s" using "%s"', segments.path, brat_file, text_file)
        self._text = open(text_file, encoding='utf-8').read()
        self._reset_states()

        # NB: processing order is significant to resolve references
        try:
            if self._colspec.has_global_refs():
                self._convert_with_globals(segments, brat_file)
            else:
                self._convert_local(segments, brat_file)
        except (ValueError, DataFormatError) as e:
            L.warning('failed - %s', str(e))
            return False

        return True

    def write_config_file(self, file_path):
        """ Write the annotation.conf file in the given location. """
        with open(file_path, 'wb') as self._config_file:
            if self._entities:
                self._write_config_for('entities', self._entities.items(),
                                       self._write_entity_type)

            if self._relations:
                self._write_config_for('relations', self._relations.items(),
                                       self._write_relation_type)

            if self._events:
                self._write_config_for('events', self._events.items(),
                                       self._write_event_type)

            if self._attributes:
                self._write_config_for('attributes', self._attributes.items(),
                                       self._write_attribute_type)

            if self._normalizations:
                self._store_database_names()

    def _reset_states(self):
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

    def _convert_local(self, segments, brat_file):
        offset = 0

        with open(brat_file, 'wt') as self._annotation_file:
            for seg in segments:
                unused, offset = self._convert_tokens_and_entities(seg, offset)
                self._convert_annotations(seg)
                self.__global_count += len(seg)
                self.__line_count += len(seg) + 1

    def _convert_with_globals(self, segments, brat_file):
        """
        If global references are present, they might point to entities in the
        future (that is, after the end of the current segment), so this
        approach iteratively creates the targets for the whole OTPL file by
        reading it twice (once for entities, and once for the other types).
        In other words, a OTPL file with global references is more expensive to
        convert.
        """
        self._global_map = defaultdict(dict)
        offset = 0
        local_maps = []

        with open(brat_file, 'wt+') as self._annotation_file:
            for seg in segments:
                lmap, offset = self._convert_tokens_and_entities(seg, offset)
                local_maps.append(lmap)
                self.__global_count += len(seg)
                self.__line_count += len(seg) + 1

            self.__global_count = 0
            self.__line_count = 1
            local_maps = reversed(local_maps)

            for seg in segments:
                self._local_map = next(local_maps)
                self._convert_annotations(seg)
                self.__global_count += len(seg)
                self.__line_count += len(seg) + 1

    def _convert_tokens_and_entities(self, segment, start):
        """ Convert the `segment` annotating the text starting at `offset`. """
        L.debug('global_count=%d line_count=%d',
                self.__global_count, self.__line_count)
        L.debug('text at offset=%s:\n%s...', start,
                self._text[start:start + 75].replace('\n', ' ').strip())
        L.debug('segment:\n%s', '\n'.join('\t'.join(row) for row in segment))
        self._local_map = defaultdict(dict)
        offsets = list(self._yield_offsets(start, segment))
        assert len(offsets) == len(segment)
        self._process_pos(segment, offsets)
        self._process_entities(segment, offsets)
        return self._local_map, offsets[-1][-1]

    def _convert_annotations(self, segment):
        for columns, maker_method in [
            (self._colspec.iter_relations(), self._make_relation),
            (self._colspec.iter_events(), self._make_event),
            (self._colspec.iter_normalizations(), self._make_normalization),
            (self._colspec.iter_attributes(), self._make_attribute),
        ]:
            OtplBratConverter._process_columns_with(segment, columns,
                                                    maker_method)

    def _yield_offsets(self, start, segment):
        c = self._colspec.token

        for idx, row in enumerate(segment):
            token = row[c]
            length = len(token)

            try:
                update = self._text.index(token, start)

                if update - start > 1000:
                    L.warning('"%s" found %d chars after "%s..."',
                              token, update - start,
                              self._text[start:start + len(token) + 10])

                start = update
            except ValueError:
                content = self._text[start:start + len(token) + 10].replace(
                    '\n', '\\n'
                )
                raise ValueError(
                    'token "%s" from line %d not found at "%s" (%d)' % (
                        token, self.__line_count + idx, content, start
                    )
                )

            yield (start, start + length)
            start += length

    def _process_pos(self, segment, offsets):
        col = self._colspec.pos_tag

        if col is not None:
            for idx, data in enumerate(segment):
                val = data[col]

                if val and val != 'NULL':
                    self._make_entity([data], idx + 1, col, *offsets[idx])

    def _process_entities(self, segment, offsets):
        for col in self._colspec.iter_entities():
            rows, start = self._parse_bioe(segment, col, offsets)

            if rows:
                self._make_entity(rows, len(segment) - len(rows),
                                  col, start, offsets[-1][-1])

    @staticmethod
    def _process_columns_with(segment, column_iter, make_annotation):
        for col in column_iter:
            for row, data in enumerate(segment, 1):
                make_annotation(data, row, col)

    def _parse_bioe(self, segment, col, offsets):
        start, data_rows = 0, []
        row_num = lambda: idx + 1 - len(data_rows)

        for idx, data in enumerate(segment):
            val = data[col]

            if val.startswith('B-'):
                if data_rows:
                    self._make_entity(data_rows, row_num(),
                                      col, start, offsets[idx - 1][-1])

                start = offsets[idx][0]
                data_rows = [data]
            elif val.startswith('E-'):
                if data_rows:
                    data_rows.append(data)
                    self._make_entity(data_rows, row_num(),
                                      col, start, offsets[idx][-1])
                    data_rows = []
                else:
                    self._make_entity([data], row_num(),
                                      col, *offsets[idx])
            elif val.startswith('I-'):
                if not data_rows:  # start of IEO tags
                    start = offsets[idx][0]
                    data_rows = []

                data_rows.append(data)
            elif val == 'O':
                if data_rows:
                    self._make_entity(data_rows, row_num(),
                                      col, start, offsets[idx - 1][-1])
                    data_rows = []
            else:
                L.warning('bad BIO entity tag: "%s"', val)

        return data_rows, start

    def _make_entity(self, rows, row_num, col, start, end):
        pos_col = self._colspec.pos_tag
        off = 0 if col == pos_col else 2

        try:
            name = self._validate_name(rows[0][col][off:])
        except IndexError:
            L.error('could not detect the entity name at col=%s, off=%s in %s',
                    col, off, rows)
            return
        except DataFormatError:
            L.error('brat cannot cope with entity name "%s" in column %d',
                    rows[0][col][off:], col + 1)
            return

        if col != pos_col:
            assert all(
                r[col][2:] == name for r in rows
            ), [r[col] for r in rows]

        uid = self._register(col, 'T', self._entity_counter, row_num, *rows)

        if name not in self._entities:
            self._entities[name] = None

        self._store_annotation(brat.Entity(uid, name, start, end,
                                           self._text[start:end]))

    def _make_normalization(self, data, row_num, col):
        ns_id = data[col]

        if ns_id and ns_id != 'NULL':
            target_col = self._colspec.get_normalization_target(col)
            target_id = self._get_local_target_id(target_col, data, row_num)
            uid = self._register(col, 'N', self._normalization_counter,
                                 row_num, data)
            string = ns_id

            if ' ' in ns_id:
                ns_id, string = ns_id.split(' ', 1)

            db, xref = ns_id.split(':', 1)

            try:
                self._validate_name(db)
            except DataFormatError:
                L.error('brat cannot cope with DB name "%s" in column %d',
                        db, col + 1)
                return

            self._normalizations.add(db)  # DB namespace only
            self._store_annotation(brat.Normalization(uid, target_id, db,
                                                      xref, string))

    def _make_relation(self, data, row_num, col):
        name = data[col]
        ref_col = col - 1

        if data[ref_col] and name and data[ref_col] != '0' and name != 'NULL':
            try:
                name = self._validate_name(name)
            except DataFormatError:
                L.error(
                    'brat cannot cope with relation name "%s" in column %d',
                    name, col + 1
                )
                return

            uid = self._register(col, 'R', self._relation_counter, row_num,
                                 data)
            source_col = self._colspec.get_relation_target(col)
            source_id = self._get_local_target_id(source_col, data, row_num)
            target_id = self._get_referenced_id(data, ref_col)
            self._relations[name].add(col)
            self._store_annotation(brat.Relation(uid, name,
                                                 source_id, target_id))

    def _make_event(self, data, row_num, col):
        name = data[col]
        trigger_col, ref_cols = self._colspec.get_event_targets(col)

        if name and name != 'NULL' and \
                data[trigger_col] and data[trigger_col] != '0':
            try:
                name = self._validate_name(name)
            except DataFormatError:
                L.error('brat cannot cope with event name "%s" in column %d',
                        name, col + 1)
                return

            uid = self._register(col, 'E', self._event_counter, row_num, data)
            trigger_id = self._get_referenced_id(data, trigger_col)
            ref_ids = [(None if data[c] == '0' else
                        self._get_referenced_id(data, c)) for c in ref_cols]
            references = dict(('Arg%d' % num, rid)
                              for num, rid in enumerate(ref_ids, 1)
                              if rid is not None)
            self._store_event_arguments(
                name, list(zip(ref_cols, [i is not None for i in ref_ids]))
            )
            self._store_annotation(brat.Event(uid, name, trigger_id,
                                              **references))

    def _store_event_arguments(self, name, col_req_pairs):
        if name in self._events:
            existing_pairs = self._events[name]
            is_required = 1  # the second element in the pair; for readability

            for idx, new_pair in enumerate(col_req_pairs):
                if not new_pair[is_required] and \
                        existing_pairs[idx][is_required]:
                    existing_pairs[idx] = (new_pair[0], False)
        else:
            self._events[name] = col_req_pairs

    def _make_attribute(self, data, row_num, col):
        name = data[col]

        if name and name != 'NULL':
            try:
                name = self._validate_name(name)
            except DataFormatError:
                L.error(
                    'brat cannot cope with attribute name "%s" in column %d',
                    name, col + 1
                )
                return

            uid = 'A', + next(self._attribute_counter)
            target_col = self._colspec.get_attribute_target(col)
            target = self._get_local_target_id(target_col, data, row_num)
            modifier = ''

            if ' ' in name:
                idx = name.index(' ')
                name, modifier = name[:idx], name[idx:]

            mods, cols = self._attributes[name]
            mods.add(modifier.rstrip(' ') if modifier else True)
            cols.add(col)
            self._store_annotation(brat.Attribute(uid, name, target, modifier))

    def _store_annotation(self, ann):
        self._annotation_file.write(str(ann))
        self._annotation_file.write(os.linesep)

    def _register(self, col, letter, counter, num, *data_items):
        uid = letter + str(next(counter))  # the uid for this brat annotation
        global_enum = self._colspec.global_enum
        local_enum = self._colspec.local_enum
        base_num = self.__global_count + num

        # register the uid to each data row
        for idx, data in enumerate(data_items):
            if self._global_map is not None:
                global_id = str(base_num + idx) if global_enum is None else \
                    data[global_enum]
                self._global_map[col].setdefault(global_id, uid)

            local_id = str(num + idx) if local_enum is None else \
                data[local_enum]
            self._local_map[col].setdefault(local_id, uid)

        return uid

    def _get_referenced_id(self, data, ref_col):
        target_col = self._colspec.get_reference_target(ref_col)

        try:
            if self._colspec.is_global_ref(ref_col):
                return self._get_global_id(target_col, data[ref_col])
            else:
                return self._ge_local_id(target_col, data[ref_col])
        except RuntimeError:
            raise ValueError('unresolved reference %d->%d with number %s' % (
                ref_col + 1, target_col + 1, data[ref_col]
            ))

    def _get_local_target_id(self, target_col, data, row_num):
        row = str(row_num) if self._colspec.local_enum is None else \
            data[self._colspec.local_enum]

        try:
            return self._ge_local_id(target_col, row)
        except RuntimeError:
            raise ValueError(
                'unresolved local target column %d with number %s' % (
                    target_col + 1, row
                )
            )

    def _ge_local_id(self, col, num):
        return OtplBratConverter.__get_id(col, num, self._local_map)

    def _get_global_id(self, col, num):
        return OtplBratConverter.__get_id(col, num, self._global_map)

    @staticmethod
    def __get_id(col, num, mapping):
        if num in mapping[col]:
            return mapping[col][num]
        else:
            raise RuntimeError('unknown num=%s in column=%s' % (num, col))

    def _write_config_for(self, section, collection, write_config):
        """
        Write the collection of names for a section to the configuration file.
        """
        self._store_configuration('\n[%s]\n\n' % section)

        for name, data in sorted(collection):
            write_config(name, data)

    def _write_entity_type(self, name, _):
        """ Write the entity name, None pair to the configuration file. """
        self._store_configuration('%s\n' % name)

    def _write_relation_type(self, name, columns):
        """
        Write the relation name, columns pair to the configuration file.
        """
        self._store_configuration('%s\t' % name)

        target1 = self._elicit_shortcut_for(
            columns, self._colspec.get_relation_target
        )
        target2 = self._elicit_shortcut_for(
            columns, lambda c: self._colspec.get_reference_target(c - 1)
        )
        self._store_configuration('Arg1:%s, Arg2:%s\n' % (target1, target2))

    def _write_event_type(self, name, pairs):
        """ Write the event name, pairs pair to the configuration file. """
        self._store_configuration('%s\t' % name)
        arguments = []

        for col, req in pairs:
            shortcut = self._elicit_shortcut_for(
                [col], self._colspec.get_reference_target
            )
            arguments.append('Col%d%s:%s' % (
                col + 1, '' if req else '?', shortcut
            ))

        self._store_configuration(', '.join(arguments))
        self._store_configuration('\n')

    def _write_attribute_type(self, name, values):
        """
        Write the attribute name, values pair to the configuration file.
        """
        modifiers = '' if len(values[0]) == 1 else \
            ', Value:%s' % '|'.join(values[0])
        shortcut = self._elicit_shortcut_for(
            values[1], self._colspec.get_attribute_target
        )
        self._store_configuration(
            '%s\tArg:%s%s\n' % (name, shortcut, modifiers)
        )

    def _store_database_names(self):
        self._store_configuration('\n# [normalization]\n')

        for name in self._normalizations:
            try:
                name = self._validate_name(name)
                self._store_configuration(
                    OtplBratConverter.NORMALIZATION_LINE % name
                )
            except DataFormatError:
                L.warning('database name "%s" has illegal characters', name)
                self._store_configuration('# %s\n' % name)

    def _store_configuration(self, string):
        self._config_file.write(string.encode('utf-8'))

    def _elicit_shortcut_for(self, cols, get_target_column):
        """ Establish the best shortcut name for the configuration file. """
        coltype = None

        for c in cols:
            update = self._colspec.get_property_target_column_type(
                get_target_column(c)
            )

            if coltype is None:
                coltype = update
            elif coltype != update:
                coltype = ColumnSpecification._ANNOTATION
                break

        if coltype == ColumnSpecification._ANNOTATION:
            return '<ANY>'
        elif coltype in ColumnSpecification._ENTITY_COLUMNS:
            return '<ENTITY>'
        elif coltype == ColumnSpecification.RELATION:
            return '<RELATION>'
        elif coltype == ColumnSpecification.EVENT:
            return '<EVENT>'
        else:
            raise ValueError(
                'illegal shortcut %s for %s' % (str(coltype), str(cols))
            )

    def _validate_name(self, name):
        if name in self._name_dict:
            name = self._name_dict[name]

        if not A_VALID_NAME.match(name):
            raise DataFormatError('illegal name=%s' % name)

        return name


def otpl_to_brat(configuration):
    """
    For a list of `text_files` (paths), read the associated OTPL files and
    write the converted brat files.

    :type configuration: Configuration
    :return: the error count (number of failed conversions)
    """
    converter = OtplBratConverter()
    converter.set_colspec(configuration.colspec)
    errors = 0

    if configuration.name_labels is not None:
        converter.set_name_dict(configuration.name_labels)

    for text_file in configuration.input_files:
        otpl_file = make_path_to(text_file, configuration.otpl_suffix)
        brat_file = make_path_to(text_file, configuration.brat_suffix)

        if exists(otpl_file):
            segments = configure_reader(otpl_file, configuration)

            if segments is None:
                errors += 1
                continue

            if configuration.colspec is None:
                configuration.colspec = guess_colspec(segments)
                converter.set_colspec(configuration.colspec)

            if not converter.convert(segments, text_file, brat_file):
                L.error('conversion for "%s" failed', text_file)
                errors += 1
        else:
            L.error('could not locate OTPL file "%s" for "%s"',
                    otpl_file, text_file)
            errors += 1

    if not errors:
        brat_config_file = join(dirname(configuration.input_files[-1]),
                                configuration.config)

        if not exists(brat_config_file):
            converter.write_config_file(brat_config_file)

    if errors:
        L.debug('conversion of %s file%s failed',
                errors, '' if errors == 1 else 's')

    return errors


def make_path_to(text_file, suffix):
    """Replace the `text_file` suffix with `suffix."""
    base, ext = splitext(text_file)
    return '%s%s' % (base, suffix)
