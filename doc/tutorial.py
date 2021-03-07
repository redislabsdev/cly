import os
import sys
from cly import *
from cly.interactive import Interact

def do_quit():
    sys.exit(0)

def do_cat(files):
    for file in files:
        print open(os.path.expanduser(file)).read()

grammar = Grammar(
    # Quit is distinct from normal commands, so lets reflect that with a visual
    # cue.
    # Those are just a few of the features of CLY. Check the tutorial for more
    # and the API documentation for detail. Enjoy :)
    quit=Node('Quit', group=9999)(
        Action('Quit', do_quit),
    ),
    cat=Node('Concatenate files')(
        # This matches a file any number of times...
        # Note how the example matched any file. If we add the following...
        # Next, we'll restrict the number of files to 2...
        files=File('File to concatenate', traversals=2, includes=['*.py'])(
            Action('Concatenate files', do_cat),
            # This jumps back to the parent (files) node
            Alias('..'),
            # Now let's see it in action...
        ),
    ),
)

interact = Interact(grammar)
interact.loop()
