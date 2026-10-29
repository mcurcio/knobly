"""``villanelle.files``: the filesystem document source (S2-04's rules, as TypeScript's ``createFileSource``)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import villanelle as vl
from villanelle.files import file_source, fs_writer


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


def test_fs_writer_stages_every_file_then_renames_each_over_its_target(tmp_path: Path) -> None:
    a, b = tmp_path / "a.conf", tmp_path / "b.conf"
    a.write_text("a 1;\r\n", newline="")
    b.write_text("b 1;\n")
    fs_writer().write([vl.FileWrite(str(a), "a 2;\r\n", "a 1;\r\n"), vl.FileWrite(str(b), "b 2;\n", "b 1;\n")])
    assert a.read_bytes() == b"a 2;\r\n"
    assert b.read_text() == "b 2;\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.conf", "b.conf"]


def test_fs_writer_refuses_a_lost_update_writing_nothing(tmp_path: Path) -> None:
    a, b = tmp_path / "a.conf", tmp_path / "b.conf"
    a.write_text("a 1;\n")
    b.write_text("changed by someone else;\n")
    with pytest.raises(OSError, match=r"b\.conf"):
        fs_writer().write([vl.FileWrite(str(a), "a 2;\n", "a 1;\n"), vl.FileWrite(str(b), "b 2;\n", "b 1;\n")])
    assert a.read_text() == "a 1;\n"
    assert b.read_text() == "changed by someone else;\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.conf", "b.conf"]


def test_save_through_fs_writer_writes_the_changed_file_once(tmp_path: Path) -> None:
    root = tmp_path / "main.conf"
    root.write_text("x 1;\n")
    graph = vl.Processor(source=file_source()).load(str(root))
    x = graph.root.block[0]
    assert isinstance(x, vl.WrittenDirective)
    x.values[0].replace_with_text("2")
    assert graph.save(fs_writer()) == [str(root)]
    assert root.read_text() == "x 2;\n"
    assert graph.save(fs_writer()) == []


def test_fs_writer_reads_a_missing_target_as_empty_text(tmp_path: Path) -> None:
    new, gone = tmp_path / "new.conf", tmp_path / "gone.conf"
    fs_writer().write([vl.FileWrite(str(new), "a;\n", "")])
    assert new.read_text() == "a;\n"
    with pytest.raises(OSError, match=r"gone\.conf"):
        fs_writer().write([vl.FileWrite(str(gone), "b;\n", "b 1;\n")])
    assert not gone.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["new.conf"]


def test_fs_writer_replaces_nothing_and_leaves_no_temporary_when_staging_fails(tmp_path: Path) -> None:
    a = tmp_path / "a.conf"
    a.write_text("a 1;\n")
    missing = tmp_path / "no-such-directory" / "b.conf"
    with pytest.raises(FileNotFoundError):
        fs_writer().write([vl.FileWrite(str(a), "a 2;\n", "a 1;\n"), vl.FileWrite(str(missing), "b;\n", "")])
    assert a.read_text() == "a 1;\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.conf"]


def test_fs_writer_removes_the_temporaries_not_yet_renamed_when_a_rename_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = tmp_path / "a.conf", tmp_path / "b.conf"
    a.write_text("a 1;\n")
    b.write_text("b 1;\n")
    replace = os.replace
    calls: list[str] = []

    def failing_second(src: str, dst: str) -> None:
        calls.append(dst)
        if len(calls) == 2:
            raise OSError("rename failed")
        replace(src, dst)

    monkeypatch.setattr(os, "replace", failing_second)
    with pytest.raises(OSError, match="rename failed"):
        fs_writer().write([vl.FileWrite(str(a), "a 2;\n", "a 1;\n"), vl.FileWrite(str(b), "b 2;\n", "b 1;\n")])
    assert a.read_text() == "a 2;\n"
    assert b.read_text() == "b 1;\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.conf", "b.conf"]
