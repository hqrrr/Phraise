# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for flowlayout gc.
"""Tests for FlowLayout garbage-collection safety (Task 13).

Verifies that removing ``FlowLayout.__del__`` prevents segfaults during
Python GC — Qt/PySide6 6.5+ handles layout item cleanup safely on its own.
"""

import gc
import unittest

from phraise.floating_window import FlowLayout


def _qapp():
    """Return (or create) a QApplication singleton."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestFlowLayoutGC(unittest.TestCase):
    """Verify FlowLayout does not crash during garbage collection."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _qapp()

    # ------------------------------------------------------------------
    # Core GC safety
    # ------------------------------------------------------------------

    def test_gc_after_parent_deletion_does_not_crash(self):
        """Delete parent widget containing FlowLayout + children, then GC."""
        from PySide6.QtWidgets import QLabel, QWidget

        parent = QWidget()
        layout = FlowLayout(parent)
        layout.addWidget(QLabel("A", parent))
        layout.addWidget(QLabel("BB", parent))
        layout.addWidget(QLabel("CCC", parent))
        parent.deleteLater()

        del layout, parent
        gc.collect()
        # Surviving is the assertion — no segfault

    def test_gc_without_parent_deletion_does_not_crash(self):
        """GC a FlowLayout whose parent is still alive (orphan layout)."""
        from PySide6.QtWidgets import QLabel, QWidget

        parent = QWidget()
        layout = FlowLayout(parent)
        layout.addWidget(QLabel("X", parent))
        layout.addWidget(QLabel("YY", parent))

        del layout
        gc.collect()
        # Cleanup QWidget
        del parent
        gc.collect()

    def test_many_items_gc_does_not_crash(self):
        """Stress test: many items, delete parent, trigger GC."""
        from PySide6.QtWidgets import QLabel, QWidget

        parent = QWidget()
        layout = FlowLayout(parent)
        for i in range(50):
            layout.addWidget(QLabel(f"item-{i}", parent))

        del layout, parent
        gc.collect()

    # ------------------------------------------------------------------
    # Functional regression — layout still works
    # ------------------------------------------------------------------

    def test_layout_functionality_intact(self):
        """FlowLayout count / sizeHint still work after __del__ removal."""
        from PySide6.QtWidgets import QLabel, QWidget

        parent = QWidget()
        layout = FlowLayout(parent)
        lbl = QLabel("Hello", parent)
        layout.addWidget(lbl)

        self.assertEqual(layout.count(), 1)
        sh = layout.sizeHint()
        self.assertGreater(sh.width(), 0)
        self.assertGreater(sh.height(), 0)

        # takeAt still works
        item = layout.takeAt(0)
        self.assertIsNotNone(item)
        self.assertEqual(layout.count(), 0)

        del lbl, layout, parent
        gc.collect()


if __name__ == "__main__":
    unittest.main()
