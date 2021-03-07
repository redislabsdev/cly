# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

"""CLY is a Python module for simplifying the creation of interactive shells.
Kind of like the builtin ``cmd`` module on steroids.

It has the following features:

  - Tab completion of all commands.

  - Contextual help.

  - Extensible grammar - you can define your own commands with full dynamic
    completion, contextual help, and so on.

  - Simple. Grammars are constructed from objects using a convenient
    ''function-call'' syntax.

  - Flexible command grouping and ordering.

  - Grammar parser, including completion and help enumeration, can be used
    independently of the readline-based shell. This allows CLY's parser to
    be used in other environments (think "web-based shell" ;))

  - Lots of other cool stuff.
"""


__docformat__ = 'restructuredtext en'
__author__ = 'Alec Thomas <alec@swapoff.org>'
try:
    __version__ = __import__('pkg_resources').get_distribution('cly').version
except ImportError:
    pass


from cly.parser import *
from cly.builder import *
from cly.interactive import *
