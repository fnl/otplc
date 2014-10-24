# coding=utf-8
from unittest import TestCase
from otplc.segmenter import split_single, split_multi, MAY_CROSS_ONE_LINE, \
    split_newline, rewrite_line_separators


OSPL = u"""One sentence per line.
And another sentence on the same line.
(How about a sentence in parenthesis?)
Or a sentence with "a quote!"
'How about those pesky single quotes?'
[And not to forget about square brackets.]
And, brackets before the terminal [2].
You know Mr. Abbreviation I told you so.
What about the med. staff here?
But the undef. abbreviation not.
And this f.e. is tricky stuff.
I.e. a little easier here.
However, e.g., should be really easy.
This one btw., is clear.
What the heck??!?!
Let's meet at 14.10 in N.Y..
12 monkeys ran into here.
In the Big City.
How we got an A.
An abbreviation at the end..
This is a sentence terminal ellipsis...
This is another sentence terminal ellipsis....
An easy to handle G. species mention.
This quote "He said it." is actually inside.
A. The first assumption.
B. The second bullet.
C. The last case.
1. This is one.
2. And that is two.
3. Finally, three, too.
Always last, clear closing example."""

SENTENCES = OSPL.split('\n')
TEXT = u' '.join(SENTENCES)

class TestSentenceSegmenter(TestCase):

    def setUp(self):
        self.maxDiff = None

    def test_simple_case(self):
        self.assertEqual([u'This is a test.'], list(split_single(u"This is a test.")))

    def test_regex(self):
        self.assertSequenceEqual(SENTENCES, list(split_single(TEXT)))

    def test_names(self):
        sentences = [u"Written by A. McArthur, K. Elvin, and D. Eden.",
                     u"This is Mr. A. Starr.",
                     u"B. Boyden is over there."]
        self.assertSequenceEqual(sentences, list(split_single(u' '.join(sentences))))

    def test_IRL_examples(self):
        sentences = [u"This is figure A, B, and C.",
                     u"Their (R. S. Kauffman, R. Ahmed, and B. N. Fields) paper they show..."]
        self.assertSequenceEqual(sentences, list(split_single(u' '.join(sentences))))

    def test_multiline(self):
        text = u"This is a\nmultiline sentence. And this is Mr.\nAbbrevation."
        ml_sentences = [u"This is a multiline sentence.", u"And this is Mr. Abbrevation."]
        self.assertSequenceEqual(ml_sentences, list(split_multi(text)))

    def test_linebreak(self):
        text = u"This is a\nmultiline sentence."
        rx_sentences = text.split('\n')
        self.assertSequenceEqual(rx_sentences, list(split_single(text)))

    def test_newline(self):
        self.assertSequenceEqual(SENTENCES, list(split_newline(OSPL)))

    def test_rewrite(self):
        # noinspection PyTypeChecker
        a_text = OSPL.replace(u'\n', u'\u2028').replace(u' ', u'\n')
        result = rewrite_line_separators(a_text, MAY_CROSS_ONE_LINE)
        self.assertSequenceEqual(OSPL, u''.join(result))