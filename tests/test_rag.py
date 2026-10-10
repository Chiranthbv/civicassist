"""
Unit tests for Municipal RAG Pipeline & Vector Store.
"""

import unittest
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.rag import MunicipalRAGPipeline

class TestMunicipalRAG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rag = MunicipalRAGPipeline()

    def test_load_waste_data(self):
        zones = self.rag.get_all_waste_zones()
        self.assertGreaterEqual(len(zones), 10)
        zone_a = self.rag.get_waste_by_zone("Zone A")
        self.assertIsNotNone(zone_a)
        self.assertIn("Monday", zone_a.get("pickup_days", []))

    def test_load_permits(self):
        permits = self.rag.get_all_permits()
        self.assertGreaterEqual(len(permits), 10)
        p1 = [p for p in permits if p.get("permit_id") == "PERMIT-001"]
        self.assertEqual(len(p1), 1)
        self.assertIn("$450", p1[0].get("fee", ""))

    def test_load_events(self):
        events = self.rag.get_all_events()
        self.assertGreaterEqual(len(events), 15)
        marathon = self.rag.get_event_by_name("City Marathon")
        self.assertIsNotNone(marathon)
        self.assertEqual(marathon.get("date"), "2026-10-12")

    def test_waste_retrieval(self):
        sources = self.rag.retrieve("When is garbage collected in Zone A?", top_k=3, domain="waste")
        self.assertGreater(len(sources), 0)
        self.assertEqual(sources[0].record_id, "Zone A")

    def test_permit_retrieval(self):
        sources = self.rag.retrieve("What documents do I need for a food business permit?", top_k=3, domain="permits")
        self.assertGreater(len(sources), 0)
        self.assertEqual(sources[0].record_id, "PERMIT-002")

    def test_event_retrieval(self):
        sources = self.rag.retrieve("Where is the city marathon?", top_k=3, domain="events")
        self.assertGreater(len(sources), 0)
        self.assertEqual(sources[0].record_id, "EVT-003")

if __name__ == "__main__":
    unittest.main()
