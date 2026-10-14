"""Source correspondence only; actual queue decisions have Rust replay tests."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def body(path: str, name: str) -> str:
    source = (ROOT / path).read_text(encoding="utf-8")
    start = re.search(rf"(?m)^(?:pub(?:\([^)]*\))? )?(?:async )?fn {name}\(", source)
    if not start:
        raise AssertionError(f"missing production function {name}")
    remainder = source[start.end():]
    end = re.search(r"(?m)^(?:pub(?:\([^)]*\))? )?(?:async )?fn \w+\(", remainder)
    return remainder[:end.start()] if end else remainder


class OutputDrainWiring(unittest.TestCase):
    def test_start_error_schedules_the_shared_drain(self):
        self.assertRegex(body("src-tauri/src/commands/audio.rs", "emit_start_error"),
                         r"audio_service::flush_pending_paste\(app_handle\)")

    def test_start_cancel_schedules_before_the_terminal_branch(self):
        source = body("src-tauri/src/commands/audio.rs", "stop_recording_inner")
        branch = source.index("let session = match recording {")
        self.assertIn("audio_service::flush_pending_paste(&app_handle)", source[:branch])

    def test_success_and_error_terminal_helpers_schedule_the_shared_drain(self):
        for name in ["emit_done_with_timing", "emit_terminal_outcome"]:
            self.assertIn("flush_pending_paste(app)",
                          body("src-tauri/src/services/audio_service/finalize.rs", name))


if __name__ == "__main__":
    unittest.main()
