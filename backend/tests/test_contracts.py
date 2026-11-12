"""Check a reusable and non-shared structured agent message."""
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from core.contracts import AgentMessage  # noqa: E402


class ContractTests(unittest.TestCase):
    def test_message_contract(self):
        msg = AgentMessage(request_id="req_demo", agent="dl_prediction", status="skipped")
        self.assertEqual(
            set(msg.to_dict()),
            {"request_id", "agent", "status", "payload", "evidence", "version", "error"},
        )
        self.assertEqual(msg.to_dict()["evidence"], [])

    def test_mutable_defaults_are_not_shared(self):
        a = AgentMessage(request_id="r1", agent="a", status="ok")
        b = AgentMessage(request_id="r2", agent="b", status="ok")
        a.payload["k"] = "test"
        a.evidence.append({"source": "example"})
        self.assertEqual(b.payload, {})
        self.assertEqual(b.evidence, [])


if __name__ == "__main__":
    unittest.main()
