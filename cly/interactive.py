# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

"""CLY and readline, together at last.

This module uses readline's line editing and tab completion along with CLY's
grammar parser to provide an interactive command line environment.

It includes support for application specific history files, dynamic prompt,
customisable completion key, interactive help and more.

Press ``?`` at any location to contextual help.
"""

import os
import sys
import readline
import cly.rlext
import cly.console as console
from cly.exceptions import Error, ParseError
from cly.builder import Grammar
from cly.parser import Parser


__all__ = ['Interact', 'interact']
__docformat__ = 'restructuredtext en'


class Interact(object):
    """CLY interaction through readline. Due to readline limitations, only one
    Interact object can be active within an application.

    Constructor arguments:

    ``parser``: ``Parser`` or ``Grammar`` object
        The parser/grammar to use for interaction.

    ``application='cly'``: string
        The application name. Used to construct the history file name and
        prompt, if not provided.

    ``prompt=None``: string
        The prompt.

    ``user_context=None``: `anything`
        A user-specified object to pass to the parser. The parser builds each
        parse ``Context`` with this object, which in turn will deliver this
        object on to terminal nodes that have set ``with_context=True``.

    ``with_context=False``: `boolean`
        Force ``user_context`` to be passed to all action nodes, unless they
        explicitly set the member variable ``with_context=False``.

    ``history_file=None``: `string`
        Defaults to ``~/.<application>_history``.

    ``history_length=500``: `integer`
        Lines of history to keep.

    ``completion_key='tab'``: `string`
        Key to use for completion, per the readline documentation.

    ``completion_delimiters=' \t'``: `string`
        Characters that terminate completion.

    ``help_key='?'``: `key`
        Key to use for tab completion.

    """
    _cli_inject_text = ''
    _completion_candidates = []
    _parser = None
    prompt = None
    user_context = None
    history_file = None
    application = None

    def __init__(self, grammar_or_parser, application='cly', prompt=None,
                 user_context=None, with_context=None, history_file=None,
                 history_length=500, completion_key='tab',
                 completion_delimiters=' \t',
                 help_key='?', inhibit_exceptions=False,
                 with_backtrace=False):
        if prompt is None:
            prompt = application + '> '
        if history_file is None:
            history_file = os.path.expanduser('~/.%s_history' % application)
        if isinstance(grammar_or_parser, Grammar):
            parser = Parser(grammar_or_parser)
        else:
            parser = grammar_or_parser

        if with_context is not None:
            parser.with_context = with_context
        if user_context is not None:
            parser.user_context = user_context
        Interact._parser = parser
        Interact.prompt = prompt
        Interact.application = application
        Interact.user_context = user_context
        Interact.history_file = history_file
        Interact.history_length = history_length
        Interact.completion_delimiters = completion_delimiters
        Interact.completion_key = completion_key

        try:
            readline.set_history_length(history_length)
            readline.read_history_file(history_file)
        except:
            pass

        readline.parse_and_bind("%s: complete" % completion_key)
        readline.set_completer_delims(self.completion_delimiters)
        readline.set_completer(Interact._cli_completion)
        readline.set_startup_hook(Interact._cli_injector)

        # Use custom readline extensions
        cly.rlext.bind_key(ord(help_key), Interact._cli_help)


    def once(self, default_text='', callback=None):
        """Input one command from the user and return the result of the
        executed command. `callback` is called with the Interact object before
        each line is displayed."""
        Interact._cli_inject_text = default_text

        while True:
            command = ''
            try:
                command = raw_input(self.prompt)
            except KeyboardInterrupt:
                print
                continue
            except EOFError:
                print
                return None

            try:
                context = Interact._parser.parse(command, user_context=self.user_context)
                context.execute()
            except ParseError, e:
                self.print_error(context, e)
            return context

    def loop(self, inhibit_exceptions=False, with_backtrace=False):
        """Repeatedly read and execute commands from the user.

        Arguments:

        ``inhibit_exceptions=True``: `boolean`
            Normally, ``interact_loop`` will pass exceptions back to the caller for
            handling. Setting this to ``True`` will cause an error message to
            be printed, but interaction will continue.

        ``with_backtrace=False``: `boolean`
            Whether to print a full backtrace when ``inhibit_exceptions=True``.
        """
        try:
            while True:
                try:
                    if not self.once():
                        break
                except Exception, e:
                    if inhibit_exceptions:
                        if with_backtrace:
                            import traceback
                            console.cerror(traceback.format_exc())
                        else:
                            console.cerror('error: %s' % e)
                    else:
                        raise
        finally:
            self.write_history()

    def print_error(self, context, e):
        """Called by `once()` to print a ParseError."""
        candidates = [help[1] for help in context.help()]
        if len(candidates) > 1:
            message = '%s (candidates are %s)'
        else:
            message = '%s (expected %s)'
        message = message % (str(e), ', '.join(candidates))
        self.error_at_cursor(context, message)

    def error_at_cursor(self, context, text):
        """Attempt to intelligently print an error at the current cursor
        offset."""
        text = str(text)
        term_width = console.termwidth()
        indent = ' ' * (context.cursor % term_width
                        + len(Interact.prompt))
        if len(indent + text) > term_width:
            console.cerror(indent + '^')
            console.cerror(text)
        else:
            console.cerror(indent + '^ ' + text)

    def write_history(self):
        """ Write command line history out. """
        try:
            readline.write_history_file(self.history_file)
        except:
            pass

    @staticmethod
    def _dump_traceback(exception):
        import traceback
        from StringIO import StringIO
        out = StringIO()
        traceback.print_exc(file=out)
        print >>sys.stderr, str(exception)
        print >>sys.stderr, out.getvalue()


    @staticmethod
    def _cli_injector():
        readline.insert_text(Interact._cli_inject_text)
        Interact._cli_inject_text = ''


    @staticmethod
    def _cli_completion(text, state):
        line = readline.get_line_buffer()[0:readline.get_begidx()]
        ctx = None
        try:
            result = Interact._parser.parse(line)
            if not state:
                Interact._completion_candidates = list(result.candidates(text))
            if Interact._completion_candidates:
                return Interact._completion_candidates.pop()
            return None
        except cly.Error:
            return None
        except Exception, e:
            Interact._dump_traceback(e)
            cly.rlext.force_redisplay()
            raise


    @staticmethod
    def _cli_help(key, count):
        try:
            command = readline.get_line_buffer()[:cly.rlext.cursor()]
            context = Interact._parser.parse(command)
            if context.remaining.strip():
                print
                candidates = [help[1] for help in context.help()]
                text = '%s^ invalid token (candidates are %s)' % \
                       (' ' * (context.cursor + len(Interact.prompt)),
                        ', '.join(candidates))
                console.cerror(text)
                cly.rlext.force_redisplay()
                return
            help = context.help()
            print
            help.format(sys.stdout)
            cly.rlext.force_redisplay()
            return 0
        except Exception, e:
            Interact._dump_traceback(e)
            cly.rlext.force_redisplay()
            return 0


def interact(grammar_or_parser, inhibit_exceptions=False, with_backtrace=False,
             *args, **kwargs):
    """Start an interactive session with the given grammar or parser object."""
    interact = Interact(grammar_or_parser, *args, **kwargs)
    interact.loop(inhibit_exceptions=inhibit_exceptions,
                  with_backtrace=with_backtrace)
