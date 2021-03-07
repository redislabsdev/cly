# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

"""Console/terminal interaction classes and functions.

This module provides a simple formatting syntax for basic terminal visual
control sequences. The syntax is a carat ``^`` followed by a single character.

Valid formatting controls are:

``^N``
    Reset all formatting.
``^B``
    Toggle bold.
``^U``
    Toggle underline.
``^0``
    Set black foreground.
``^1``
    Set red foreground.
``^2``
    Set green foreground.
``^3``
    Set brown foreground.
``^4``
    Set blue foreground.
``^5``
    Set magenta foreground.
``^6``
    Set cyan foreground.
``^7``
    Set white foreground.

"""
from __future__ import division

from builtins import str
from builtins import map
from builtins import range
from past.utils import old_div
import re
import sys
import os
import codecs


__docformat__ = 'restructuredtext en'


_decode_re = re.compile(r'''\^([N0-7BU])|.''')
_encode_re = re.compile(r'''\033(?:[^[]|$)|\033\[(.*?)m''')
_cprint_strip = re.compile(r'''\^([N0-7BU])''')
_cwrap_re = re.compile(r'''(\n)|(\s+)|((?:\^[N0-7BU]|\S)+\b[^\n^\w]*)|(.)''')
_colour_terminal = 0


if sys.stdout.isatty():
    try:
        import curses
        curses.setupterm()
        if curses.tigetnum('colors') >= 0:
            _colour_terminal = 1
    except:
        pass

    try:
        import msvcrt
        def getch():
            """Get a single character from the terminal."""
            return msvcrt.getch()
    except ImportError:
        def getch():
            """Get a single character from the terminal."""
            import tty
            import termios

            fd = sys.stdin.fileno()
            try:
                old_settings = termios.tcgetattr(fd)
            except termios.error:
                return os.read(fd, 1)
            try:
                tty.setraw(fd)
                ch = os.read(fd, 1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch


class Codec(codecs.Codec):
    def __init__(self, *args, **kwargs):
        try:
            codecs.Codec.__init__(self, *args, **kwargs)
        except AttributeError:
            pass
        self.reset()

    _encode_mapping = {
        0: '^N', 1: '^B', 4: '^U', 22: '^B', 24: '^U', 30: '^0', 31: '^1',
        32: '^2', 33: '^3', 34: '^4', 35: '^5', 36: '^6', 37: '^7',
    }

    def _decode_match(self, match):
        c = match.group(1)
        if c:
            if c == 'B':
                self.bold = not self.bold
                if self.bold:
                    return "\033[1m"
                else:
                    return "\033[22m"
            elif c == 'U':
                self.underline = not self.underline
                if self.underline:
                    return "\033[4m"
                else:
                    return "\033[24m"
            elif c == 'N':
                self.underline = self.bold = 0
                return "\033[0m"
            elif c >= '0' and c <= '7':
                return "\033[3" + c + "m"
            else:
                return match.group(0)
        return match.group(0)

    def decode(self, input, errors='strict'):
        return _decode_re.sub(self._decode_match, input)

    def _encode_match(self, match):
        c = match.group(1)
        if c:
            return self._encode_mapping[int(c)]
        return match.group(0)

    def encode(self, input, errors='strict'):
        return _encode_re.sub(self._encode_match, input)

    def reset(self):
        self.bold = False
        self.underline = False


class CodecStreamWriter(Codec, codecs.StreamWriter):
    def __init__(self, stream, errors='strict'):
        Codec.__init__(self)
        codecs.StreamWriter.__init__(self, stream, errors)
        self.errors = errors

    def write(self, object):
        self.stream.write(self.decode(object))

    def writelines(self, lines):
        for line in lines:
            self.write(line)
            self.write('\n')


class CodecStreamReader(Codec, codecs.StreamReader):
    def __init__(self, stream, errors='strict'):
        Codec.__init__(self)
        codecs.StreamReader.__init__(self, stream, errors)

    def read(self, size=-1, chars=-1):
        raise NotImplementedError

    def readline(self, size=None, keepends=True):
        raise NotImplementedError

    def readlines(self, sizehint=None, keepends=True):
        raise NotImplementedError

    def seek(self, offset, whence=0):
        self.stream(offset, whence)
        self.reset()


def decode(input, errors='strict'):
    return (Codec(errors=errors).decode(input), len(input))


def encode(input, errors='strict'):
    return (Codec(errors=errors).encode(input), len(input))


def register_codec():
    """Register the 'console' codec with Python.

    The formatting syntax can then be used like any other codec:

    >>> register_codec()
    >>> '^Bbold^B'.decode('console')
    '\\x1b[1mbold\\x1b[22m'
    >>> '\\x1b[1mbold\\x1b[22m'.encode('console')
    '^Bbold^B'
    """
    def inner_register(encoding):
        if encoding != 'console':
            return None
        return (encode, decode, CodecStreamReader, CodecStreamWriter)
    return codecs.register(inner_register)


def colour_cwrite(io, text):
    """Decode text to ANSI escape sequences and write to the io object."""
    io.write(decode(text)[0])


def mono_cwrite(io, text):
    """Strip all colour encoding and write to io."""
    io.write(_cprint_strip.sub('', text))

if sys.stdout.isatty() and _colour_terminal:
    cwrite = colour_cwrite
else:
    cwrite = mono_cwrite

cwrite.__doc__ ="""
Print using colour escape codes similar to the Quake engine. That is,
^0-7 correspond to colours, ^B toggles bold, ^U toggles underline and
^N is reset to normal text. Colour is not automatically reset at the
end of output.

If ``sys.stdout`` is not a TTY, colour codes will be stripped.
"""


def cprint(*args):
    """Emulate the ``print`` builtin, with terminal shortcuts."""
    stream = sys.stdout
    if args and type(args[0]) is file:
        stream = args[0]
        args = args[1:]
    cwrite(stream, ' '.join(args) + '\n')


def cprintstrip(*args):
    """As with cprint, but strip colour codes."""
    return _cprint_strip.sub('', ' '.join(map(str, args)))


def clen(arg):
    """Return the length of arg after colour codes are stripped."""
    return len(cprintstrip(arg))


def cerror(*args):
    """Print a message in red to stderr."""
    cprint(sys.stderr, "^1^B" + ' '.join(map(str, args)) + '^N')


def cfatal(*args):
    """Print a message in red to stderr then exit with status -1."""
    cprint(sys.stderr, "^1^B" + ' '.join(map(str, args)) + '^N')
    sys.exit(-1)


def cwarning(*args):
    """Print a yellow warning message to stderr."""
    cprint(sys.stderr, "^3^B" + ' '.join(map(str, args)) + '^N')


def cinfo(*args):
    """Print a green notice."""
    cprint("^2" + ' '.join(map(str, args)) + '^N')


def termwidth():
    """Guess the current terminal width."""
    try:
        return curses.tigetnum('cols')
    except:
        return int(os.environ.get('COLUMNS', 80))


def termheight():
    """Guess the current terminal height."""
    try:
        return curses.tigetnum('lines')
    except:
        return int(os.environ.get('LINES', 25))


def csplice(text, start=0, end=-1):
    """Splice a colour encoded string."""
    out = ''
    if end == -1:
        end = len(text)
    sofar = 0
    for token in _decode_re.finditer(text):
        if sofar > end: break
        txt = token.group(0)
        if token.group(1):
            if start < sofar < end:
                out += txt
        else:
            # Whether beginning and end of segment are in slice
            bs = start < sofar < end
            es = start < sofar + len(txt) < end
            if bs and es:
                out += txt
            elif not bs and es:
                out += txt[start - sofar:]
            elif bs and not es:
                out += txt[:end - sofar]
                break
            elif sofar <= start and sofar + len(txt) >= end:
                out += txt[start - sofar:end]
                break
            sofar += len(txt)
    return out


def cwraptext(rtext, width=termwidth(), subsequent_indent=''):
    """Wrap multi-line text to width (defaults to termwidth())"""
    out = []
    for text in rtext.splitlines():
        tokens = [t.group(0) for t in _cwrap_re.finditer(text)] + [' ' * width]
        line = tokens.pop(0)
        first_line = 1

        def add_line(line, first_line):
            if clen(line.rstrip()) > width:
                tokens.insert(0, csplice(line, width))
                line = csplice(line, 0, width)
            out.append((not first_line and subsequent_indent or '') + line.rstrip())
            first_line = 0
            if not out[-1]:
                out.pop()
            return first_line

        if tokens:
            while tokens:
                if clen(line) + clen(tokens[0].rstrip()) > width:
                    first_line = add_line(line, first_line)
                    line = tokens.pop(0)
                else:
                    line += tokens.pop(0)
            if line:
                add_line(line, first_line)
        else:
            out.append('')
    return out


def wraptoterm(text, **kwargs):
    """Wrap the given text to the current terminal width"""
    return '\n'.join(cwraptext(text, **kwargs))


def rjustify(text, width=termwidth()):
    """Right justify the given text."""
    text = cwraptext(text, width)
    out = ''
    for line in text:
        out += (' ' * (width - clen(line))) + line + '\n'
    return out.rstrip()


def cjustify(text, width=termwidth()):
    """Centre the given text."""
    text = cwraptext(text, width)
    out = ''
    for line in text:
        out += (' ' * (old_div((width - clen(line)), 2))) + line + '\n'
    return out.rstrip()


def print_table(header, table, sep=' ', indent='',
                auto_format=('^B^U', '^6', '^B^6'), expand_to_fit=True, min_widths=None):
    """Print a list of lists as a table, so that columns line up nicely.

    ``header``: list of column headings
        Will be printed as the first row.

    ``table``: list of rows
        Data to print.

    ``sep=' '``: string
        The column separator.

    ``indent=''``: string
        Table indentation as a string.

    ``auto_format=('^B^U', '^6', '^B^2')``: tuple
        A tuple specifying the formatting colours to use for each row. The
        first element is the header colour, subsequent elements are for
        alternating rows.

    ``expand_to_fit=True``: boolean or integer
        If a boolean, signifies whether print_table should expand the table to
        the width of the terminal or compact it as much as possible. If an
        integer, specifies the width to expand to.

    ``min_widths``: list of minimum column widths
        Columns will be guaranteed to be at least the width of each element
        in the list.

    Note: ``print_table`` supports the ``^R`` formatting code, in addition to
    those supported by cprint, which corresponds to the colour formatting of
    the current table row."""
    def ctlen(s):
        return clen(s.replace('^R', ''))

    seplen = len(sep)
    # Find column scale factor
    if header:
        table.insert(0, header)

    # Stringify entire table
    table = [[str(c) for c in r] for r in table]

    # Make sure min_widths is usable
    min_widths = min_widths or []
    for i in range(len(min_widths),len(table[0])):
        min_widths.append(0)

    rows, cols = len(table), len(table[0])
    colwidths = [0] * cols
    for i in range(0, cols):
        colwidths[i] = max([max([0] + list(map(ctlen, c[i].splitlines()))) for c in table])
        colwidths[i] = max(colwidths[i], min_widths[i])
        if i < cols - 1:
            colwidths[i] += seplen

    # Scale columns if total width is less than the terminal width, or user
    # requested
    if expand_to_fit in (None, True, False):
        max_width = termwidth() - len(indent)
    else:
        max_width = expand_to_fit
        expand_to_fit = True

    # Make sure min_widths is sensible
    if sum(min_widths) > max_width:
        raise Exception('Table exceeds maximum width')

    # Scale columns out to max_width
    if expand_to_fit is True or max_width < sum(colwidths):
        scale = float(max_width - 1 - sum(min_widths)) / float(sum(colwidths) - sum(min_widths))
        colwidths = [max(int(float(colwidths[x]) * scale), min_widths[x]) for x in range(0, len(colwidths))]
        mincol = min(colwidths)
        # Pad smallest column out so total width is size of max_width
        colwidths[colwidths.index(mincol)] += max_width - sum(colwidths)

    auto_format = list(auto_format)

    rowalt = -1

    if not header:
        auto_format = auto_format[1:]
        rowalt = 0

    for row in table:
        fmt = ''
        if rowalt == -1:
            fmt = auto_format[0]
            auto_format.pop(0)
        else:
            fmt = auto_format[rowalt % len(auto_format)]
        # Perform wrapping
        xrow = [cwraptext(col.replace('^R', fmt),
                          colwidths[i] - (i < cols - 1 and seplen or 0))
                for i, col in enumerate(row)]
        # Pad column rows out to the maximum of all columns
        maxrows = max([0] + list(map(len, xrow)))
        for col in xrow:
            col += [''] * (maxrows - len(col))
        realrows = max([0] + list(map(len, xrow)))
        # Emit
        for i in range(0, realrows):
            cwrite(sys.stdout, indent + fmt)
            for j, col in enumerate(xrow):
                slen = j < cols - 1 and seplen or 0
                cwrite(sys.stdout, col[i] + ' ' * (colwidths[j] - ctlen(col[i]) - slen))
                if slen:
                    cwrite(sys.stdout, sep)
            cwrite(sys.stdout, '^N\n')
        rowalt += 1


if __name__ == '__main__':
    import doctest
    doctest.testmod()
