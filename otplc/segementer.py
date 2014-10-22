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

Special care is taken not to split at common abbreviations like "i.e." or "etc.",
to not split at first or middle name initials "... F. M. Last ...",
to not split before a comma, colon, or semi-colon,
and to avoid single letters or digits as sentences ("A. This sentence...").

Sentence splits will always be enforced at [consecutive] line separators.

*Important*: Windows uses ``\\r\\n`` as line split; use consecutive splits for single line splits
and the special windows function for multi-line splits.
"""
from regex import compile, DOTALL, VERBOSE, UNICODE


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'

SENTENCE_TERMINALS = u'.!?\u203C\u203D\u2047\u2047\u2049\u3002' \
                     u'\uFE52\uFE57\uFF01\uFF0E\uFF1F\uFF61'
"""The list of valid Unicode sentence terminal characters."""

# Use upper-case for abbreviations that always are capitalized:
# Lower-case abbreviations may occur capitalized or not.
# Abbreviations with intervening dots (like U.S.A., Dr.med.univ., or i.e.) are auto-detected.
ABBREVIATIONS = u"""AB abbrev AC acad AD al alt AM approx apr asap asf assn assoc aug ave
BA BC BRA BS btw capt cent co col comdr corp cpl DC dec dept DF dist div dr ed est et etc
feb fl fig figs gal gen gov grad hon hr inc inst jan jr jun jul lat lb lib long lt ltd
mag mar med MD min mr mrs ms msgr mt mts mus nat nov nr oct op oz pl pop PRC prof pseud pt pub
rer rev sep sept ser sgt sr sra st univ US USA USSR vol vs wt""".split()
ABBREVIATIONS.extend(a.capitalize() for a in ABBREVIATIONS if a[0].islower())
ABBREVIATIONS = u'|'.join(sorted(ABBREVIATIONS))
ABBREVIATIONS = compile(ur'(?:\b(?:%s)|\w+\.\w+)$' % ABBREVIATIONS, UNICODE)
"A pattern to detect common abbreviations at the candidate sentence end."

NAME_ABBREV = compile(ur'\b\p{{Lu}}\p{{L}}?$', UNICODE)
"A pattern to detect one upper-case letter and an optional letter before the candidate end."
LAST_NAME = compile(ur'^(?:(?:\p{{Lu}}[\p{{Ll}}\p{{Lm}}]+){1,2}|\p{{Lu}}$)', UNICODE)
"A pattern to detect capitalized first words or single upper-case letter segments."

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

_compile = lambda cnt: compile(SEGMENTER_REGEX.format(u'{%d,}' % cnt), DOTALL | VERBOSE | UNICODE)

# Define that one or more line-breaks split sentences:
DO_NOT_CROSS_LINES = _compile(1)
"A pattern where any newline (CR, NL/LF, or LS) terminates a sentence."

# Define that two or more line-breaks split sentences:
MAY_CROSS_ONE_LINE = _compile(2)
"A pattern where two or more successive newlines (CR, NL/LF, or LS) terminate sentences."

WINDOW_LINEBREAK_X = _compile(4)
"A pattern for the Windows line-break format."


def split_single(text):
    """
    Split at sentences terminals and at line separator chars.

    :param text: input plain-text
    :return: a sentence generator with inner linebreaks replaced with spaces
    """
    return _sentences(DO_NOT_CROSS_LINES.split(text))


def split_multi(text):
    """
    Split sentences that may contain non-consecutive line separator chars.

    :param text: input plain-text
    :return: a sentence generator with inner linebreaks replaced with spaces
    """
    return _sentences(MAY_CROSS_ONE_LINE.split(text))


def split_windows(text):
    """
    Split sentences that may contain non-consecutive line separator chars.

    :param text: input plain-text with **Windows** line-break format ``\\r\\n``
    :return: a sentence generator with inner linebreaks replaced with spaces
    """
    return _sentences(WINDOW_LINEBREAK_X.split(text))

def split_newline(text):
    """
    Split the `text` at newlines (``\\n'') and strip the lines,
    but only return lines with content.

    :param text: input plain-text
    :return: a "sentence" generator (lines with [stripped] content)
    """
    for line in text.split(u'\n'):
        line = line.strip()

        if line:
            yield line


def rewrite_line_separators(text, pattern):
    """
    Remove line separator chars inside sentences and ensure there is a ``\\n`` at their end.

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
            yield '\n'
            intervening = intervening[1:]

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
                        (ABBREVIATIONS.search(segment) or
                         (NAME_ABBREV.search(segment) and LAST_NAME.match(lookAhead()))))
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

        for span in rewrite_line_separators(text, MAY_CROSS_ONE_LINE):
            stdout.write(span.encode('utf-8'))
