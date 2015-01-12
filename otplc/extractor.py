"""
Reconstruct the text of a OTPL file using the tokens.
"""
from logging import getLogger
from os import remove
from os.path import splitext
from otplc import configure_reader, guess_colspec
from otplc.converter import make_path_to


L = getLogger('otplc.extractor')


def segment_otpl_file(otpl_file, factor, encoding):
    """
    Split a OTPL file into smaller ones, placing at most `factor` segments in each.

    :param otpl_file: The OTPL file to split.
    :param factor: The split factor; should be a positive integer.
    :param encoding: The character encoding of the OTPL file.
    :return: A list of all the names of the new files.
    """
    assert factor > 0, "factor not in (0,MAXINT] range"
    basename, extension = splitext(otpl_file)
    segment_file_names = []
    segment_count = 0
    out_stream = _new_segment_file(basename, len(segment_file_names), extension, encoding)
    segment_file_names.append(out_stream.name)

    with open(otpl_file, encoding=encoding) as in_stream:
        for raw in in_stream:
            line = raw.strip()

            if not line:
                segment_count += 1
                print('', file=out_stream)

                if segment_count == factor:
                    out_stream.close()
                    out_stream = _new_segment_file(basename, len(segment_file_names), extension,
                                                   encoding)
                    segment_file_names.append(out_stream.name)
                    segment_count = 0
            else:
                print(line, file=out_stream)

    if segment_count == 0:
        remove(segment_file_names.pop())

    out_stream.close()
    return segment_file_names


def _new_segment_file(basename, segment_id, extension, encoding):
    """Open a new file for the given basename, segment_id, and extension (with leading dot)."""
    out_file = "%s-%i%s" % (basename, segment_id, extension)
    return open(out_file, encoding=encoding, mode='wt')


def otpl_to_text(configuration):
    """
    Extract the text using the tokens of the OTPL files and store the results into separate
    plain-text files.

    :param configuration: a :class:`otplc.settings.Configuration` object
    :return: The number of failed conversion for the input files.
    """
    errors = 0

    for otpl_file in configuration.input_files:
        text_file = make_path_to(otpl_file, configuration.text_suffix)
        msg = "output text file and input OTPL file have the same path " \
              "(ensure the OTPL file does not use the extension '{}')"
        assert otpl_file != text_file, msg.format(configuration.text_suffix)
        segments = configure_reader(otpl_file, configuration)

        if segments is None:
            errors += 1
            continue

        if configuration.colspec is None:
            configuration.colspec = guess_colspec(segments)

        token = configuration.colspec.token

        try:
            with open(text_file, encoding=configuration.encoding, mode='wt') as out_stream:
                for seg in segments:
                    print(*[row[token] for row in seg], file=out_stream)
        except IOError as e:
            L.error('I/O error while extracting %s to %s: %s', otpl_file, text_file, str(e))
            errors += 1

    return errors