#!/usr/bin/env python
# coding=utf-8

from re import compile, DOTALL, VERBOSE

try:
    from otplc.sspostproc import refine_split
except ImportError:
    # to use this on the command line
    from sspostproc import refine_split

# As defined by Pontus Stenetorp...
SENTENCES_DO_NOT_CROSS_LINES = compile(ur'''
        # Require a leading non-whitespace character for the sentence
        \S
        # Then, anything goes, but don't be greedy
        .*?
        # Anchor the sentence at...
        (:?
            # One (or multiple) terminal character(s)
            #   followed by one (or multiple) whitespace
            (:?(\.|!|\?|。|！|？)+(?=\s+))
        | # Or...
            # Newlines, to respect file formatting
            (:?(?=\n+))
        | # Or...
            # End-of-file, excluding whitespaces before it
            (:?(?=\s*$))
        )
    ''', DOTALL | VERBOSE)
# Similar...
SENTENCES_CROSS_LINES = compile(ur'''
        # Require a leading non-whitespace character for the sentence
        \S
        # Then, anything goes, but don't be greedy
        .*?
        # Anchor the sentence at...
        (:?
            # One (or multiple) terminal character(s)
            #   followed by one (or multiple) whitespace
            (:?(\.|!|\?|。|！|？)+(?=\s+))
        | # Or...
            # Consecutive newlines, to respect file formatting
            (:?(?=\n{2,}))
        | # Or...
            # End-of-file, excluding whitespaces before it
            (:?(?=\s*$))
        )
    ''', DOTALL | VERBOSE)


def regex_sentences(text):
    """
    Split sentences that never cross lines.

    :param text: input plain-text
    :return: a list of sentences with any inner newlines replaced with spaces
    """
    return _sentences(text, SENTENCES_DO_NOT_CROSS_LINES)


def multiline_sentences(text):
    """
    Split sentences that may cross newlines, except consecutive ones.

    :param text: input plain-text
    :return: a list of sentences with any inner newlines replaced with spaces
    """
    return _sentences(text, SENTENCES_CROSS_LINES)


def single_sentences(text):
    """
    Split at newlines, and return lines with content.

    :param text: input plain-text
    :return: a list of lines with content
    """
    return [s for s in text.split('\n') if s.strip()]


def rewrite_newlines(text, regex):
    """
    Remove newlines inside sentences and ensure there is one at their end.

    :param text: input plain-text
    :param regex: for the initial sentence splitting
    :return: a generator yielding the spans from the text
    """
    spaces_only = text.replace('\n', ' ')
    boundaries = _sentence_boundaries(text, regex)
    sentences = _text_segments(spaces_only, boundaries)
    sentences = refine_split('\n'.join(sentences)).split('\n')
    offset = 0
    last = len(text)

    for s in sentences:
        start = spaces_only.index(s, offset)
        end = start + len(s)
        yield text[offset:start]
        yield text[start:end].replace('\n', ' ')
        offset = end

        if offset != last:
            yield '\n'
            offset += 1

    if offset < last:
        yield text[offset:]


def _sentences(text, regex):
    boundaries = _sentence_boundaries(text, regex)
    sentences = _text_segments(text.replace('\n', ' '), boundaries)
    return refine_split('\n'.join(sentences)).split('\n')


def _sentence_boundaries(text, regex):
    for match in regex.finditer(text):
        yield match.span()

def _text_segments(text, offsets):
    for start, end in offsets:
        yield text[start:end]


if __name__ == '__main__':
    # print one sentence per line
    from sys import argv, stdout

    for txt_file_path in argv[1:]:
        text = open(txt_file_path, 'rt').read().decode('UTF-8')

        for span in rewrite_newlines(text, SENTENCES_CROSS_LINES):
            stdout.write(span.encode('utf-8'))
