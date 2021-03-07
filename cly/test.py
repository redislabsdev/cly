# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

import unittest
import doctest
from cly import Grammar, Parser


class TestXMLGrammar(unittest.TestCase):
    """Test XML grammar parser."""
    def setUp(self):
        self._output = None

    def _echo(self, **kwargs):
        self._output = kwargs

    def test_basic(self):
        xml = """<?xml version="1.0"?>
        <grammar>
            <node name='echo'>
                <variable name='text'>
                    <action callback='echo'/>
                </variable>
            </node>
        </grammar>
        """

        grammar = Grammar.from_xml(xml, echo=self._echo)
        parser = Parser(grammar)
        parser.execute('echo magic')
        self.assertEqual(self._output, {'text': 'magic'})

    def test_integer_types(self):
        xml = """<?xml version="1.0"?>
        <grammar>
            <node name='echo'>
                <variable name='text' traversals='0'>
                    <alias target='/echo/*'/>
                    <action callback='echo'/>
                </variable>
            </node>
        </grammar>
        """

        grammar = Grammar.from_xml(xml, echo=self._echo)
        parser = Parser(grammar)
        parser.execute('echo magic monkey')
        self.assertEqual(self._output, {'text': ['magic', 'monkey']})

    def test_group(self):
        xml = """<?xml version="1.0"?>
        <grammar>
            <node name='echo'>
                <group traversals='0'>
                    <variable name='text'>
                        <alias target='../../*'/>
                        <action callback='echo'/>
                    </variable>
                </group>
            </node>
        </grammar>
        """

        grammar = Grammar.from_xml(xml, echo=self._echo)
        parser = Parser(grammar)
        parser.execute('echo magic monkey')
        self.assertEqual(self._output, {'text': ['magic', 'monkey']})

    def test_completion(self):
        xml = """<?xml version="1.0"?>
        <grammar>
            <node name='echo'>
                <variable name='text' candidates='candidates'>
                    <action callback='echo'/>
                </variable>
            </node>
        </grammar>
        """

        def candidates(context, text):
            return ['monkey', 'muppet']

        grammar = Grammar.from_xml(xml, echo=self._echo, candidates=candidates)
        parser = Parser(grammar)
        context = parser.parse('echo ')
        self.assertEqual(list(context.candidates()), ['monkey', 'muppet'])

    def test_node_extension(self):
        from cly.builder import Variable


        class ABC(Variable):
            pattern = r'(?i)[abc]+'


        xml = """<?xml version="1.0"?>
        <grammar>
            <node name='echo'>
                <abc name='text'>
                    <action callback='echo'/>
                </abc>
            </node>
        </grammar>
        """

        grammar = Grammar.from_xml(xml, extra_nodes=[ABC], echo=self._echo)
        parser = Parser(grammar)
        parser.execute('echo abaabbccc')
        self.assertEqual(self._output, {'text': 'abaabbccc'})


def suite():
    import cly
    import cly.interactive
    import cly.console
    import cly.extra
    import cly.parser
    import cly.builder
    import cly.exceptions

    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestXMLGrammar, 'test'))
    suite.addTest(doctest.DocTestSuite(cly))
    suite.addTest(doctest.DocTestSuite(cly.interactive))
    suite.addTest(doctest.DocTestSuite(cly.console))
    suite.addTest(doctest.DocTestSuite(cly.extra))
    suite.addTest(doctest.DocTestSuite(cly.parser))
    suite.addTest(doctest.DocTestSuite(cly.builder))
    suite.addTest(doctest.DocTestSuite(cly.exceptions))

    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
