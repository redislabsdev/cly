# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

"""Useful functions for use in conjunction with CLY."""


__all__ = ['cull_candidates', 'static_candidates']
__docformat__ = 'restructuredtext en'


def cull_candidates(candidates, text):
    """Cull candidates that do not start with ``text``."""
    return [_f for _f in [c + ' ' for c in candidates if c.startswith(text)] if _f]


def static_candidates(*candidates):
    """Convenience function to provide candidates matching a prefix.

    Returns a callable that can be used directly with ``Node.candidates=``.

    >>> from cly.parser import Parser
    >>> from cly.builder import Grammar, Node
    >>> static_candidates('foo', 'bar')(None, 'f')
    ['foo ']
    >>> parser = Parser(Grammar(node=Node('Test', candidates=static_candidates('foo', 'fuzz', 'bar'))))
    >>> list(parser.parse('f').candidates())
    ['foo ', 'fuzz ']
    """
    def cull_candidates(context, text):
        return [_f for _f in [c + ' ' for c in candidates if c.startswith(text)] if _f]
    return cull_candidates


if __name__ == '__main__':
    import doctest
    doctest.testmod()
