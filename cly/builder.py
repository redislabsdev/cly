# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#


"""Classes for constructing CLY grammars."""


import re
import os
import posixpath
from xml.dom import minidom
from inspect import isclass
from cly.exceptions import *


__all__ = ['Node', 'Alias', 'Group', 'Action', 'Variable', 'Grammar', 'Help',
           'LazyHelp', 'Word', 'String', 'URI', 'LDAPDN', 'Integer', 'Float', 'IP',
           'Hostname', 'Host', 'EMail', 'File', 'Boolean']
__docformat__ = 'restructuredtext en'


class Node(object):
    """The base class for all grammar nodes.

    Constructor arguments are:

    ``help``: string or callable returning a list of (key, help) tuples
        A help string or a callable returning an iterable of (key, help)
        pairs. There is a useful class called Help which can be used for
        this purpose.

    ``name=None``: string
        The name of the node. If ommitted the key used by the parent Node
        is used. The node name also defines the node path:

        >>> Node('Something', name='something')
        <Node:/something>

    The following constructor arguments are also class variables, and as
    such can be overridden at the class level by subclasses of Node. Useful If
    you find yourself using a particular pattern repeatedly.

    ``pattern=None``: regular expression string
        The regular expression used to match user input. If not provided,
        the node name is used:

        >>> a = Node('Something', name='something')
        >>> a.pattern == a.name
        True

    ``separator=r'\s+|\s*$'``: regular expression string
        A regular expression used to match the text separating this node
        and the next.

    ``group=0``: integer
        Nodes can be grouped together to provide visual cues. Groups are
        ordered ascending numerically.

    ``order=0``: integer
        Within a group, nodes are normally ordered alphabetically. This can
        be overridden by setting this to a value other than 0.

    ``match_candidates=False``: boolean
        The candidates() method returns a list of words that match at the
        current token, which are then used for completion, but can also be
        used to constrain the allowed matches if match_candidates=True.
        Useful for situations where you have a general regex pattern (eg. a
        pattern matching files) but a known set of matches at this point (eg.
        files in the current directory).

    ``traversals=1``: integer
        The number of times this node can match in any parse context. Alias
        nodes allow for multiple traversal.

        If ``traversals=0`` the node will match an infinite number of times.
    """
    pattern = None
    separator = r'\s+|\s*$'
    order = 0
    group = 0
    match_candidates = False
    traversals = 1

    def __init__(self, help='', *args, **kwargs):
        self._children = {}
        if isinstance(help, basestring):
            self.help = LazyHelp(self, help)
        elif callable(help):
            self.help = help
        else:
            raise InvalidHelp('help must be a callable or a string')
        if 'pattern' in kwargs:
            self.pattern = kwargs.pop('pattern')
        if 'separator' in kwargs:
            self.separator = kwargs.pop('separator')
        if self.pattern is not None:
            self._pattern = re.compile(self.pattern)
        self._separator = re.compile(self.separator)
        if self.pattern is not None and self.separator is not None:
            self._full_match = re.compile('(?:%s)(?:%s)' %
                                          (self.pattern, self.separator))
        self.name = kwargs.pop('name', None)
        self.parent = None
        self.__anonymous_children = 0
        self(*args, **kwargs)

    def _set_name(self, name):
        """Set the name of this node. If the Node does not have an existing
        matching pattern associated with it, a pattern will be created using
        the name."""
        self._name = name
        if isinstance(name, basestring) and self.pattern is None:
            self.pattern = name
            self._pattern = re.compile(name)
        if self.pattern is not None and self.separator is not None:
            self._full_match = re.compile('(?:%s)(?:%s)' %
                                          (self.pattern, self.separator))
    name = property(lambda self: self._name, _set_name)

    def __call__(self, *anonymous, **options):
        """Update or add options and child nodes.

        Positional arguments are treated as anonymous child nodes, while
        keyword arguments can either be named child nodes or attribute updates
        for this node. See __init__ for more information on attributes.

        As a special case, if a positional argument is a `Grammar` object, its
        *children* will be merged.

        >>> top = Node('Top', name='top')
        >>> top(subnode=Node('Subnode'))
        <Node:/top>
        >>> top.find('subnode')
        <Node:/top/subnode>
        """
        for node in anonymous:
            if isinstance(node, Grammar):
                children = dict([(n.name, n) for n in node])
                self(**children)
                continue
            if not isinstance(node, Node):
                raise InvalidAnonymousNode('Anonymous node is not a Node object')
            # TODO Convert help to name instead of __anonymous_<n>
            node.name = '__anonymous_%i' % self.__anonymous_children
            node.parent = self
            self._children[node.name] = node
            self.__anonymous_children += 1

        for k, v in options.iteritems():
            if isinstance(v, Node):
                if k.endswith('_'):
                    k = k[:-1]
                v.name = k
                v.parent = self
                self._children[k] = v
            else:
                setattr(self, k, v)
        return self

    def __iter__(self):
        """Iterate over child nodes, ignoring context.

        >>> tree = Node('One')(two=Node('Two'), three=Node('Three'))
        >>> list(tree)
        [<Node:/three>, <Node:/two>]
        """
        children = sorted(self._children.values(),
                          key=lambda i: (i.group, i.order, i.name))
        for child in children:
            yield child

    def __setitem__(self, key, child):
        """Emulate dictionary set.

        >>> node = Node('One')
        >>> node['two'] = Node('Two')
        >>> list(node.walk())
        [<Node:/>, <Node:/two>]
        """
        self(**{key: child})

    def __getitem__(self, key):
        """Emulate dictionary get.

        >>> node = Node('One')(two=Node('Two'))
        >>> node['two']
        <Node:/two>
        """
        return self._children[key]

    def __delitem__(self, key):
        """Emulate dictionary delete.

        >>> node = Node('One')(two=Node('Two'), three=Node('Three'))
        >>> list(node.walk())
        [<Node:/>, <Node:/three>, <Node:/two>]
        >>> del node['two']
        >>> list(node.walk())
        [<Node:/>, <Node:/three>]
        """
        child = self._children.pop(key)
        child.parent = None

    def __contains__(self, key):
        """Emulate dictionary key existence test.

        >>> node = Node('One')(two=Node('Two'), three=Node('Three'))
        >>> 'two' in node
        True
        """
        return key in self._children

    def walk(self, predicate=None):
        """Perform a recursive walk of the grammar tree.

        >>> tree = Node('One')(two=Node('Two', three=Node('Three'),
        ...                             four=Node('Four')))
        >>> list(tree.walk())
        [<Node:/>, <Node:/two>, <Node:/two/four>, <Node:/two/three>]
        """
        if predicate is None:
            predicate = lambda node: True

        def walk(root):
            if not predicate(root):
                return
            yield root
            for node in root._children.itervalues():
                for subnode in walk(node):
                    yield subnode

        for node in walk(self):
            yield node

    def children(self, context, follow=False):
        """Iterate over child nodes, optionally follow()ing branches.

        >>> from cly.parser import Context
        >>> tree = Node('One')(two=Node('Two', three=Node('Three'),
        ...                             four=Node('Four')), five=Alias('../two/*'))
        >>> context = Context(None, None)
        >>> list(tree.children(context))
        [<Alias:/five for /two/*>, <Node:/two>]
        >>> list(tree.children(context, follow=True))
        [<Node:/two/four>, <Node:/two/three>, <Node:/two>]
        """
        for child in self:
            if child.valid(context):
                if follow:
                    for branch in child.follow(context):
                        if branch.valid(context):
                            yield branch
                else:
                    yield child

    def follow(self, context):
        """Return alternative Nodes to traverse.

        The children() method calls this method when follow=True to expand
        aliased nodes, although it could be used for other purposes."""
        yield self

    def selected(self, context, match):
        """This node was selected by the parser.

        By default, informs the context that the node has been traversed."""
        context.selected(self)

    def next(self, context):
        """Return an iterable over the set of next candidate nodes."""
        for child in self.children(context, follow=True):
            yield child

    def match(self, context):
        """Does this node match the current token?

        Must return a regex match object or None for no match. If
        ``match_candidates`` is true the token must also match one of the values
        returned by ``candidates()``.

        Must include separator in determining whether a match was
        successful."""
        if not self.valid(context):
            return None
        match = self._pattern.match(context.command, context.cursor)
        if match:
            # Check that separator matches as well
            if not self._separator.match(context.command, context.cursor +
                                         len(match.group())):
                return None
            if self.match_candidates and match.group() + ' ' not in \
                    self.candidates(context, match.group()):
                return None
            return match

    def advance(self, context):
        """Advance context cursor based on this nodes match."""
        match = self._full_match.match(context.command, context.cursor)
        context.advance(len(match.group()))

    def visible(self, context):
        """Should this node be visible?"""
        return True

    def terminal(self, context):
        """This node was selected as a terminal."""
        raise UnexpectedEOL(context)

    def depth(self):
        """The depth of this node in the grammar.

        >>> grammar = Grammar(one=Node('One'), two=Node('Two'))
        >>> grammar.depth()
        0
        >>> grammar.find('two').depth()
        1
        """
        return self.parent and self.parent.depth() + 1 or 0

    def path(self):
        """The full grammar path to this node. Path components are separated
        by a forward slash.

        >>> grammar = Grammar(one=Node('One'), two=Node('Two'))
        >>> grammar.find('two').path()
        '/two'
        """
        names = []
        node = self
        while node is not None:
            if node.name is not None:
                names.insert(0, node.name)
            node = node.parent
        return '/' + '/'.join(names)

    def candidates(self, context, text):
        """Return an iterable of completion candidates for the given text. The
        default is to use the content of self.help().

        >>> grammar = Grammar(one=Node('One'), two=Node('Two'))
        >>> list(grammar.find('one').candidates(None, 'o'))
        ['one ']
        >>> list(grammar.find('one').candidates(None, 't'))
        []
        """
        for key, help in self.help(context):
            if key[0] != '<' and key.startswith(text):
                yield key + ' '

    def find(self, path):
        """Find a Node by path rooted at this node.

        >>> top = Node('Top', name='top', one=Node('One'), two=Node('Two',
        ...            three=Node('Three')))
        >>> top.find('/two/three')
        <Node:/top/two/three>
        >>> top.find('/one/bar')
        Traceback (most recent call last):
        ...
        InvalidNodePath: /top/one/bar
        """
        components = filter(None, path.split('/'))
        if not components:
            return self
        for child in self:
            if child.name == components[0]:
                return child.find('/'.join(components[1:]))
        raise InvalidNodePath(posixpath.join(self.path(), path.strip('/')))

    def valid(self, context):
        """Is this node valid in the given context?"""
        # Node is invalid if traversed more than self.traversals times
        return not self.traversals or \
            context.traversed(self) < self.traversals

    def _get_anonymous(self):
        """Is this node anonymous?"""
        return self.name.startswith('__anonymous_')

    anonymous = property(_get_anonymous, doc=_get_anonymous.__doc__)

    def __repr__(self):
        return '<%s:%s>' % (self.__class__.__name__, self.path() or '<root>')


class Group(Node):
    """Apply settings to all ancestor nodes.

    Terminates application of settings on any deeper Group node.

    Before applying settings:

    >>> top = Node('Top')(one=Node('One'),
    ...                   two=Node('Two', three=Node('Three')))
    >>> [node.traversals for node in top.walk()]
    [1, 1, 1, 1]

    And after applying settings:

    >>> apply = Group(traversals=0)(top)
    >>> [node.traversals for node in top.walk()]
    [0, 0, 0, 0]
    """
    pattern = ''

    def __init__(self, **apply):
        self._apply = apply
        Node.__init__(self, object.__repr__(self))

    def __call__(self, *args, **kwargs):
        result = Node.__call__(self, *args, **kwargs)

        def stop_on_ancestors(node):
            return node is self or not isinstance(node, Group)

        for child in self.walk(predicate=stop_on_ancestors):
            if child is self:
                Node.__call__(self, **self._apply)
            else:
                child(**self._apply)

        return result

    def valid(self, context):
        return True

    def follow(self, context):
        for child in self:
            yield child


class Alias(Node):
    """An alias for another node, or set of nodes.

    An Alias overrides the ``follow()`` method to return aliased Nodes. Globs
    are supported.

    Constructor arguments:

    ``alias``: relative or absolute grammar path
        Path to the aliased node. If the alias contains glob characters (``*``
        or ``?``) all matching nodes are aliased.

    >>> from cly.parser import Parser, Context
    >>> parser = Parser(Grammar(one=Node('One'), two=Node('Two',
    ...                 three=Node('Three')), four=Alias('../one'), five=Node('Five', six=Alias('../../*'))))
    >>> alias = parser.find('/four')
    >>> alias
    <Alias:/four for /one>
    >>> context = Context(None, None)
    >>> list(alias.follow(context))
    [<Node:/one>]
    >>> alias = parser.find('/five/six')
    >>> alias
    <Alias:/five/six for /*>
    >>> list(alias.follow(context))
    [<Node:/five>, <Node:/one>, <Node:/one>, <Node:/two>]
    """

    pattern = ''

    def __init__(self, target, *args, **kwargs):
        Node.__init__(self, '<alias for "%s">' % target,
                      *args, **kwargs)
        self._target = target

    def valid(self, context):
        for node in self.follow(context):
            if node.valid(context):
                return True
        return False

    def visible(self, context):
        for node in self.follow(context):
            if node.visible(context):
                return True
        return False

    def selected(self, context, match):
        """This node was selected by the parser."""
        raise Error('Alias nodes should never be selected')

    def follow(self, context):
        """Return an iterable of all aliased nodes."""
        root = self
        while root.parent:
            root = root.parent
        try:
            yield root.find(self.target)
        except InvalidNodePath:
            from fnmatch import fnmatch
            start = root.find(posixpath.dirname(self.target))
            match = posixpath.basename(self.target)
            for child in start.children(context, True):
                if fnmatch(child.name, match):
                    yield child

    def _get_target(self):
        """Absolute path to the aliased node."""
        return posixpath.normpath(posixpath.join(self.path(), self._target))

    target = property(_get_target)

    def __repr__(self):
        return '<%s:%s for %s>' % (self.__class__.__name__, self.path(),
                                   self.target)


class Action(Node):
    """Action node, matches EOL. The ``callback`` arg will be used as the
    callable. If ``with_user_context`` is true, the user_context object provided to
    the ``Parser`` will be passed as the first argument.

    >>> from cly.parser import Parser, Context
    >>> def write_text():
    ...     print "some text"
    >>> grammar = Grammar(action=Action("Write some text", write_text))
    >>> parser = Parser(grammar)
    >>> context = Context(parser, 'foo bar')
    >>> node = grammar.find('action')
    >>> node.help(None)
    (('<eol>', 'Write some text'),)
    >>> list(node.help(None))
    [('<eol>', 'Write some text')]
    >>> node.terminal(context)
    some text
    """
    pattern = '$'
    group = 9999
    with_user_context = None

    def __init__(self, help='', callback=None, *args, **kwargs):
        if isinstance(help, basestring):
            help_string = help
            help = lambda ctx: (('<eol>', help_string),)
        Node.__init__(self, help, callback=callback, *args, **kwargs)

    def help(self, context):
        """Return help for this action.

        >>> Action('Test', None).help(None)
        (('<eol>', 'Test'),)
        """
        if not self.visible(context):
            return
        if isinstance(self.doc, basestring):
            yield ('<eol>', self.doc)
        else:
            yield self.doc

    def terminal(self, context):
        if self.with_user_context or \
                (self.with_user_context is None and
                 self.parser.with_user_context):
            return self.callback(context.user_context, **context.vars)
        else:
            return self.callback(**context.vars)

    def callback(self, *args, **kwargs):
        raise UnexpectedEOL(None)

    def selected(self, context, match):
        # We don't "traverse" Action nodes, because they are always terminal,
        # and if we do they get excluded from help.
        pass


class Variable(Node):
    """Parse and record the users input in the vars member of the context.

    The node name is used as the variable name unless var_name is provided to
    the constructor.

    If ``traversals != 1`` the variable will accumulate values into a list.
    """

    pattern = r'\w+'

    def __init__(self, *args, **kwargs):
        self._var_name = kwargs.pop('var_name', None)
        Node.__init__(self, *args, **kwargs)

    def _set_var_name(self, value):
        self._var_name = value

    def _get_var_name(self):
        """Get the var name for this variable. Will use ``var_name`` if
        provided to the constructor, otherwise it will use the node name."""
        if self._var_name is not None:
            return self._var_name
        return self.name

    var_name = property(_get_var_name, _set_var_name)

    def valid(self, context):
        if self.traversals != 1 or \
                (self.traversals == 1 and self.name not in context.vars) or \
                len(context.vars.get(self.name, [])) < self.traversals:
            return Node.valid(self, context)
        return False

    def selected(self, context, match):
        """Convert the match to a value with self.parse(), then add
        the result to the context "vars" member.

        Raises ValidationError if the variable raises InvalidMatch.

        >>> from cly.parser import Context
        >>> c = Context(None, 'foo bar')
        >>> v = Variable('Test', name='var')
        >>> v.selected(c, re.match(r'\w+', 'test'))
        >>> c.vars['var']
        'test'
        """
        try:
            value = self.parse(context, match)
        except ValidationError, e:
            raise ValidationError(context, token=match.group(),
                                  exception=unicode(e))
        if not self.traversals or self.traversals > 1:
            context.vars.setdefault(self.var_name, []).append(value)
        else:
            context.vars[self.var_name] = value
        return Node.selected(self, context, match)

    def parse(self, context, match):
        """Parse the match and return a value. Value can be of any type: tuple,
        list, object, etc.

        Must throw a ValidationError if the input is invalid. Alternate
        variables should override this method.

        >>> v = Variable('Test')
        >>> v.parse(None, re.match(r'\w+', 'test'))
        'test'
        """
        return match.group()


class Grammar(Node):
    """The root node for a grammar."""
    def __init__(self, *args, **kwargs):
        Node.__init__(self, '<root>', pattern='', *args, **kwargs)

    def terminal(self, context):
        """Null-op for empty lines."""

    def from_xml(cls, xml, extra_nodes=None, **locals):
        """Build a CLY Grammar from XML.

        ``xml``: string
            XML source
        ``extra_nodes``: dictionary
            Dictionary of Node subclasses.
        ``locals``:
            Valid locals() when evaluating XML grammar node attributes.

        Returns a new Grammar object.
        """
        try:
            dom = minidom.parseString(xml)
        except Exception, e:
            raise XMLParseError(str(e))

        extra_nodes = extra_nodes or []

        def boolean(v):
            return v in ('True', 'true')

        def evaluate(v):
            return eval(v, globals(), locals)

        arg_types = {
            'traversals': int,
            'group': int,
            'order': int,
            'match_candidates': boolean,
        }

        arg_types.update(dict.fromkeys(
            'children follow selected next match advance visible ' \
            'terminal depth path candidates find valid callback'.split(),
            evaluate
            ))

        node_types = dict([(v.__name__.lower(), v)
                          for v in (globals().values() + extra_nodes)
                          if isclass(v) and issubclass(v, Node)])

        def parse(parent, xnode):
            if not xnode:
                return

            if xnode.nodeType == minidom.Node.ELEMENT_NODE:
                cls = node_types.get(xnode.localName.lower())
                if not cls:
                    raise XMLParseError('Invalid node type "%s"' % name)

                attributes = dict([(str(k), v) for k, v
                                   in xnode.attributes.items()])

                for k, v in attributes.items():
                    if k.startswith('eval:'):
                        attributes.pop(k)
                        k = k[5:]
                        v = evaluate(v)
                    else:
                        v = arg_types.get(k, str)(v)
                    attributes[k] = v

                name = attributes.pop('name', None)
                node = cls(**attributes)
                if name:
                    path = parent.path() + '/' + name
                    parent(**{str(name): node})
                else:
                    parent(node)
            else:
                node = parent

            parse(node, xnode.firstChild)
            parse(parent, xnode.nextSibling)

        grammar = Grammar()
        if dom.firstChild.localName != 'grammar':
            raise XMLParseError('Invalid root element "%s", expected "grammar"'
                                % dom.firstChild.localName)
        parse(grammar, dom.firstChild.firstChild)
        return grammar

    from_xml = classmethod(from_xml)


class Help(object):
    """A callable object representing help for a Node.

    Returns an iterable of pairs in the form (key, help).

    Constructor arguments

    ``doc``:
        An iterable of two element tuples in the form ``(key, help)``.

        >>> h = Help([('a', 'b'), ('b', 'c')])
        >>> [i for i in h(None)]
        [('a', 'b'), ('b', 'c')]
    """
    def __init__(self, doc):
        self.doc = doc

    def __call__(self, context):
        """Returns an iterable of two element tuples in the form (key, help)."""
        for n, h in self.doc:
            yield (n, h)

    @staticmethod
    def pair(name, help):
        """Create a Help object from a single (name, help) pair.

        >>> h = Help.pair('a', 'b')
        >>> [i for i in h(None)]
        [('a', 'b')]
        """
        return Help([(name, help)])


class LazyHelp(Help):
    """Extract help key from a node.

    Used internally by Node when a string is provided as help.

    If the Node does not have a custom pattern, the help will be in the form
    (name, text), otherwise it will be in the form (<name>, text).
    """
    def __init__(self, node, text):
        self.node = node
        self.text = text

    def __call__(self, context):
        """Extract help key from node.

        >>> node = Node('Test', name='test')
        >>> help = LazyHelp(node, 'Moo')
        >>> [i for i in help(None)]
        [('test', 'Moo')]
        """
        if self.node.name == self.node.pattern:
            yield (self.node.name, self.text)
        else:
            yield ('<%s>' % self.node.name, self.text)


class Word(Variable):
    """Matches a Pythonesque variable name.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Word('Foo')))
    >>> parser.parse('a123').vars['foo']
    'a123'
    >>> parser.parse('123').remaining
    '123'
    """
    pattern = r'(?i)[A-Z_]\w+'


class String(Variable):
    """Matches either a bare word or a quoted string.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=String('Foo')))
    >>> parser.parse('"foo bar"').vars['foo']
    'foo bar'
    >>> parser.parse('foo_bar').vars['foo']
    'foo_bar'
    """
    pattern = r"""(\w+)|"([^"\\]*(?:\\.[^"\\]*)*)"|'([^'\\]*(?:\\.[^'\\]*)*)'"""

    def parse(self, context, match):
        return match.group(match.lastindex).decode('string_escape')



class URI(Variable):
    """Matches a URI. Result is a string.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=URI('Foo')))
    >>> parser.parse('http://www.example.com/test/;test?a=10&b=10#fragment').vars['foo']
    'http://www.example.com/test/;test?a=10&b=10#fragment'
    """
    pattern = r"""(([a-zA-Z][0-9a-zA-Z+\\-\\.]*:)?/{0,2}[0-9a-zA-Z;/?:@&=+$\\.\\-_!~*'()%]+)(#[0-9a-zA-Z;/?:@&=+$\\.\\-_!~*'()%]+)?"""

    def __init__(self, doc, scheme='', allow_fragments=1, *argl, **argd):
        Variable.__init__(self, doc, *argl, **argd)
        self.scheme = scheme
        self.allow_fragments = allow_fragments

    #def parse(self, context, match):
        #import urlparse
        #return urlparse.urlparse(match.string[match.start():match.end()], self.scheme, self.allow_fragments)


class LDAPDN(Variable):
    """Matches an LDAP DN.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=LDAPDN('Foo')))
    >>> parser.parse('cn=Manager,dc=example,dc=com').vars['foo']
    'cn=Manager,dc=example,dc=com'
    """
    pattern = r'(\w+=\w+)(?:,(\w+=\w+))*'


class Integer(Variable):
    """Matches an integer.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Integer('Foo')))
    >>> parser.parse('12345').vars['foo']
    12345
    >>> parser.parse('123.45').remaining
    '123.45'
    """
    pattern = r'\d+'

    def parse(self, context, match):
        return int(match.group())


class Boolean(Variable):
    """Matches a boolean.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Boolean('Foo')))
    >>> parser.parse('true').vars['foo']
    True
    >>> parser.parse('no').vars['foo']
    False
    """
    TRUE = 'true yes aye enable enabled on 1'.split()
    FALSE = 'false no disable disabled off 0'.split()

    pattern = r'(?i)(%s)' % '|'.join(TRUE + FALSE)

    def parse(self, context, match):
        boolean = match.group()
        return boolean in self.TRUE


class Float(Variable):
    """Matches a floating point number.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Float('Foo')))
    >>> parser.parse('12345.34').vars['foo']
    12345.34
    >>> parser.parse('123.45e10').vars['foo']
    1234500000000.0
    """
    pattern = r'[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?'

    def parse(self, context, match):
        return float(match.group())


class IP(Variable):
    """Match an IP address, parsing it as a tuple of four integers.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=IP('Foo')))
    >>> parser.parse('123.34.67.89').vars['foo']
    (123, 34, 67, 89)
    >>> parser.parse('123.34.67.256').remaining
    '123.34.67.256'
    """
    pattern = r'(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'

    def parse(self, context, match):
        return tuple(map(int, match.groups()))


class Hostname(Variable):
    """Match a hostname and parse it as a tuple of components.

    Note: This will match hostnames consisting only of numbers, including but
    not limited to IP addresses.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Hostname('Foo')))
    >>> parser.parse('www.example.com').vars['foo']
    ('www', 'example', 'com')
    """
    pattern = r'(?i)([A-Z0-9][A-Z0-9_-]*)(?:\.([A-Z0-9][A-Z0-9_-]*))*'

    def parse(self, context, match):
        return tuple(match.group().split('.'))


class Host(Variable):
    """Match either an IP address or a hostname and return a tuple.

    If an IP address is matched, the elements of the tuple will be integers.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Host('Foo')))
    >>> parser.parse('www.example.com').vars['foo']
    ('www', 'example', 'com')
    >>> parser.parse('123.34.67.89').vars['foo']
    (123, 34, 67, 89)
    """

    pattern = r'(?i)(%s)|(%s)' % (IP.pattern, Hostname.pattern)

    def parse(self, context, match):
        components = match.string[match.start():match.end()].split('.')
        if match.lastindex == 1:
            return tuple(map(int, components))
        return tuple(components)


class EMail(Variable):
    """Match an E-Mail address.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=EMail('Foo')))
    >>> parser.parse('foo@bar.com').vars['foo']
    'foo@bar.com'
    """
    pattern = r'(?i)[A-Z0-9._%-]+@[A-Z0-9.-]+\.[A-Z]{2,4}'


class File(Variable):
    """Match and provide completion candidates for local files.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=File('Foo', allow_directories=True)))
    >>> parser.parse('.').vars['foo']
    '.'
    """
    pattern = r'\S+'
    includes = ['*']
    excludes = []
    allow_dotfiles = False
    allow_directories = False

    def match(self, context):
        match = Variable.match(self, context)
        if match and self.match_file(match.group(), self.allow_directories):
            return match

    def match_file(self, file, match_directories=True):
        from fnmatch import fnmatch
        file = os.path.expanduser(file)
        if match_directories and os.path.isdir(file):
            return True
        if not self.allow_dotfiles and os.path.basename(file).startswith('.'):
            return False
        for exclude in self.excludes:
            if fnmatch(file, exclude):
                return False
        for include in self.includes:
            if fnmatch(file, include):
                return True
        return False

    def candidates(self, context, text):
        """Return list of valid file candidates."""

        if text.startswith('~'):
            if '/' in text:
                short_home = text[:text.index('/')]
            else:
                short_home = text
            expanded_home = os.path.expanduser(short_home)
            text = os.path.expanduser(text)
        else:
            short_home = None

        text = os.path.expanduser(text)
        dir = os.path.dirname(text) or os.path.curdir
        file = os.path.basename(text)
        cwd = os.path.curdir + os.path.sep

        def clean(file):
            if file.startswith(cwd):
                return file[len(cwd):]
            if short_home and file.startswith(expanded_home):
                return short_home + file[len(expanded_home):]
            return file

        def get_candidates(dir, file):
            return [f for f in os.listdir(dir) if f.startswith(file)
                    and self.match_file(os.path.join(dir, f))]

        candidates = get_candidates(dir, file)
        if len(candidates) == 1:
            if os.path.isdir(os.path.join(dir, candidates[0])):
                dir = os.path.join(dir, candidates[0] + '/')
                return [dir]
                file = ''
                candidates = get_candidates(dir, file)
            else:
                return [clean(os.path.join(dir, candidates[0] + ' '))]
        return [clean(os.path.join(dir, f))
                for f in candidates if self.allow_dotfiles or f[0] != '.']


if __name__ == '__main__':
    import doctest
    doctest.testmod()
