"""``villanelle.files``: the filesystem document source (S2-04's rules, as TypeScript's ``createFileSource``)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import villanelle as vl
from villanelle.files import file_source


def test_resolve_joins_a_spec_to_the_parents_directory_and_a_missing_file_is_no_path(tmp_path: Path) -> None:
    (tmp_path / "a.conf").write_text("a;\n")
    parent = vl.LoadContext(str(tmp_path / "main.conf"))
    assert file_source().resolve("a.conf", parent) == [str(tmp_path / "a.conf")]
    assert file_source().resolve("missing.conf", parent) == []
    assert file_source().resolve(".", parent) == []


def test_a_glob_lists_the_matching_files_and_a_missing_directory_is_no_path(tmp_path: Path) -> None:
    (tmp_path / "d").mkdir()
    for name in ["b.conf", "a.conf", "x.txt"]:
        (tmp_path / "d" / name).write_text("")
    (tmp_path / "d" / "sub.conf").mkdir()
    parent = vl.LoadContext(str(tmp_path / "main.conf"))
    found = file_source().resolve("d/*.conf", parent)
    assert sorted(found) == [str(tmp_path / "d" / "a.conf"), str(tmp_path / "d" / "b.conf")]
    assert file_source().resolve("nope/*.conf", parent) == []


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions and a non-root user")
def test_a_permission_error_raises_so_the_load_reports_e3004_not_e3001(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "a.conf").write_text("")
    locked.chmod(0)
    try:
        with pytest.raises(PermissionError):
            file_source().resolve("locked/a.conf", vl.LoadContext(str(tmp_path / "main.conf")))
    finally:
        locked.chmod(0o755)
