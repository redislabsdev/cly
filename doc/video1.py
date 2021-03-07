from __future__ import print_function
# To demonstrate how easy it is to create interactive shells with CLY, I'm
# going to write a simple interface to BeautifulSoup.

import sys
import re
from cly.all import *
from urllib2 import urlopen
from BeautifulSoup import BeautifulSoup

# I'll start with three basic commands:
#
#  fetch <uri>
#  find tag <tag>
#  find text <regex>
#
# And there we have it. Three commands built up in a very short amount of
# time. Enjoy.

# For the purposes of this demonstration we'll use a global to store the
# current page. You could just as easily use a class member, and all callbacks
# could also be methods.
page = None

def fetch(uri):
    global page
    content = urlopen(uri).read()
    page = BeautifulSoup(content)
    # Whoops

def find_tag(tag):
    for t in page(tag):
        print(t)

def find_text(text):
    for t in page(text=re.compile(text)):
        print(t)

# First we define the grammar. Now we'll fill it out a bit more. Each Node
# defines a token in the grammar. 
#
# We've used a couple of new node types here. The first is a Variable, which
# is mapped to the arguments in the final Action callback. An Action is a
# terminal node in the syntax, and defines what function to call to perform
# the action.
grammar = Grammar(
    fetch=Node('Fetch page to interrogate')(
        # What's going on? This is due to the fact that the default pattern
        # used to match tokens is a basic word match... To override this we
        # can pass pattern=r'...' to the Variable constructor...
        # We've been a little too liberal with our pattern...Fortunately there
        # is a built in node that matches a URI: cly.types.URI
        uri=URI('URI of page')(
            Action('Fetch page', fetch)
        ),
    ),
    # Obviously we don't want the "find" command to be used if we don't have
    # a valid page... Fortunately, the 'valid()' method can be overridden to
    # achieve this:
    find=Node('Find objects in page', valid=lambda context: page)(
        tag=Node('Find tags')(
            tag=Variable('Tag to search for')(
                Action('Find tags', find_tag)
            )
        ),
        text=Node('Find text')(
            # Need to be a bit more permissive with our pattern...
            # Displaying <text> for the user is nice, but not explicit enough
            # about what the grammar actually expects, ie. a regex. We can
            # override the node help to achieve this.
            text=Variable('Text to search for', pattern=r'.+')(
                Action('Find text', find_text)
            )
        ),
    ),
)

# All non-keyword arguments passed to a node "call" are treated as anonymous
# nodes. eg. Node('Foo')(Node('Bar'), Node('Baz'))

# Next, we interact with the user. Nice, though we want to change the
# application and prompt... The application is, by default, used to build
# a prompt, if not provided, and to store the history
# (~/.<application>_history).
quickstart(grammar, application='soupsh', prompt='> ')
