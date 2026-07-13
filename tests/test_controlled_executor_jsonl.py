from __future__ import annotations

import asyncio
import json
import unittest

from asterion.services.controlled_executor import (
    ControlledExecutionRequest,
    ControlledExecutorError,
)
from asterion.services.controlled_executor_jsonl import (
    ControlledExecutorJsonlClient,
    TrustedValidationConfig,
)


class BufferWriter:
    def __init__(self) -> None:
        self.values: list[bytes] = []

    def write(self, value: bytes) -> None:
        self.values.append(value)

    async def drain(self) -> None:
        return None


def response(**overrides):
    value = {
        "protocol": "dci.executor/v1",
        "request_id": "asterion-exec-1",
        "type": "execution.result",
        "status": "completed",
        "exit_code": 0,
        "stdout": "SECRET-STDOUT",
        "stderr": "",
        "stdout_truncated": False,
        "stderr_truncated": False,
        "code": None,
    }
    value.update(overrides)
    return value


class ControlledExecutorJsonlTests(unittest.IsolatedAsyncioTestCase):
    async def test_translates_logical_target_using_trusted_configuration(self) -> None:
        reader = asyncio.StreamReader()
        reader.feed_data((json.dumps(response()) + "\n").encode())
        writer = BufferWriter()
        client = ControlledExecutorJsonlClient(
            reader=reader,
            writer=writer,
            config=TrustedValidationConfig(
                program_id="python-check",
                argument_prefix=("--check",),
                cwd="workspace",
                deadline_ms=1000,
                max_output_bytes=4096,
            ),
        )

        result = await client.execute(ControlledExecutionRequest("src/example.py"))

        request = json.loads(writer.values[0])
        self.assertEqual(request["program_id"], "python-check")
        self.assertEqual(request["arguments"], ["--check", "src/example.py"])
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.stdout_bytes, len("SECRET-STDOUT".encode()))
        self.assertFalse(hasattr(result, "stdout"))

    async def test_malformed_mismatched_or_protocol_error_responses_are_redacted(self) -> None:
        for payload in (
            b"not-json\n",
            (json.dumps(response(request_id="other")) + "\n").encode(),
            (
                json.dumps(
                    {
                        "protocol": "dci.executor/v1",
                        "request_id": "asterion-exec-1",
                        "type": "protocol.error",
                        "code": "SECRET-CODE",
                        "message": "SECRET-MESSAGE",
                    }
                )
                + "\n"
            ).encode(),
        ):
            reader = asyncio.StreamReader()
            reader.feed_data(payload)
            writer = BufferWriter()
            client = ControlledExecutorJsonlClient(
                reader=reader,
                writer=writer,
                config=TrustedValidationConfig(
                    program_id="check",
                    argument_prefix=(),
                    cwd="workspace",
                    deadline_ms=1000,
                    max_output_bytes=1024,
                ),
            )
            with self.assertRaises(ControlledExecutorError) as caught:
                await client.execute(ControlledExecutionRequest("src/example.py"))
            self.assertNotIn("SECRET", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
