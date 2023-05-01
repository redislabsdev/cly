# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

"""CLY grammar and help parsers, and support classes."""


__all__ = ['HelpParser', 'Context', 'Parser']
__docformat__ = 'restructuredtext en'


from cly.exceptions import *


class HelpParser(object):
    """Extract the help for children of the specified Node.

    Help is extracted from the Node's children, following branches, and
    returned ordered by group, order and finally help key and string.
    """
    def __init__(self, context, node):
        self.help = []
        self.node = node

        def add_help(node):
            node_help = sorted(node.help(context))
            for help in node_help:
                self.help.append((node.group, node.order, help[0], help[1]))

        for child in node.children(context, follow=True):
            if child.visible(context):
                add_help(child)

        self.help.sort()

    def __iter__(self):
        """Iterate over each (key, help) help pair.

        >>> from cly.builder import Grammar, Node, Help
        >>> context = Context(None, None)
        >>> help = HelpParser(context, Grammar(one=Node('1'),
        ...     two=Node(Help.pair('<two>', '2'), group=2)))
        >>> list(help)
        [(0, 'one', '1'), (2, '<two>', '2')]
        """

        for help in self.help:
            yield (help[0],) + help[2:]

    def format(self, out):
        """Format help into a human readable form.

        >>> from cly.builder import Grammar, Node, Help
        >>> import sys
        >>> context = Context(None, None)
        >>> help = HelpParser(context, Grammar(one=Node('1'),
        ...     two=Node(Help.pair('<two>', '2'), group=2)))
        >>> help.format(sys.stdout)
          one   1
        <BLANKLINE>
          <two> 2
        """
        import cly.console as console

        if not self.help:
            return
        last_group = None
        max_len = max([len(h[2]) for h in self.help])
        if out.isatty():
            write = console.colour_cwrite
        else:
            write = console.mono_cwrite
        for group, order, command, help in self.help:
            if last_group is not None and last_group != group:
                out.write('\n')
            last_group = group
            write(out, '  ^B%-*s^B %s\n' % (max_len, command, help))


class Context(object):
    """Represents the parsing context of a single command.

    The context contains all the information the parser needs to maintain
    state while parsing the input command.
    """
    def __init__(self, parser, command, user_context=None):
        self.parser = parser
        self.command = command
        self.cursor = 0
        self.user_context = user_context
        self.vars = {}
        self._traversed = {}
        self.trail = []

    def _get_remaining_input(self):
        """Return the current remaining unparsed text in the command.

        >>> context = Context(None, 'one two')
        >>> context.advance(4)
        >>> context.remaining
        'two'
        """
        return self.command[self.cursor:]
    remaining = property(_get_remaining_input, doc=_get_remaining_input.__doc__)

    def _get_parsed(self):
        """Return command text that has been successfully parsed.
        >>> context = Context(None, 'one two')
        >>> context.advance(4)
        >>> context.parsed
        'one '
        """
        return self.command[:self.cursor]
    parsed = property(_get_parsed, doc=_get_parsed.__doc__)

    def _last_node(self):
        """Return the last node parsed.

        >>> from cly.builder import Grammar, Node
        >>> parser = Parser(Grammar(one=Node('1', two=Node('2'))))
        >>> context = parser.parse('one two three')
        >>> context.last_node
        <Node:/one/two>
        """
        if self.trail[-1][1] is None or self.trail[-1][1].group():
            return self.trail[-1][0]
        else:
            return self.trail[-2][0]
    last_node = property(_last_node, doc=_last_node.__doc__)

    def execute(self):
        """Execute the current (terminal) node. If there is still input
        remaining an exception will be thrown.

        >>> from cly.builder import Grammar, Node, Action
        >>> def test(): print 'OK'
        >>> parser = Parser(Grammar(one=Node('1')(Action('', test))))
        >>> context = parser.parse('one')
        >>> context.execute()
        OK
        """
        if self.remaining.strip():
            raise InvalidToken(self)
        node = self.trail[-1][0]
        return node.terminal(self)

    def advance(self, distance):
        """Advance cursor.

        >>> context = Context(None, 'one two')
        >>> context.cursor
        0
        >>> context.advance(4)
        >>> context.cursor
        4
        """
        self.cursor += distance

    def candidates(self, text=None):
        """Return potential candidates from children of last successfully
        parsed node.

        If text is not provided, the remaining unparsed text in the current
        command will be used.

        >>> from cly.builder import Grammar, Node
        >>> parser = Parser(Grammar(one=Node('1')(two=Node('2'),
        ...                 three=Node('3')), four=Node('4')))
        >>> context = parser.parse('one')
        >>> list(context.candidates())
        ['three ', 'two ']
        >>> list(context.candidates('th'))
        ['three ']
        """
        if text is None:
            text = self.remaining
        for child in self.last_node.children(self, follow=True):
            for candidate in child.candidates(self, text):
                yield candidate

    def help(self):
        """Return a HelpParser object describing the last successfully parsed
        node.

        >>> import sys
        >>> from cly.builder import Grammar, Node
        >>> parser = Parser(Grammar(one=Node('1')(two=Node('2'),
        ...                 three=Node('3')), four=Node('4')))
        >>> context = parser.parse('one')
        >>> help = context.help()
        >>> help.format(sys.stdout)
          three 3
          two   2
        """
        return HelpParser(self, self.last_node)

    def selected(self, node):
        """The given node has been selected and will be followed."""
        path = node.path()
        self._traversed.setdefault(path, 0)
        self._traversed[path] += 1

    def traversed(self, node):
        """How many times has node been traversed in this context?

        >>> from cly.builder import Grammar, Node, Alias
        >>> parser = Parser(Grammar(one=Node('1', traversals=0)(Alias('/one'))))
        >>> node = parser.find('/one')
        >>> for i in range(4):
        ...     context = parser.parse('one ' * i)
        ...     print context.traversed(node), context.parsed # doctest: +NORMALIZE_WHITESPACE
        0
        1 one 
        2 one one 
        3 one one one 
        """
        return self._traversed.get(node.path(), 0)

    def __repr__(self):
        return "<Context command:'%s' remaining:'%s'>" % (self.command, self.remaining)


class Parser(object):
    """Parse and execute CLY grammars."""
    def __init__(self, grammar, with_user_context=False):
        self.grammar = grammar
        self.with_user_context = with_user_context

    def _set_grammar(self, grammar):
        """Set grammar and update all nodes' ``parser`` attribute."""
        from cly.builder import Grammar
        assert isinstance(grammar, Grammar)
        self._grammar = grammar
        for node in self:
            node.parser = self

    def _get_grammar(self):
        """The grammar associated with this parser."""
        return self._grammar

    grammar = property(_get_grammar, _set_grammar)

    def __iter__(self):
        """Walk every node in the grammar.

        >>> from cly.builder import Node, Grammar
        >>> parser = Parser(Grammar(one=Node('1'), two=Node('2', three=Node('3'))))
        >>> list(parser)
        [<Grammar:/>, <Node:/two>, <Node:/two/three>, <Node:/one>]
        """
        for node in self.grammar.walk():
            yield node

    def parse(self, command, user_context=None):
        """Parse command using the current grammar.

        This will return a Context object that can be used to inspect the state
        of the parser.

        If a user_context is provided it will be passed on to any ``Action``
        node callbacks that have set ``with_context=True``.

        >>> from cly.builder import Grammar, Node, Action
        >>> parser = Parser(Grammar(one=Node('1'), two=Node('2', three=Node('3',
        ...                 action=Action('Do stuff', lambda: "foo bar")))))
        >>> context = parser.parse('two three')
        >>> context
        <Context command:'two three' remaining:''>
        >>> context.execute()
        'foo bar'
        >>> parser.parse('two four')
        <Context command:'two four' remaining:'four'>
        """
        context = Context(self, command, user_context)

        def parse(node, match):
            context.trail.append((node, match))
            if match is not None:
                node.advance(context)
            node.selected(context, match)

            for subnode in node.next(context):
                if subnode.valid(context):
                    submatch = subnode.match(context)
                    if submatch is not None:
                        return parse(subnode, submatch)
            else:
                return
            raise InvalidToken(context)

        parse(self.grammar, None)
        return context

    def execute(self, command, user_context=None):
        """Parse and execute the given command.

        >>> from cly.builder import Grammar, Node, Action
        >>> parser = Parser(Grammar(one=Node('1'), two=Node('2', three=Node('3',
        ...                 action=Action('Do stuff', lambda: "foo bar")))))
        >>> parser.execute('two three')
        'foo bar'
        """
        return self.parse(command, user_context).execute()

    def find(self, path):
        """Find a node by its absolute path.

        >>> from cly.builder import Grammar, Node, Action
        >>> parser = Parser(Grammar(one=Node('1'), two=Node('2', three=Node('3'))))
        >>> parser.find('/two/three')
        <Node:/two/three>
        """
        return self.grammar.find(path)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
