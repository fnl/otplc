"""
A helper module for capturing and unit-testing log events.
"""
from functools import partial
from logging.handlers import BufferingHandler
from functools import reduce


__author__ = 'Florian Leitner <florian.leitner@gmail.com>'


def filterIf(val, pos, msgs):
    if val is not None:
        return filter(lambda m: m[pos] == val, msgs)
    else:
        return msgs


def reverseApply(msgs, fun):
    return fun(msgs)


class LoggingTestHandler(BufferingHandler):

    def __init__(self, test_case):
        super(LoggingTestHandler, self).__init__(0)
        self.test = test_case

    def shouldFlush(self, record):
        return False

    def emit(self, record):
        self.buffer.append(record.__dict__)

    def assertMatches(self, msg, args=None, levelname=None, lineno=None, count=1):
        """ Look for `count` log entries matching the supplied arguments. """
        if len(self.buffer) == 0 and count != 0:
            self.test.fail(u'empty log buffer')

        messages = [(m['levelname'], m['lineno'], m['msg'], m['args']) for m in self.buffer]
        filters = [
            partial(filterIf, levelname, 0),
            partial(filterIf, lineno, 1),
            partial(filterIf, msg, 2),
            partial(filterIf, args, 3),
        ]
        matches = list(reduce(reverseApply, filters, messages))

        if len(matches) != count:
            if len(matches) == 0:
                target = '%s @ %s: "%s" %% %s' % (str(levelname), str(lineno), msg, repr(args))
                self.test.fail(u'no matches for:\n%s\nfound in:\n%s' % (
                    target,
                    '\n'.join(u'%s @ %d: "%s" %% %s' % m for m in messages)
                ))
            else:
                self.test.fail(u'counted %s, but expected %s matches' % (len(matches), count))
