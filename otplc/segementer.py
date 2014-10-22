#!/usr/bin/env python
"""
A pattern-based sentence segmentation strategy; Known limitations:

1. The sentence must use a known sentence terminal followed by space(s),
   skipping one optional, intervening quote and/or bracket.
1. The next sentence must start with an upper-case letter or a number,
   ignoring one optional quote and/or bracket before it.
1. If the sentence ends with a single upper-case letter followed by the dot,
   a split is never made (to not split names like "A. Dent").

The decision for requiring an "syntactically correct" terminal sequence with upper-case letters or
numbers as start symbol is based on the preference to under-split rather than over-split sentences.

Special care is taken not to split at common abbreviations "i.e.", "etc.",
to not split at first or middle name initials "... F. M. Last ...",
and to avoid single letters or digits as sentences ("A. This sentence...").

Sentence splits will always be enforced at either single or double line-breaks.
"""
import os
from regex import compile, DOTALL, VERBOSE, UNICODE

try:
    from otplc.tokenizer import LINEBREAK, SENTENCE_TERMINALS
except ImportError:
    # to use this on the command line
    from tokenizer import LINEBREAK, SENTENCE_TERMINALS

# Use upper-case for abbreviations that are all capitals without intervening dots.
# Lower-case abbreviations may occur capitalized or not.
# Repeat-dot abbrevations (like Dr.med.univ. or i.e.) are auto-detected.
ABBREVIATIONS = u"""AB abbrev AC acad AD al alt AM approx apr asap assn assoc aug ave
BA BC BRA BS btw capt cent co col comdr corp cpl DC dec dept DF dist div dr ed est et etc
feb fl fig figs gal gen gov grad hon hr inc inst jan jr jun jul lat lb lib long lt ltd
mag mar med MD min mr mrs ms msgr mt mts mus nat nov nr oct op oz pl pop PRC prof pseud pt pub
rer rev sep sept ser sgt sr sra st univ US USA USSR vol vs wt""".split()
ABBREVIATIONS.extend(a.capitalize() for a in ABBREVIATIONS if a[0].islower())
ABBREVIATIONS = u'|'.join(sorted(ABBREVIATIONS))
ABBREVIATIONS = compile(ur'.*?(?:\b(?:%s)|\w+\.\w+)$' % ABBREVIATIONS, UNICODE)

LB_PATTERN = compile(LINEBREAK, UNICODE)

NAME_ABBREV = compile(ur'^.*?\b[A-Z][A-z]?$', UNICODE)  # including two-letter abbreviations
# Last name or single-letter middle name abbreviation; Aj. B. McArthur
LAST_NAME = compile(ur'^(?:(?:[A-Z][a-z]+){1,2}|[A-Z]$)', UNICODE)

SEGMENTER_REGEX = (
    ur'('   # A sentence ends at one of two sequences:
    ur'[%s]'   # Either, a sequence starting with a sentence terminal,
    ur'[\'\u2019\"\u201D]?'   # an optional left quote,
    ur'[\]\)]?'   # an optional closing bracket and
    ur'\s+'   # required spaces,
    ur'(?='   # iff this potential terminating sequence is followed
    ur'[\[\(]?'   # by an optional opening bracket,
    ur'[\'\u2018\"\u201C]?'   # an optional right quote and
    ur'[\p{{Lt}}\p{{Lu}}\p{{Nd}}\p{{Nl}}]'   # a required Unicode upper-case letter or number.
    ur')'
    u'|[\r\n\u2028]{}'  # Otherwise, a sentence also terminates at [consecutive?] newlines.
    ur')'
) % (SENTENCE_TERMINALS)#, LINEBREAK)
"""
Require a sentence terminal, followed by spaces and an upper-case letter or number.

Optionally, a right bracket and/or quote may succeed the terminal
and a left bracket and/or quote may precede the alphanumeric.

Alternatively, an yet undefined number of line-breaks also may terminate sentences.
"""

# Define that one or more line-breaks split sentences:
DO_NOT_CROSS_LINES = compile(SEGMENTER_REGEX.format(u'+'), DOTALL | VERBOSE | UNICODE)
"A pattern where any newline (CR, NL/LF, or LS) terminates a sentence."
# Define that two or more line-breaks split sentences:
MAY_CROSS_ONE_LINE = compile(SEGMENTER_REGEX.format(u'{2,}'), DOTALL | VERBOSE | UNICODE)
"A pattern where two or more successive newlines (CR, NL/LF, or LS) terminate sentences."


def regex_segmenter(text):
    """
    Split sentences that never cross lines.

    :param text: input plain-text
    :return: a sentence generator with inner linebreaks replaced with spaces
    """
    return _sentences(DO_NOT_CROSS_LINES.split(text))


def multiline_segmenter(text):
    """
    Split sentences that may cross newlines, except consecutive ones.

    :param text: input plain-text
    :return: a sentence generator with inner linebreaks replaced with spaces
    """
    return _sentences(MAY_CROSS_ONE_LINE.split(text))


def single_segmenter(text):
    """
    Split at newlines (``\n''), but only return lines with content.

    :param text: input plain-text
    :return: a "sentence" generator (lines with [stripped] content)
    """
    for line in text.split(u'\n'):
        line = line.strip()

        if line:
            yield line


def rewrite_newlines(text, pattern):
    """
    Remove newlines (CR, LF/NL, LS) inside sentences and ensure there is a ``\\n`` at their end.

    :param text: input plain-text
    :param pattern: for the initial sentence splitting
    :return: a generator yielding the spans from the text
    """
    spaces_only = _clean_newlines(text)
    offset = 0

    for sentence in _sentences(pattern.split(text)):
        start = spaces_only.index(sentence, offset)
        intervening = text[offset:start]

        if offset != 0 and u'\n' not in intervening:
            intervening = '\n' + intervening[1:]

        yield intervening
        yield sentence
        offset = start + len(sentence)

    if offset < len(text):
        yield text[offset:]


def _sentences(spans):
    "Generic segmentation function."
    terminal = None
    segment = None
    i = -2
    lookAhead = lambda: spans[i + 1] if len(spans) > i + 1 else u''
    isAbbrev = lambda: (terminal[0] == u'.' and
                        (ABBREVIATIONS.match(segment) or
                         (NAME_ABBREV.match(segment) and LAST_NAME.match(lookAhead()))))
    isSingleAlnum = lambda: len(segment) == 1 and segment.isalnum()

    for i, terminal in enumerate(spans):
        if i and i % 2:  # i: even => segment, uneven => (potential) terminal
            if segment and not (isAbbrev() or isSingleAlnum()):
                yield u'%s%s' % (segment, terminal.rstrip())
                segment = None
            else:
                segment += _clean_newlines(terminal)
        else:
            if segment is None:
                segment = _clean_newlines(terminal).lstrip()
            else:
                segment += _clean_newlines(terminal)

    if segment:
        segment = segment.rstrip()

        if segment:
            yield segment


def _clean_newlines(text):
    return text.replace(u'\n', u' ').replace(u'\r', u' ').replace(u'\u2028', u' ')


def _sentence_boundaries(text, pattern):
    for match in pattern.finditer(text):
        yield match.span()



if __name__ == '__main__':
    # print one sentence per line
    from sys import argv, stdout

    for txt_file_path in argv[1:]:
        text = open(txt_file_path, 'rt').read().decode('UTF-8')

        for span in rewrite_newlines(text, MAY_CROSS_ONE_LINE):
            stdout.write(span.encode('utf-8'))
