"""
Reconstruct the text of a OTPL file using the tokens.
"""
from logging import getLogger
from otplc import configure_reader, guess_colspec
from otplc.converter import make_path_to


L = getLogger('otplc.extractor')


def otpl_to_text(configuration):
    """
    Extract the text using the tokens of the OTPL files and store the results into separate plain-text files.

    :param configuration: a :class:`otplc.settings.Configuration` object
    :return: The number of failed conversion for the input files.
    """
    errors = 0

    for otpl_file in configuration.text_files:
        text_file = make_path_to(otpl_file, configuration.text_suffix)
        assert otpl_file != text_file, "text file and OTPL file have the same path " \
                                       "(probable cause: OTPL file with suffix '.txt')"
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