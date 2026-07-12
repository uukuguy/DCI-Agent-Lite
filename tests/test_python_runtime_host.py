from __future__ import annotations

import json
import unittest
from collections.abc import AsyncIterator
from pathlib import Path

from dci.framework.host import (
    AgentRuntimeClient,
    RunEvent,
    RunRequest,
    RuntimeManifest,
    parse_event_stream,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/agent_runtime/v1"


class FixtureClient:
    manifest = RuntimeManifest.from_mapping(
        json.loads((FIXTURE_DIR / "valid-runtime-manifest.json").read_text())
    )

    async def run(self, request: RunRequest) -> AsyncIterator[RunEvent]:
        del request
        events = [
            json.loads(line)
            for line in (FIXTURE_DIR / "valid-research.jsonl").read_text().splitlines()
        ]
        for event in parse_event_stream(events):
            yield event


class PythonRuntimeHostTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_client_consumes_manifest_request_and_event_values(self) -> None:
        client: AgentRuntimeClient = FixtureClient()
        request = RunRequest(
            run_id="host-run",
            input_text="Investigate the fixture corpus",
            requested_capabilities=("filesystem.read", "shell"),
            deadline_ms=30_000,
        )

        events = [event async for event in client.run(request)]

        self.assertEqual(client.manifest.runtime_id, "fixture-runtime")
        self.assertEqual(request.to_mapping()["input"]["text"], request.input_text)
        self.assertEqual(events[0].type, "run.started")
        self.assertEqual(events[-1].type, "run.completed")

    def test_public_host_module_has_no_adapter_imports(self) -> None:
        source = (REPO_ROOT / "src/dci/framework/host.py").read_text()

        self.assertNotIn("framework.adapters", source)
        self.assertNotIn("framework.runtimes", source)


if __name__ == "__main__":
    unittest.main()
