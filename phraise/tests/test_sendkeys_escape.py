# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for sendkeys escape.
"""Tests for SendKeys special character escaping.

Verifies that _escape_sendkeys() properly escapes all SendKeys
special characters: {}()+-^%~ so that literal text like "C++ is 50% done"
is not interpreted as keystroke modifiers.
"""

from phraise.text_grabber import TextGrabber


class TestSendKeysEscape:
    def setup_method(self):
        self.escape = TextGrabber._escape_sendkeys

    def test_no_special_chars(self):
        """Plain text is unchanged."""
        assert self.escape("hello world") == "hello world"
        assert self.escape("abc123") == "abc123"
        assert self.escape("") == ""

    def test_plus_sign(self):
        """+ is escaped as {+}."""
        assert self.escape("C++") == "C{+}{+}"
        assert self.escape("a+b") == "a{+}b"

    def test_percent_sign(self):
        """% is escaped as {%}."""
        assert self.escape("50% done") == "50{%} done"
        assert self.escape("%path%") == "{%}path{%}"

    def test_caret(self):
        """^ is escaped as {^}."""
        assert self.escape("x^2") == "x{^}2"
        assert self.escape("^^") == "{^}{^}"

    def test_tilde(self):
        """~ is escaped as {~}."""
        assert self.escape("hello~world") == "hello{~}world"

    def test_parens(self):
        """() are escaped as { ( } and { ) }."""
        assert self.escape("(test)") == "{(}test{)}"
        assert self.escape("foo(bar)baz") == "foo{(}bar{)}baz"

    def test_curly_braces(self):
        """{} are escaped as {{} and {}}."""
        assert self.escape("{hello}") == "{{}hello{}}"
        # {{}} → each { → {{}, each } → {}}
        # Sequence: {{} + {{} + {}} + {}} = {{}{{}{}}{}}
        assert self.escape("{{}}") == "{{}{{}{}}{}}"
        # Verify round-trip decode logic:
        # {{} → {, {{} → {, {}} → }, {}} → } = {{}}
        assert self.escape("}{") == "{}}{{}"

    def test_real_world_c_plus_plus(self):
        """'C++ is 50% done' is fully escaped.

        Without escaping, SendKeys would interpret + as Shift modifier
        and % as Alt modifier, producing corrupted output like "C is 50 done".
        """
        result = self.escape("C++ is 50% done")
        assert result == "C{+}{+} is 50{%} done"

    def test_all_special_chars(self):
        """All special chars in one string are each escaped."""
        result = self.escape("{}+^%~()")
        assert result == "{{}{}}{+}{^}{%}{~}{(}{)}"

    def test_no_false_positives(self):
        """Characters that just happen to contain special patterns are fine."""
        assert self.escape("normal text") == "normal text"
        assert self.escape("underscore_not_special") == "underscore_not_special"
