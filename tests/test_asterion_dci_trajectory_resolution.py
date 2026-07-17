from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import asterion.dci.trajectory_resolution as trajectory_resolution
from asterion.dci.artifacts import DciConversationFeatures, DciRunRecorder
from asterion.dci.config import resolve_dci_paths
from asterion.dci.run import DciRunRequest
from asterion.dci.trajectory_resolution import (
    TrajectoryAnalysisConfig,
    TrajectoryResolutionError,
    analyze_trajectory_resolution,
    public_resolution_projection,
)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _protocol_event(sequence: int, event_type: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "protocol": "dci.agent-runtime/v1",
        "run_id": "run-1-attempt-0001",
        "sequence": sequence,
        "type": event_type,
        "payload": payload,
    }


class TrajectoryResolutionTest(unittest.TestCase):
    def _fixture(
        self,
        root: Path,
        *,
        documents: dict[str, str],
        gold: tuple[tuple[str, tuple[tuple[int, int], ...]], ...],
        calls: tuple[tuple[str, str, dict[str, object], str], ...],
    ) -> tuple[Path, Path, Path]:
        run_dir = root / "run"
        corpus_dir = root / "corpus"
        tool_dir = run_dir / "tool_results"
        protocol_dir = run_dir / "protocol"
        corpus_dir.mkdir()
        tool_dir.mkdir(parents=True)
        protocol_dir.mkdir()

        manifest_documents = []
        for document_id, body in documents.items():
            data = body.encode()
            path = corpus_dir / document_id
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            spans = dict(gold)[document_id]
            manifest_documents.append(
                {
                    "id": document_id,
                    "path": document_id,
                    "sha256": _digest(data),
                    "evidence_spans": [
                        {"start": start, "end": end} for start, end in spans
                    ],
                }
            )
        manifest = {
            "schema": "dci.gold-document-manifest/v1",
            "dataset_id": "fixture.qa",
            "query_id": "q-1",
            "documents": manifest_documents,
        }
        manifest_path = root / "gold.json"
        _write_json(manifest_path, manifest)

        events = [_protocol_event(1, "run.started", {"capabilities": []})]
        sequence = 2
        for call_id, tool_name, arguments, output in calls:
            events.append(
                _protocol_event(
                    sequence,
                    "tool.call",
                    {"call_id": call_id, "name": tool_name, "arguments": arguments},
                )
            )
            sequence += 1
            events.append(
                _protocol_event(
                    sequence,
                    "tool.result",
                    {"call_id": call_id, "output": output, "is_error": False},
                )
            )
            sequence += 1
            _write_json(
                tool_dir / f"{call_id}.json",
                {
                    "saved_at": "2026-07-17T00:00:00+00:00",
                    "message": {
                        "role": "toolResult",
                        "toolCallId": call_id,
                        "toolName": tool_name,
                        "content": [{"type": "text", "text": output}],
                    },
                },
            )
        events.append(_protocol_event(sequence, "run.completed", {"status": "completed"}))
        _write_json(
            protocol_dir / "attempt-0001.request.json",
            {
                "protocol": "dci.agent-runtime/v1",
                "run_id": "run-1-attempt-0001",
                "input": {"text": "fixture question"},
                "requested_capabilities": [],
            },
        )
        protocol_path = protocol_dir / "attempt-0001.events.jsonl"
        protocol_path.write_text(
            "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
            encoding="utf-8",
        )
        _write_json(
            run_dir / "state.json",
            {
                "run_id": "run-1",
                "status": "completed",
                "question": "fixture question",
                "cwd": str(root),
                "provider": None,
                "model": None,
                "tools": "",
                "conversation_features": DciConversationFeatures().to_mapping(),
                "notes": [],
                "pi_source_attempts": [{"fixture": True}],
                "resume_count": 0,
                "attempts": [
                    {
                        "attempt": 1,
                        "status": "completed",
                        "command_summary": {
                            "executable": "node",
                            "mode": "rpc",
                            "option_names": ["--mode"],
                            "configured_extra_argument_groups": 0,
                            "typed_extra_argument_count": 0,
                        },
                        "timeout_seconds": None,
                        "stderr_tail_characters": 0,
                    }
                ],
            },
        )
        _write_json(
            run_dir / "latest_model_context.json",
            {
                "status": "completed",
                "question": "fixture question",
                "cwd": str(root),
                "provider": None,
                "model": None,
                "conversation_features": DciConversationFeatures().to_mapping(),
                "request_count": 1,
                "runtime_context_management": None,
                "latest": {"messages": []},
                "notes": [],
                "pi_source_attempts": [{"fixture": True}],
            },
        )
        return run_dir, corpus_dir, manifest_path

    def test_read_span_aligns_only_returned_gold_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            body = "prefix\nneedle evidence\nsuffix\n"
            start = body.index("needle")
            run_dir, corpus_dir, manifest = self._fixture(
                root,
                documents={"docs/a.txt": body},
                gold=(("docs/a.txt", ((start, start + len("needle evidence")),)),),
                calls=(("read-1", "read", {"path": "docs/a.txt", "offset": 2, "limit": 1}, "needle evidence"),),
            )

            evidence = analyze_trajectory_resolution(
                run_dir=run_dir,
                attempt=1,
                corpus_dir=corpus_dir,
                gold_manifest_path=manifest,
                config=TrajectoryAnalysisConfig(segment_characters=8),
            )

            self.assertEqual(evidence["schema"], "dci.trajectory-resolution/v1")
            self.assertEqual(evidence["metrics"]["coverage"], {"any": 1.0, "mean": 1.0, "all": 1.0})
            self.assertGreater(evidence["metrics"]["localization"]["value"], 0.0)
            alignment = evidence["private"]["alignments"][0]
            self.assertEqual(alignment["rule"], "read-returned-span")
            self.assertEqual(alignment["document_id"], "docs/a.txt")
            self.assertEqual(alignment["snippet_characters"], len("needle evidence"))

    def test_consumes_an_actual_completed_native_recorder_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            corpus_dir = root / "corpus"
            corpus_dir.mkdir()
            body = "native gold evidence\n"
            (corpus_dir / "a.txt").write_text(body)
            manifest = root / "gold.json"
            _write_json(
                manifest,
                {
                    "schema": "dci.gold-document-manifest/v1",
                    "dataset_id": "fixture.native",
                    "query_id": "q-native",
                    "documents": [
                        {
                            "id": "a.txt",
                            "path": "a.txt",
                            "sha256": _digest(body.encode()),
                            "evidence_spans": [{"start": 0, "end": 20}],
                        }
                    ],
                },
            )
            run_dir = root / "native-run"
            recorder = DciRunRecorder(
                output_dir=run_dir,
                request=DciRunRequest(run_id="run-native", question="q", cwd=root),
                paths=resolve_dci_paths(root),
                features=DciConversationFeatures(externalize_tool_results=True),
            )
            recorder.record_event(
                {
                    "type": "tool_execution_start",
                    "toolCallId": "read-1",
                    "toolName": "read",
                    "args": {"path": "a.txt"},
                }
            )
            recorder.record_event(
                {
                    "type": "tool_execution_end",
                    "toolCallId": "read-1",
                    "toolName": "read",
                    "isError": False,
                    "result": "native gold evidence",
                }
            )
            tool_message = {
                "role": "toolResult",
                "toolCallId": "read-1",
                "toolName": "read",
                "content": [{"type": "text", "text": "native gold evidence"}],
            }
            recorder.record_event({"type": "message_end", "message": tool_message})
            recorder.record_event(
                {
                    "type": "provider_request_context",
                    "requestIndex": 1,
                    "model": "fixture",
                    "messages": [tool_message],
                    "payload": {},
                    "runtimeContextManagement": None,
                }
            )
            recorder.finalize(status="completed", final_text="done")

            evidence = analyze_trajectory_resolution(
                run_dir=run_dir,
                attempt=1,
                corpus_dir=corpus_dir,
                gold_manifest_path=manifest,
                config=TrajectoryAnalysisConfig(segment_characters=8),
            )

            self.assertEqual(evidence["run"], {"run_id": "run-native", "attempt": 1})
            self.assertEqual(evidence["metrics"]["coverage"]["all"], 1.0)

    def test_grep_output_aligns_each_exact_matched_line_and_multiple_gold_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = "alpha\nMATCH one\nomega\n"
            second = "head\nMATCH two\ntail\n"
            run_dir, corpus_dir, manifest = self._fixture(
                root,
                documents={"a.txt": first, "b.txt": second},
                gold=(
                    ("a.txt", ((first.index("MATCH"), first.index("MATCH") + 9),)),
                    ("b.txt", ((second.index("MATCH"), second.index("MATCH") + 9),)),
                ),
                calls=(("grep-1", "grep", {"path": ".", "pattern": "MATCH"}, "a.txt:2:MATCH one\nb.txt:2:MATCH two"),),
            )

            evidence = analyze_trajectory_resolution(
                run_dir=run_dir,
                attempt=1,
                corpus_dir=corpus_dir,
                gold_manifest_path=manifest,
                config=TrajectoryAnalysisConfig(segment_characters=8),
            )

            self.assertEqual(evidence["metrics"]["coverage"], {"any": 1.0, "mean": 1.0, "all": 1.0})
            self.assertEqual(evidence["metrics"]["localization"]["matched_gold_count"], 2)
            self.assertEqual(
                [item["rule"] for item in evidence["private"]["alignments"]],
                ["grep-matched-line", "grep-matched-line"],
            )

    def test_explicit_path_with_unmatched_text_uses_full_document_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            body = "gold evidence lives here\n"
            run_dir, corpus_dir, manifest = self._fixture(
                root,
                documents={"a.txt": body},
                gold=(("a.txt", ((0, 13),)),),
                calls=(("read-1", "read", {"path": "a.txt"}, "not present in the document"),),
            )

            evidence = analyze_trajectory_resolution(
                run_dir=run_dir,
                attempt=1,
                corpus_dir=corpus_dir,
                gold_manifest_path=manifest,
                config=TrajectoryAnalysisConfig(segment_characters=8),
            )

            alignment = evidence["private"]["alignments"][0]
            self.assertEqual(alignment["rule"], "full-document-fallback")
            self.assertEqual(alignment["snippet_characters"], len(body))
            self.assertEqual(evidence["metrics"]["coverage"]["any"], 1.0)

    def test_unknown_tool_and_malformed_or_missing_evidence_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir, corpus_dir, manifest = self._fixture(
                root,
                documents={"a.txt": "evidence\n"},
                gold=(("a.txt", ((0, 8),)),),
                calls=(("web-1", "web", {"query": "a.txt"}, "a.txt"),),
            )
            with self.assertRaises(TrajectoryResolutionError):
                analyze_trajectory_resolution(
                    run_dir=run_dir,
                    attempt=1,
                    corpus_dir=corpus_dir,
                    gold_manifest_path=manifest,
                    config=TrajectoryAnalysisConfig(segment_characters=8),
                )

            (run_dir / "tool_results/web-1.json").unlink()
            with self.assertRaises(TrajectoryResolutionError):
                analyze_trajectory_resolution(
                    run_dir=run_dir,
                    attempt=1,
                    corpus_dir=corpus_dir,
                    gold_manifest_path=manifest,
                    config=TrajectoryAnalysisConfig(segment_characters=8),
                )

    def test_protocol_mutation_and_externalized_body_truncation_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir, corpus_dir, manifest = self._fixture(
                root,
                documents={"a.txt": "gold evidence\n"},
                gold=(("a.txt", ((0, 13),)),),
                calls=(("read-1", "read", {"path": "a.txt"}, "gold evidence"),),
            )
            protocol = run_dir / "protocol/attempt-0001.events.jsonl"
            lines = protocol.read_text().splitlines()
            malformed = json.loads(lines[1])
            malformed["sequence"] = 99
            lines[1] = json.dumps(malformed)
            protocol.write_text("\n".join(lines) + "\n")
            with self.assertRaises(TrajectoryResolutionError):
                analyze_trajectory_resolution(
                    run_dir=run_dir,
                    attempt=1,
                    corpus_dir=corpus_dir,
                    gold_manifest_path=manifest,
                    config=TrajectoryAnalysisConfig(segment_characters=8),
                )

            malformed["sequence"] = 2
            lines[1] = json.dumps(malformed)
            protocol.write_text("\n".join(lines) + "\n")
            externalized_path = run_dir / "tool_results/read-1.json"
            externalized = json.loads(externalized_path.read_text())
            externalized["message"]["content"][0]["text"] = "gold"
            _write_json(externalized_path, externalized)
            with self.assertRaises(TrajectoryResolutionError):
                analyze_trajectory_resolution(
                    run_dir=run_dir,
                    attempt=1,
                    corpus_dir=corpus_dir,
                    gold_manifest_path=manifest,
                    config=TrajectoryAnalysisConfig(segment_characters=8),
                )

    def test_foreign_final_context_and_attempt_request_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir, corpus_dir, manifest = self._fixture(
                root,
                documents={"a.txt": "gold evidence\n"},
                gold=(("a.txt", ((0, 13),)),),
                calls=(("read-1", "read", {"path": "a.txt"}, "gold evidence"),),
            )
            latest_path = run_dir / "latest_model_context.json"
            latest = json.loads(latest_path.read_text())
            latest["question"] = "foreign question"
            _write_json(latest_path, latest)
            with self.assertRaises(TrajectoryResolutionError):
                analyze_trajectory_resolution(
                    run_dir=run_dir,
                    attempt=1,
                    corpus_dir=corpus_dir,
                    gold_manifest_path=manifest,
                    config=TrajectoryAnalysisConfig(segment_characters=8),
                )

            latest["question"] = "fixture question"
            _write_json(latest_path, latest)
            request_path = run_dir / "protocol/attempt-0001.request.json"
            request_document = json.loads(request_path.read_text())
            request_document["input"]["text"] = "foreign question"
            _write_json(request_path, request_document)
            with self.assertRaises(TrajectoryResolutionError):
                analyze_trajectory_resolution(
                    run_dir=run_dir,
                    attempt=1,
                    corpus_dir=corpus_dir,
                    gold_manifest_path=manifest,
                    config=TrajectoryAnalysisConfig(segment_characters=8),
                )

    def test_path_only_and_ambiguous_pipeline_use_conservative_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            body = "gold evidence and more\n"
            run_dir, corpus_dir, manifest = self._fixture(
                root,
                documents={"a.txt": body},
                gold=(("a.txt", ((0, 13),)),),
                calls=(
                    ("grep-1", "grep", {"path": "a.txt", "pattern": "missing"}, "0 matches"),
                    ("bash-1", "bash", {"command": "cat a.txt | head -n 1"}, "gold evidence"),
                    ("bash-2", "bash", {"command": "printf prefix-a.txt-suffix"}, "a.txt"),
                ),
            )

            evidence = analyze_trajectory_resolution(
                run_dir=run_dir,
                attempt=1,
                corpus_dir=corpus_dir,
                gold_manifest_path=manifest,
                config=TrajectoryAnalysisConfig(segment_characters=8),
            )

            alignments = evidence["private"]["alignments"]
            self.assertEqual(len(alignments), 2)
            self.assertTrue(all(item["rule"] == "full-document-fallback" for item in alignments))
            self.assertNotIn("bash-2", {item["call_id"] for item in alignments})

    def test_rejects_traversal_symlink_and_duplicate_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir, corpus_dir, manifest = self._fixture(
                root,
                documents={"a.txt": "evidence\n"},
                gold=(("a.txt", ((0, 8),)),),
                calls=(("read-1", "read", {"path": "a.txt"}, "evidence"),),
            )
            document = json.loads(manifest.read_text())
            duplicate = dict(document["documents"][0])
            duplicate["id"] = "A.TXT"
            document["documents"].append(duplicate)
            _write_json(manifest, document)
            with self.assertRaises(TrajectoryResolutionError):
                analyze_trajectory_resolution(
                    run_dir=run_dir,
                    attempt=1,
                    corpus_dir=corpus_dir,
                    gold_manifest_path=manifest,
                    config=TrajectoryAnalysisConfig(segment_characters=8),
                )

            document["documents"] = [document["documents"][0]]
            document["documents"][0]["path"] = "../a.txt"
            _write_json(manifest, document)
            with self.assertRaises(TrajectoryResolutionError):
                analyze_trajectory_resolution(
                    run_dir=run_dir,
                    attempt=1,
                    corpus_dir=corpus_dir,
                    gold_manifest_path=manifest,
                    config=TrajectoryAnalysisConfig(segment_characters=8),
                )

            document["documents"][0]["path"] = "alias.txt"
            _write_json(manifest, document)
            os.symlink(corpus_dir / "a.txt", corpus_dir / "alias.txt")
            with self.assertRaises(TrajectoryResolutionError):
                analyze_trajectory_resolution(
                    run_dir=run_dir,
                    attempt=1,
                    corpus_dir=corpus_dir,
                    gold_manifest_path=manifest,
                    config=TrajectoryAnalysisConfig(segment_characters=8),
                )

    def test_rejects_inode_replacement_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir, corpus_dir, manifest = self._fixture(
                root,
                documents={"a.txt": "gold evidence\n"},
                gold=(("a.txt", ((0, 13),)),),
                calls=(("read-1", "read", {"path": "a.txt"}, "gold evidence"),),
            )
            original_align = trajectory_resolution._align

            def replace_after_alignment(*args: object, **kwargs: object) -> object:
                result = original_align(*args, **kwargs)
                replacement = corpus_dir / "replacement.txt"
                replacement.write_text("gold evidence\n")
                os.replace(replacement, corpus_dir / "a.txt")
                return result

            with mock.patch.object(
                trajectory_resolution, "_align", side_effect=replace_after_alignment
            ), self.assertRaises(TrajectoryResolutionError):
                analyze_trajectory_resolution(
                    run_dir=run_dir,
                    attempt=1,
                    corpus_dir=corpus_dir,
                    gold_manifest_path=manifest,
                    config=TrajectoryAnalysisConfig(segment_characters=8),
                )

    def test_rejects_run_and_corpus_root_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir, corpus_dir, manifest = self._fixture(
                root,
                documents={"a.txt": "gold evidence\n"},
                gold=(("a.txt", ((0, 13),)),),
                calls=(("read-1", "read", {"path": "a.txt"}, "gold evidence"),),
            )
            run_alias = root / "run-alias"
            corpus_alias = root / "corpus-alias"
            os.symlink(run_dir, run_alias)
            os.symlink(corpus_dir, corpus_alias)
            for selected_run, selected_corpus in (
                (run_alias, corpus_dir),
                (run_dir, corpus_alias),
            ):
                with self.subTest(
                    run=selected_run.name, corpus=selected_corpus.name
                ), self.assertRaises(TrajectoryResolutionError):
                    analyze_trajectory_resolution(
                        run_dir=selected_run,
                        attempt=1,
                        corpus_dir=selected_corpus,
                        gold_manifest_path=manifest,
                        config=TrajectoryAnalysisConfig(segment_characters=8),
                    )

    def test_private_artifact_is_atomic_and_public_projection_is_body_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            secret = "PRIVATE GOLD EVIDENCE"
            run_dir, corpus_dir, manifest = self._fixture(
                root,
                documents={"secret/a.txt": secret},
                gold=(("secret/a.txt", ((0, len(secret)),)),),
                calls=(("read-1", "read", {"path": "secret/a.txt"}, secret),),
            )
            output_path = run_dir / "trajectory-resolution.json"

            evidence = analyze_trajectory_resolution(
                run_dir=run_dir,
                attempt=1,
                corpus_dir=corpus_dir,
                gold_manifest_path=manifest,
                config=TrajectoryAnalysisConfig(segment_characters=8),
                output_path=output_path,
            )
            public = public_resolution_projection(evidence)
            serialized = json.dumps(public)

            self.assertTrue(output_path.is_file())
            self.assertEqual(os.stat(output_path).st_mode & 0o777, 0o600)
            self.assertNotIn(secret, serialized)
            self.assertNotIn(str(root), serialized)
            self.assertNotIn("secret/a.txt", serialized)
            self.assertNotIn("private", public)
            self.assertEqual(public["schema"], "dci.trajectory-resolution-summary/v1")
            self.assertEqual(len(evidence["identity"]["sha256"]), 64)

            evidence["metrics"]["coverage"]["leaked_body"] = secret
            evidence["counts"]["leaked_path"] = str(root)
            with self.assertRaises(TrajectoryResolutionError):
                public_resolution_projection(evidence)
            evidence["metrics"]["coverage"].pop("leaked_body")
            evidence["counts"].pop("leaked_path")

            evidence["metrics"]["coverage"]["any"] = secret
            with self.assertRaises(TrajectoryResolutionError):
                public_resolution_projection(evidence)
            evidence["metrics"]["coverage"]["any"] = 1.0
            evidence["dataset"]["query_id"] = "/private/path"
            with self.assertRaises(TrajectoryResolutionError):
                public_resolution_projection(evidence)
            evidence["dataset"]["query_id"] = "different-safe-id"
            with self.assertRaises(TrajectoryResolutionError):
                public_resolution_projection(evidence)


if __name__ == "__main__":
    unittest.main()
