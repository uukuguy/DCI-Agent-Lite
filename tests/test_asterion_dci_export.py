from __future__ import annotations

import base64
import contextlib
import fcntl
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import pyarrow as pa
import pyarrow.parquet as pq

import asterion.dci.export as export_module
from asterion.dci.cli import main as cli_main
from asterion.dci.export import (
    CANARY,
    DciExportError,
    _decrypt,
    _derive_key,
    _pick_col,
    build_filename,
    export_bcplus,
    export_bcplus_qa,
    export_bright,
    main as export_main,
    parse_args as export_parse_args,
    export_subset,
    extract_title,
    get_domain,
    safe_relative_path,
    sanitize_name,
    unique_path,
)


ROOT = Path(__file__).resolve().parents[1]


def _encrypt(value: str) -> str:
    raw = value.encode("utf-8")
    key = _derive_key(CANARY, len(raw))
    return base64.b64encode(bytes(a ^ b for a, b in zip(raw, key))).decode()


def _parquet(
    path: Path, rows: list[dict[str, object]], *, row_group_size: int = 1
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path, row_group_size=row_group_size)


class AsterionDciExportTests(unittest.TestCase):
    def test_scripts_bcplus_eval_extract_bcplus_qa_py_function_derive_key(self) -> None:
        self.assertEqual(
            _derive_key("x", 65),
            hashlib.sha256(b"x").digest() * 2 + hashlib.sha256(b"x").digest()[:1],
        )

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_function_decrypt(self) -> None:
        self.assertEqual(_decrypt(_encrypt("问题")), "问题")
        for value in ("%%%", base64.b64encode(b"\xff").decode()):
            with self.assertRaises(DciExportError):
                _decrypt(value)

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_function_pick_col(self) -> None:
        self.assertEqual(_pick_col(["QID", "Question", "Target"], ["qid", "id"]), "QID")
        with self.assertRaises(DciExportError):
            _pick_col(["other"], ["qid"])

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_durable_output_output_jsonl(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "qa.jsonl"
            _parquet(
                source / "b10.parquet",
                [{"QID": "3", "Question": _encrypt("q3"), "Target": _encrypt("a3")}],
            )
            _parquet(
                source / "b2.parquet",
                [
                    {"QID": "1", "Question": _encrypt("q1"), "Target": _encrypt("a1")},
                    {"QID": "2", "Question": _encrypt("q2"), "Target": _encrypt("a2")},
                ],
                row_group_size=1,
            )
            self.assertEqual(export_bcplus_qa(source, output), 3)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual([row["query_id"] for row in rows], ["3", "1", "2"])
            before = output.stat().st_ino
            self.assertEqual(export_bcplus_qa(source, output), 3)
            self.assertEqual(output.stat().st_ino, before)

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_function_main(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "s"
            output = root / "o.jsonl"
            _parquet(
                source / "x.parquet",
                [{"id": 7, "problem": "raw", "solution": "answer"}],
            )
            self.assertEqual(
                export_main(
                    [
                        "bcplus-qa",
                        "--parquet-dir",
                        str(source),
                        "--output",
                        str(output),
                        "--no-decrypt",
                    ]
                ),
                1,
            )
            self.assertEqual(json.loads(output.read_text())["query"], "raw")

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_cli_flag_no_decrypt(self) -> None:
        self.assertIn("--no-decrypt", cli_main_help("export", "bcplus-qa"))

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_cli_flag_output(self) -> None:
        self.assertIn("--output", cli_main_help("export", "bcplus-qa"))

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_cli_flag_parquet_dir(
        self,
    ) -> None:
        self.assertIn("--parquet-dir", cli_main_help("export", "bcplus-qa"))

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_extract_title(
        self,
    ) -> None:
        self.assertEqual(extract_title("x\nTitle:  Example  \ny"), "Example")
        self.assertIsNone(extract_title("none"))

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_sanitize_name(
        self,
    ) -> None:
        self.assertEqual(sanitize_name(' a<>:"/\\|?*  b. ', "fallback"), "a b")
        self.assertEqual(sanitize_name("...", "fallback"), "fallback")
        self.assertEqual(sanitize_name("CON", "fallback"), "fallback")

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_get_domain(self) -> None:
        self.assertEqual(get_domain("https://EXAMPLE.com/a"), "example.com")
        self.assertEqual(get_domain("not a url"), "unknown-domain")

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_build_filename(
        self,
    ) -> None:
        self.assertEqual(build_filename(None, "https://x.test/a.txt", "9"), "a.txt.txt")
        self.assertLessEqual(len(Path(build_filename("x" * 300, "", "9")).stem), 140)

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_unique_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            path = root / "Name.txt"
            path.write_text("one")
            self.assertEqual(unique_path(path, "7", "one"), path)
            self.assertEqual(unique_path(path, "7", "two").name, "Name__docid_7.txt")
            (root / "Name__docid_7.txt").write_text("three")
            self.assertEqual(unique_path(path, "7", "two").name, "Name__docid_7_2.txt")

    def test_src_dci_benchmark_export_bc_plus_docs_py_durable_output_domain_title_txt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            _parquet(
                source / "part.parquet",
                [
                    {
                        "docid": "2",
                        "text": "Title: Same\nsecond",
                        "url": "https://Example.com/b",
                    },
                    {
                        "docid": "1",
                        "text": "Title: Same\nfirst",
                        "url": "https://example.com/a",
                    },
                    {
                        "docid": "3",
                        "text": "Title: SAME\nthird",
                        "url": "https://example.com/c",
                    },
                ],
            )
            self.assertEqual(export_bcplus(source, output), 3)
            names = sorted(path.name for path in (output / "example.com").glob("*.txt"))
            self.assertEqual(
                names, ["SAME__docid_3.txt", "Same.txt", "Same__docid_1.txt"]
            )
            self.assertEqual(export_bcplus(source, output), 3)

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_main(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            _parquet(
                source / "p.parquet",
                [{"docid": "1", "text": "Title: One\nbody", "url": "https://x.test/1"}],
            )
            self.assertEqual(
                export_main(
                    [
                        "bcplus",
                        "--source-dir",
                        str(source),
                        "--output-dir",
                        str(output),
                    ]
                ),
                1,
            )
            self.assertEqual(
                (output / "x.test/One.txt").read_text(), "Title: One\nbody"
            )

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_parse_args(self) -> None:
        args = export_parse_args(
            ["bcplus", "--source-dir", "source", "--output-dir", "output"]
        )
        self.assertEqual(args.export_kind, "bcplus")
        self.assertEqual(args.source_dir, Path("source"))

    def test_src_dci_benchmark_export_bc_plus_docs_py_cli_flag_output_dir(self) -> None:
        self.assertIn("--output-dir", cli_main_help("export", "bcplus"))

    def test_src_dci_benchmark_export_bc_plus_docs_py_cli_flag_source_dir(self) -> None:
        self.assertIn("--source-dir", cli_main_help("export", "bcplus"))

    def test_src_dci_benchmark_export_bright_docs_py_function_safe_relative_path(
        self,
    ) -> None:
        self.assertEqual(safe_relative_path("a/b.txt"), Path("a/b.txt"))
        for value in ("", "/a", "../a", "a/../b", "a\\b", "C:/x", "CON", "a./b"):
            with self.assertRaises(DciExportError, msg=value):
                safe_relative_path(value)

    def test_src_dci_benchmark_export_bright_docs_py_function_export_subset(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            _parquet(
                source / "p.parquet",
                [
                    {"id": "nested/a.txt", "content": "A"},
                    {"id": "nested/b.txt", "content": None},
                ],
            )
            self.assertEqual(export_subset(source, output), 2)
            self.assertEqual((output / "nested/a.txt").read_text(), "A")
            self.assertEqual((output / "nested/b.txt").read_text(), "")
            self.assertEqual((output / ".dci_export_complete").read_text(), "2\n")

    def test_src_dci_benchmark_export_bright_docs_py_durable_output_dci_export_complete(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            _parquet(
                source / "p.parquet",
                [{"id": "ok", "content": "A"}, {"id": "../bad", "content": "B"}],
            )
            with self.assertRaises(DciExportError):
                export_subset(source, output)
            self.assertFalse((output / ".dci_export_complete").exists())
            _parquet(source / "p.parquet", [{"id": "ok", "content": "A"}])
            self.assertEqual(export_subset(source, output), 1)
            self.assertTrue((output / ".dci_export_complete").is_file())

    def test_src_dci_benchmark_export_bright_docs_py_durable_output_subset_id(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            for subset in ("biology", "earth_science", "economics", "robotics"):
                _parquet(
                    source / subset / "p.parquet",
                    [{"id": f"{subset}.txt", "content": subset}],
                )
            self.assertEqual(export_bright(source, output, ("robotics",)), 1)
            self.assertFalse((output / "biology").exists())
            self.assertEqual(export_bright(source, output), 4)

    def test_src_dci_benchmark_export_bright_docs_py_function_main(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            _parquet(
                source / "biology/p.parquet",
                [{"id": "doc.txt", "content": "body"}],
            )
            self.assertEqual(
                export_main(
                    [
                        "bright",
                        "--source-root",
                        str(source),
                        "--output-root",
                        str(output),
                        "--subset",
                        "biology",
                    ]
                ),
                1,
            )
            self.assertEqual((output / "biology/doc.txt").read_text(), "body")

    def test_src_dci_benchmark_export_bright_docs_py_function_parse_args(self) -> None:
        args = export_parse_args(
            [
                "bright",
                "--source-root",
                "source",
                "--output-root",
                "output",
                "--subset",
                "robotics",
            ]
        )
        self.assertEqual(args.export_kind, "bright")
        self.assertEqual(args.subset, ["robotics"])

    def test_src_dci_benchmark_export_bright_docs_py_cli_flag_output_root(self) -> None:
        self.assertIn("--output-root", cli_main_help("export", "bright"))

    def test_src_dci_benchmark_export_bright_docs_py_cli_flag_source_root(self) -> None:
        self.assertIn("--source-root", cli_main_help("export", "bright"))

    def test_src_dci_benchmark_export_bright_docs_py_cli_flag_subset(self) -> None:
        self.assertIn("--subset", cli_main_help("export", "bright"))

    def test_exporters_reject_schema_symlink_overlap_and_portable_collisions(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            _parquet(source / "bad.parquet", [{"other": "x"}])
            with self.assertRaises(DciExportError):
                export_bcplus(source, output)
            with self.assertRaises(DciExportError):
                export_bcplus_qa(source, root / "q.jsonl")
            with self.assertRaises(DciExportError):
                export_bcplus(source, source / "nested")
            link = root / "link"
            link.symlink_to(source, target_is_directory=True)
            with self.assertRaises(DciExportError):
                export_bcplus(link, output)
            _parquet(
                source / "bad.parquet",
                [{"id": "Café", "content": "one"}, {"id": "Café", "content": "two"}],
            )
            with self.assertRaises(DciExportError):
                export_subset(source, output)

    def test_exclusive_lock_and_interrupted_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            _parquet(source / "p.parquet", [{"id": "a", "content": "A"}])
            output.mkdir()
            (output / ".asterion-dci-export.lock").write_text("held")
            self.assertEqual(export_subset(source, output), 1)
            lock = (output / ".asterion-dci-export.lock").open("a+")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(DciExportError):
                export_subset(source, output)
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
            self.assertEqual(export_subset(source, output), 1)

    def test_qa_overlap_nested_symlink_nulls_and_natural_collision_fail_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            _parquet(source / "qa.parquet", [{"id": "1", "query": "q", "answer": "a"}])
            with self.assertRaises(DciExportError):
                export_bcplus_qa(source, source / "qa.jsonl", decrypt=False)
            nested = root / "nested"
            nested.mkdir()
            (nested / "link").symlink_to(source, target_is_directory=True)
            with self.assertRaises(DciExportError):
                export_bcplus(nested / "link", output)
            _parquet(
                source / "qa.parquet",
                [{"docid": "1", "text": None, "url": "https://x"}],
            )
            with self.assertRaises(DciExportError):
                export_bcplus(source, output)
            _parquet(
                source / "qa.parquet",
                [{"id": "file02", "content": "one"}, {"id": "file2", "content": "two"}],
            )
            with self.assertRaises(DciExportError):
                export_subset(source, output)

    def test_stale_atomic_files_are_recovered_and_null_rows_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            output.mkdir()
            stale = output / (".asterion-dci-export-tmp-doc-" + "a" * 32)
            stale.write_text("partial")
            (output / ".tmp-user-work").write_text("unrelated")
            _parquet(source / "p.parquet", [{"id": "a", "content": "A"}])
            self.assertEqual(export_subset(source, output), 1)
            self.assertEqual(stale.read_text(), "partial")
            self.assertEqual((output / ".tmp-user-work").read_text(), "unrelated")
            _parquet(source / "p.parquet", [{"id": None, "content": "A"}])
            with self.assertRaises(DciExportError):
                export_subset(source, output)
            _parquet(source / "p.parquet", [{"id": "1", "query": None, "answer": "A"}])
            with self.assertRaises(DciExportError):
                export_bcplus_qa(source, root / "qa.jsonl", decrypt=False)

    def test_nested_interrupted_files_recover_and_reserved_names_fail_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            nested = output / "nested"
            nested.mkdir(parents=True)
            stale = nested / (".asterion-dci-export-tmp-doc-" + "b" * 32)
            stale.write_text("partial")
            (nested / ".tmp-user-work").write_text("unrelated")
            _parquet(
                source / "p.parquet",
                [{"id": "nested/a.txt", "content": "A"}],
            )
            self.assertEqual(export_subset(source, output), 1)
            self.assertEqual(stale.read_text(), "partial")
            self.assertEqual((nested / ".tmp-user-work").read_text(), "unrelated")
            _parquet(
                source / "p.parquet",
                [{"id": ".dci_export_complete", "content": "forged"}],
            )
            with self.assertRaises(DciExportError):
                export_subset(source, output)
            self.assertEqual((output / ".dci_export_complete").read_text(), "1\n")
            _parquet(
                source / "p.parquet",
                [{"id": "1", "query": "q", "answer": "a"}],
            )
            with self.assertRaises(DciExportError):
                export_bcplus_qa(
                    source,
                    root / ".asterion-dci-export.lock",
                    decrypt=False,
                )

    def test_reserved_portable_aliases_never_replace_lock_or_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            aliases = (
                ".ASTERION-DCI-EXPORT.LOCK",
                ".DCI_EXPORT_COMPLETE",
                ".ＡＳＴＥＲＩＯＮ-ＤＣＩ-ＥＸＰＯＲＴ.LOCK",
            )
            _parquet(source / "p.parquet", [{"id": "safe.txt", "content": "safe"}])
            self.assertEqual(export_subset(source, output), 1)
            marker = output / ".dci_export_complete"
            marker_inode = marker.stat().st_ino
            for alias in aliases:
                _parquet(source / "p.parquet", [{"id": alias, "content": "forged"}])
                with self.assertRaises(DciExportError, msg=alias):
                    export_subset(source, output)
                candidate = output / alias
                if candidate.is_file():
                    self.assertNotEqual(candidate.read_text(), "forged")
                self.assertEqual(marker.read_text(), "1\n")
                self.assertEqual(marker.stat().st_ino, marker_inode)

            nested = output / "nested"
            nested.mkdir()
            nested_alias = nested / ".DCI_EXPORT_COMPLETE"
            nested_alias.write_text("KEEP")
            _parquet(source / "p.parquet", [{"id": "safe.txt", "content": "safe"}])
            with self.assertRaises(DciExportError):
                export_subset(source, output)
            self.assertEqual(nested_alias.read_text(), "KEEP")
            self.assertEqual(marker.read_text(), "1\n")
            self.assertEqual(marker.stat().st_ino, marker_inode)

            qa_parent = root / "qa"
            qa_parent.mkdir()
            lock = qa_parent / ".asterion-dci-export.lock"
            lock.write_text("sentinel")
            lock_stream = lock.open("a+")
            fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _parquet(
                source / "p.parquet",
                [{"id": "1", "query": "q", "answer": "a"}],
            )
            for alias in (
                ".ASTERION-DCI-EXPORT.LOCK",
                ".ＡＳＴＥＲＩＯＮ-ＤＣＩ-ＥＸＰＯＲＴ.LOCK",
            ):
                with self.assertRaises(DciExportError, msg=alias):
                    export_bcplus_qa(source, qa_parent / alias, decrypt=False)
                self.assertEqual(lock.read_text(), "sentinel")
            fcntl.flock(lock_stream, fcntl.LOCK_UN)
            lock_stream.close()

    def test_bright_preflight_rejects_nonregular_control_and_temp_entries(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            outside = root / "outside"
            outside.write_text("KEEP")
            output.mkdir()
            marker = output / ".dci_export_complete"
            marker.symlink_to(outside)
            _parquet(source / "p.parquet", [{"id": "safe.txt", "content": "safe"}])
            with self.assertRaises(DciExportError):
                export_subset(source, output)
            self.assertTrue(marker.is_symlink())
            self.assertEqual(outside.read_text(), "KEEP")

            marker.unlink()
            self.assertEqual(export_subset(source, output), 1)
            marker_inode = marker.stat().st_ino
            lock = output / ".asterion-dci-export.lock"
            lock.write_text("SENTINEL")
            lock_inode = lock.stat().st_ino
            nested = output / "nested"
            nested.mkdir()
            residue = nested / (".asterion-dci-export-tmp-doc-" + "c" * 32)
            residue.mkdir()
            with self.assertRaises(DciExportError):
                export_subset(source, output)
            self.assertTrue(residue.is_dir())
            self.assertEqual(marker.read_text(), "1\n")
            self.assertEqual(marker.stat().st_ino, marker_inode)
            self.assertEqual(lock.read_text(), "SENTINEL")
            self.assertEqual(lock.stat().st_ino, lock_inode)

    def test_bright_collision_ledger_stores_fixed_content_identity(self) -> None:
        body = b"x" * (4 * 1024 * 1024)
        ledger = export_module._BrightCollisionLedger()
        ledger.add(Path("large.txt"), body)
        self.assertEqual(
            tuple(ledger.records.values()),
            (("large.txt", len(body), hashlib.sha256(body).digest()),),
        )
        self.assertFalse(
            any(isinstance(field, bytes) and len(field) == len(body) for field in next(iter(ledger.records.values())))
        )

    def test_bright_parent_portable_collisions_fail_across_reruns(self) -> None:
        pairs = (
            ("a/x.txt", "A/x.txt"),
            ("Å/x.txt", "Å/x.txt"),
            ("dir02/x.txt", "dir2/x.txt"),
        )
        for first, alias in pairs:
            with (
                self.subTest(first=first, alias=alias),
                tempfile.TemporaryDirectory() as td,
            ):
                root = Path(td).resolve()
                source = root / "source"
                output = root / "output"
                _parquet(source / "p.parquet", [{"id": first, "content": "one"}])
                self.assertEqual(export_subset(source, output), 1)
                marker = output / ".dci_export_complete"
                marker_inode = marker.stat().st_ino
                marker_content = marker.read_bytes()
                before = tuple(
                    (
                        path.relative_to(output).as_posix(),
                        path.lstat().st_ino,
                        path.read_bytes() if path.is_file() else None,
                    )
                    for path in sorted(output.rglob("*"))
                )
                _parquet(source / "p.parquet", [{"id": alias, "content": "one"}])
                with self.assertRaises(DciExportError):
                    export_subset(source, output)
                self.assertEqual((output / first).read_text(), "one")
                self.assertEqual(sum(path.is_dir() for path in output.iterdir()), 1)
                self.assertEqual(marker.read_bytes(), marker_content)
                self.assertEqual(marker.stat().st_ino, marker_inode)
                self.assertEqual(
                    tuple(
                        (
                            path.relative_to(output).as_posix(),
                            path.lstat().st_ino,
                            path.read_bytes() if path.is_file() else None,
                        )
                        for path in sorted(output.rglob("*"))
                    ),
                    before,
                )

    def test_arbitrary_export_temp_prefix_file_is_preserved_and_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            output.mkdir()
            user_file = output / ".asterion-dci-export-tmp-user-owned"
            user_file.write_text("KEEP")
            _parquet(source / "p.parquet", [{"id": "a", "content": "A"}])
            with self.assertRaises(DciExportError):
                export_subset(source, output)
            self.assertEqual(user_file.read_text(), "KEEP")
            self.assertFalse((output / ".dci_export_complete").exists())

    def test_multibyte_names_fit_portable_component_limits(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            _parquet(
                source / "p.parquet",
                [
                    {
                        "docid": "文" * 300,
                        "text": f"Title: {'界' * 300}\none",
                        "url": "https://example.com/a",
                    },
                    {
                        "docid": "文" * 299 + "二",
                        "text": f"Title: {'界' * 300}\ntwo",
                        "url": "https://example.com/b",
                    },
                ],
            )
            self.assertEqual(export_bcplus(source, output), 2)
            names = [path.name for path in (output / "example.com").iterdir()]
            self.assertEqual(len(names), 2)
            self.assertTrue(all(len(name.encode("utf-8")) <= 240 for name in names))
            self.assertTrue(
                all(len(name.encode("utf-16-le")) // 2 <= 240 for name in names)
            )

    def test_qa_publication_keeps_open_directory_authority_across_rebind(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            parent = root / "parent"
            authority = root / "held-parent"
            attacker = root / "attacker"
            attacker.mkdir()
            _parquet(source / "p.parquet", [{"id": "1", "query": "q", "answer": "a"}])
            original = export_module._remove_stale_temporaries
            rebound = False

            def rebind(directory: object) -> None:
                nonlocal rebound
                original(directory)
                if not rebound:
                    parent.rename(authority)
                    parent.symlink_to(attacker, target_is_directory=True)
                    rebound = True

            with mock.patch.object(
                export_module, "_remove_stale_temporaries", side_effect=rebind
            ):
                self.assertEqual(
                    export_bcplus_qa(source, parent / "qa.jsonl", decrypt=False), 1
                )
            self.assertEqual(
                json.loads((authority / "qa.jsonl").read_text())["query"], "q"
            )
            self.assertFalse((attacker / "qa.jsonl").exists())

    def test_parquet_reads_keep_open_source_authority_across_rebind(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            held = root / "held-source"
            attacker = root / "attacker"
            output = root / "output"
            _parquet(
                source / "p.parquet",
                [
                    {
                        "docid": "1",
                        "text": "Title: Safe\nsafe",
                        "url": "https://example.com/safe",
                    }
                ],
            )
            _parquet(
                attacker / "p.parquet",
                [
                    {
                        "docid": "1",
                        "text": "Title: Attack\nattack",
                        "url": "https://evil.test/attack",
                    }
                ],
            )
            original = export_module._locked_root

            @contextlib.contextmanager
            def rebind(path: Path):
                source.rename(held)
                source.symlink_to(attacker, target_is_directory=True)
                with original(path) as directory:
                    yield directory

            with mock.patch.object(export_module, "_locked_root", side_effect=rebind):
                self.assertEqual(export_bcplus(source, output), 1)
            self.assertEqual(
                (output / "example.com/Safe.txt").read_text(), "Title: Safe\nsafe"
            )
            self.assertFalse((output / "evil.test").exists())

    def test_bright_preflight_keeps_parquet_authority_through_publication(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            source = root / "source"
            output = root / "output"
            parquet = source / "p.parquet"
            _parquet(parquet, [{"id": "safe.txt", "content": "safe"}])
            self.assertEqual(export_subset(source, output), 1)
            original = export_module._validate_bright_destination

            def replace_after_preflight(inputs: object, directory: object) -> None:
                original(inputs, directory)
                replacement = source / "replacement.parquet"
                _parquet(replacement, [{"other": "attacker"}])
                os.replace(replacement, parquet)

            with mock.patch.object(
                export_module,
                "_validate_bright_destination",
                side_effect=replace_after_preflight,
            ):
                self.assertEqual(export_subset(source, output), 1)
            self.assertEqual((output / "safe.txt").read_text(), "safe")
            self.assertEqual((output / ".dci_export_complete").read_text(), "1\n")

    def test_cli_failures_are_body_free_and_module_has_no_baseline_import(self) -> None:
        err = io.StringIO()
        out = io.StringIO()
        self.assertEqual(
            cli_main(
                [
                    "export",
                    "bcplus",
                    "--source-dir",
                    "/missing",
                    "--output-dir",
                    "/tmp/out",
                ],
                repo_root=ROOT,
                stdout=out,
                stderr=err,
            ),
            2,
        )
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "DCI export failed\n")
        source = (
            ROOT / "packages/python/asterion-core/src/asterion/dci/export.py"
        ).read_text()
        self.assertNotIn("src.dci", source)
        self.assertNotIn("import pandas", source)
        self.assertNotIn("concat(", source)

    def test_installed_wheel_exports_without_repository_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            dist = root / "dist"
            venv = root / "venv"
            subprocess.run(
                [
                    "uv",
                    "build",
                    "--package",
                    "asterion",
                    "--wheel",
                    "--out-dir",
                    str(dist),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            wheel = next(dist.glob("*.whl"))
            with zipfile.ZipFile(wheel) as archive:
                self.assertIn("asterion/dci/export.py", archive.namelist())
                metadata = archive.read(
                    next(
                        name for name in archive.namelist() if name.endswith("METADATA")
                    )
                ).decode()
                self.assertIn("Requires-Dist: pyarrow", metadata)
            subprocess.run(
                ["uv", "venv", "--system-site-packages", str(venv)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(venv / "bin/python"),
                    str(wheel),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            imported = subprocess.run(
                [
                    str(venv / "bin/python"),
                    "-I",
                    "-c",
                    "import asterion.dci.export; import pyarrow",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(imported.returncode, 0, imported.stderr)
            command = subprocess.run(
                [str(venv / "bin/asterion-dci"), "export", "--help"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(command.returncode, 0, command.stderr)
            self.assertIn("bcplus-qa", command.stdout)
            failed = subprocess.run(
                [
                    str(venv / "bin/asterion-dci"),
                    "export",
                    "bcplus",
                    "--source-dir",
                    str(root / "missing"),
                    "--output-dir",
                    str(root / "out"),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(failed.stdout, "")
            self.assertEqual(failed.stderr, "DCI export failed\n")


def cli_main_help(*args: str) -> str:
    stdout = io.StringIO()
    status = cli_main(
        [*args, "--help"], repo_root=ROOT, stdout=stdout, stderr=io.StringIO()
    )
    if status != 0:
        raise AssertionError(f"help exited {status}")
    return stdout.getvalue()


if __name__ == "__main__":
    unittest.main()
