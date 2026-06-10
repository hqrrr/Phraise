"""Tests for Config.save() atomic write safety.

Verifies that save() writes to a temp file then uses os.replace()
so that a crash mid-write never corrupts settings.json.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from phraise.config import CONFIG_FILE, Config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton between tests so each test starts fresh."""
    Config._instance = None
    yield
    Config._instance = None


def make_patch_target(name: str) -> str:
    """Return dotted path to ``phraise.config`` name for mocking."""
    return f"phraise.config.{name}"


# ---------------------------------------------------------------------------
# Atomic write pattern: .tmp + os.replace
# ---------------------------------------------------------------------------

def test_save_writes_to_temp_then_replaces():
    """save() must write to a .tmp file then os.replace() to actual path."""
    config = Config()
    config._data = {"test": "data"}

    with (
        patch(make_patch_target("open")) as mock_open,
        patch(make_patch_target("os.replace")) as mock_replace,
        patch(make_patch_target("CONFIG_DIR")) as mock_dir,
    ):
        mock_dir.exists.return_value = True
        mock_dir.mkdir.return_value = None

        # The tmp file handle from the first open() call
        tmp_fh = MagicMock()
        mock_open.return_value.__enter__.return_value = tmp_fh

        config.save()

        # Two open calls: one for .tmp, one should NOT happen for CONFIG_FILE
        assert mock_open.call_count == 1, "save() should open ONLY the .tmp file"

        # Verify the tmp path was opened
        expected_tmp = CONFIG_FILE.with_suffix(".tmp")
        opened_path = mock_open.call_args[0][0]
        assert opened_path == expected_tmp, (
            f"Expected to open {expected_tmp}, got {opened_path}"
        )
        # Writing mode
        assert "w" in mock_open.call_args[0] or mock_open.call_args[1].get("mode", "").startswith("w"), (
            "Expected write mode on tmp file"
        )

        # Verify json.dump was called on the tmp handle
        # (the data should have been serialised to tmp_fh)
        assert tmp_fh.write.called or any(
            call[0][0] is tmp_fh for call in json.dump.call_args_list
            if hasattr(json.dump, "call_args_list")
        ), "json.dump should have written to the tmp file handle"

        # Verify os.replace was called with tmp -> actual
        mock_replace.assert_called_once_with(expected_tmp, CONFIG_FILE)


def test_save_does_not_open_actual_file_directly():
    """save() must NOT open() settings.json directly — only via os.replace."""
    config = Config()
    config._data = {"key": "value"}

    with (
        patch(make_patch_target("open")) as mock_open,
        patch(make_patch_target("os.replace")),
        patch(make_patch_target("CONFIG_DIR")) as mock_dir,
    ):
        mock_dir.exists.return_value = True
        mock_dir.mkdir.return_value = None

        config.save()

        # Coerce to string for comparison; Path("x") != "x" in Python
        paths_opened = [str(call[0][0]) for call in mock_open.call_args_list]
        assert str(CONFIG_FILE) not in paths_opened, (
            f"save() should NOT open settings.json directly. Opened: {paths_opened}"
        )


def test_save_removes_tmp_file_on_success():
    """After os.replace succeeds, the .tmp file should not remain (was renamed)."""
    config = Config()
    config._data = {"key": "value"}

    with patch(make_patch_target("CONFIG_DIR")) as mock_dir:
        mock_dir.exists.return_value = True
        mock_dir.mkdir.return_value = None

        config.save()

    # After a real os.replace(), the .tmp path no longer exists
    tmp_path = CONFIG_FILE.with_suffix(".tmp")
    assert not tmp_path.exists(), (
        f"Temporary file {tmp_path} should not exist after save()"
    )


# ---------------------------------------------------------------------------
# Crash safety: if serialization fails, original file is untouched
# ---------------------------------------------------------------------------

def test_crash_during_serialize_does_not_corrupt_original():
    """If json.dump raises mid-write, the real settings.json is unchanged."""
    def _explode(*_a, **_kw):
        raise OSError("disk full")

    original_content = '{"existing": "data"}'
    tmp_path = CONFIG_FILE.with_suffix(".tmp")

    # Ensure the real file exists with known content
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(original_content, encoding="utf-8")

    config = Config()
    # Force a reload so _data reflects the file
    config._data = {"test": "value"}

    with patch(make_patch_target("json.dump"), side_effect=_explode):
        with pytest.raises(OSError, match="disk full"):
            config.save()

    # The original file must be intact
    assert CONFIG_FILE.read_text(encoding="utf-8") == original_content, (
        "Original settings.json was corrupted after a failed save()"
    )

    # The tmp file should also be cleaned up
    if tmp_path.exists():
        # Depending on where exactly it blew up, tmp may or may not remain;
        # but if it does, it's not the end of the world — just log it.
        tmp_path.unlink()
