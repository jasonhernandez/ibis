"""Unit tests for MemtableManager, specifically volume path generation."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from ibis.backends.databricks import MemtableManager


def _make_manager(catalog="my_catalog", schema="my_schema"):
    backend = MagicMock()
    backend.current_catalog = catalog
    backend.current_database = schema
    return MemtableManager(backend, volume_path=None)


@pytest.mark.parametrize(
    ("username", "expected_prefix"),
    [
        # plain username — no change
        ("alice", "alice"),
        # period-separated name (the bug reported in ibis-project/ibis#11950)
        ("first.last", "first_last"),
        # multiple periods
        ("john.doe.smith", "john_doe_smith"),
        # other special characters should also be replaced
        ("user@domain", "user_domain"),
        ("user name", "user_name"),
        # hyphens and underscores are valid and must be preserved
        ("my-user_name", "my-user_name"),
    ],
)
def test_generate_volume_path_sanitizes_username(username, expected_prefix):
    manager = _make_manager()
    short_version = "".join(map(str, sys.version_info[:3]))
    with patch("getpass.getuser", return_value=username):
        path = manager._generate_volume_path()

    # Path must start with the /Volumes/ prefix
    assert path.startswith("/Volumes/my_catalog/my_schema/")

    # The volume name part must use the sanitized username
    volume_name = path.split("/")[-1]
    assert volume_name.startswith(expected_prefix + "-py=")

    # The path must not contain a raw period from the username
    # (periods in the Python-version string like "3.12" do not appear because
    # we join only major/minor/micro digits, but be explicit here)
    username_portion = volume_name.split("-py=")[0]
    assert "." not in username_portion, (
        f"Sanitized username portion '{username_portion}' still contains a period"
    )


def test_generate_volume_path_structure():
    """The generated path has the correct /Volumes/catalog/schema/name structure."""
    manager = _make_manager(catalog="prod_catalog", schema="prod_schema")
    with patch("getpass.getuser", return_value="alice"):
        path = manager._generate_volume_path()

    parts = path.split("/")
    # ['', 'Volumes', 'prod_catalog', 'prod_schema', '<volume_name>']
    assert parts[0] == ""
    assert parts[1] == "Volumes"
    assert parts[2] == "prod_catalog"
    assert parts[3] == "prod_schema"
    assert len(parts) == 5
