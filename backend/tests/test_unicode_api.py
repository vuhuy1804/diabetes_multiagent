"""Regression tests: Vietnamese remains intact for clients decoding JSON on Windows."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app import create_app


class UnicodeApiTests(unittest.TestCase):
    def test_json_ascii_wire_vietnamese_roundtrip(self):
        app = create_app()
        expected = 'Đái tháo đường: triệu chứng, xét nghiệm và tư vấn.'
        dumped = app.json.dumps({'answer': expected})
        # Bytes on HTTP wire are ASCII, so charset guessing cannot corrupt them.
        dumped.encode('ascii')
        self.assertEqual(json.loads(dumped)['answer'], expected)

    def test_knowledge_seed_is_valid_utf8(self):
        seed_path = BACKEND.parent / 'data/knowledge/DB_diabet.cypher'
        seed = seed_path.read_text(encoding='utf-8')
        self.assertIn('Đái tháo đường', seed)


if __name__ == '__main__':
    unittest.main()
