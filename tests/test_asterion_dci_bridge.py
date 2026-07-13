from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from asterion.dci.bridge import project_dci_run
from asterion.dci.run import DciRunResult
from asterion.runtime.host import RunEvent


def fixture_result(output_dir: Path, *, final_text: str = "SECRET-ANSWER") -> DciRunResult:
    return DciRunResult(
        output_dir=output_dir,
        final_text=final_text,
        events=(
            RunEvent("run", 1, "run.started", {"capabilities": []}),
            RunEvent(
                "run",
                2,
                "artifact.created",
                {
                    "artifact": {
                        "artifact_id": "final-answer",
                        "kind": "answer",
                        "media_type": "text/plain",
                        "uri": "final.txt",
                    }
                },
            ),
            RunEvent("run", 3, "run.completed", {"status": "completed"}),
        ),
        status="completed",
    )


class AsterionDciBridgeTests(unittest.TestCase):
    def test_projection_preserves_native_references_without_answer_body(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            projection = project_dci_run(fixture_result(Path(temporary_directory) / "run"))

        self.assertEqual(projection.events[0]["type"], "research.completed")
        self.assertEqual(projection.artifacts[0]["media_type"], "application/vnd.dci.research+json")
        self.assertEqual(
            dict(projection.artifacts[0]["value"]),
            {
                "answer_artifact_uri": "final.txt",
                "events_artifact_uri": "events.jsonl",
                "state_artifact_uri": "state.json",
            },
        )
        self.assertNotIn("SECRET-ANSWER", repr(projection))

    def test_projection_rejects_a_noncompleted_native_result(self) -> None:
        result = fixture_result(Path("run"))
        invalid = DciRunResult(
            output_dir=result.output_dir,
            final_text=result.final_text,
            events=result.events[:-1],
            status="failed",
        )
        with self.assertRaisesRegex(ValueError, "completed"):
            project_dci_run(invalid)


if __name__ == "__main__":
    unittest.main()
