"""
Comprehensive Multilingual Test Suite for CivicAssist (English, Hindi, Kannada).
Tests intent detection, cross-lingual retrieval, conversational memory,
and deterministic grounded response generation across Hindi and Kannada.
"""

import unittest
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.response_generator import CivicResponseGenerator
from src.schemas import IntentType, ConfidenceLevel

class TestMultilingualCivicAssist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = CivicResponseGenerator()

    def setUp(self):
        for sid in [
            "kn_test_1", "kn_test_follow", "kn_test_2", "kn_test_3",
            "kn_test_4", "kn_test_5", "kn_test_6", "kn_test_7", "kn_test_8",
            "hi_test_1", "hi_test_2", "hi_test_3", "hi_test_4"
        ]:
            self.generator.clear_session(sid)

    # ------------------ KANNADA TESTS ------------------

    def test_kannada_waste_query(self):
        """Test waste query in Kannada with Zone A."""
        res = self.generator.process_query("ವಲಯ ಎ ನಲ್ಲಿ ಕಸ ಯಾವಾಗ ಸಂಗ್ರಹಿಸಲಾಗುತ್ತದೆ?", session_id="kn_test_1", language="kn")
        self.assertEqual(res.detected_intent, IntentType.WASTE_QUERY)
        self.assertEqual(res.language, "kn")
        self.assertTrue("ವಲಯ" in res.answer or "Zone A" in res.answer or "ಕಸ" in res.answer)
        # Verify retrieved sources hit Zone A
        self.assertGreater(len(res.sources), 0)
        self.assertEqual(res.sources[0].record_id, "Zone A")

    def test_kannada_follow_up(self):
        """Test conversational follow-up memory in Kannada."""
        # Turn 1
        self.generator.process_query("ವಲಯ ಎ ನಲ್ಲಿ ಕಸ ಯಾವಾಗ ಸಂಗ್ರಹಿಸಲಾಗುತ್ತದೆ?", session_id="kn_test_follow", language="kn")
        # Turn 2: Follow-up
        res = self.generator.process_query("ಮುಂದಿನ ವಾರದ ಬಗ್ಗೆ ಏನು?", session_id="kn_test_follow", language="kn")
        self.assertEqual(res.detected_intent, IntentType.FOLLOW_UP_QUERY)
        self.assertEqual(res.language, "kn")
        self.assertGreater(len(res.sources), 0)
        self.assertEqual(res.sources[0].record_id, "Zone A")

    def test_kannada_permit_query(self):
        """Test food business permit requirements in Kannada."""
        res = self.generator.process_query("ಆಹಾರ ವ್ಯಾಪಾರ ಪರವಾನಗಿಗೆ ಯಾವ ದಾಖಲೆಗಳು ಬೇಕು?", session_id="kn_test_2", language="kn")
        self.assertEqual(res.detected_intent, IntentType.PERMIT_QUERY)
        self.assertEqual(res.language, "kn")
        self.assertTrue("ದಾಖಲೆ" in res.answer or "ಪರವಾನಗಿ" in res.answer or "ಅರ್ಜಿ" in res.answer)
        self.assertGreater(len(res.sources), 0)
        self.assertEqual(res.sources[0].record_id, "PERMIT-002")

    def test_kannada_event_query(self):
        """Test city marathon event lookup in Kannada."""
        res = self.generator.process_query("ನಗರದ ಮ್ಯಾರಥಾನ್ ಎಲ್ಲಿ ನಡೆಯಲಿದೆ?", session_id="kn_test_3", language="kn")
        self.assertEqual(res.detected_intent, IntentType.EVENT_QUERY)
        self.assertEqual(res.language, "kn")
        self.assertTrue("ಮ್ಯಾರಥಾನ್" in res.answer or "City Marathon" in res.answer or "ಕಾರ್ಯಕ್ರಮ" in res.answer)
        self.assertGreater(len(res.sources), 0)
        self.assertEqual(res.sources[0].record_id, "EVT-003")

    def test_kannada_weather_advisory(self):
        """Test weather impact query on city marathon in Kannada."""
        res = self.generator.process_query("ಹವಾಮಾನವು ಸಿಟಿ ಮ್ಯಾರಥಾನ್ ಮೇಲೆ ಪರಿಣಾಮ ಬೀರುತ್ತದೆಯೇ?", session_id="kn_test_4", language="kn")
        self.assertEqual(res.detected_intent, IntentType.EVENT_WEATHER_QUERY)
        self.assertEqual(res.language, "kn")
        self.assertIsNotNone(res.weather_info)
        self.assertTrue("ಹವಾಮಾನ" in res.answer or "ಮಳೆ" in res.answer or "ಮ್ಯಾರಥಾನ್" in res.answer)

    def test_kannada_edge_case_zone_z(self):
        """Test refusal to hallucinate non-existent Zone Z in Kannada."""
        res = self.generator.process_query("ವಲಯ ಝಡ್ (Zone Z) ನ ಬಗ್ಗೆ ಏನು?", session_id="kn_test_5", language="kn")
        self.assertEqual(res.detected_intent, IntentType.WASTE_QUERY)
        self.assertEqual(res.language, "kn")
        self.assertIn("Zone Z", res.answer)
        self.assertIn("ದಾಖಲೆಗಳು ಲಭ್ಯವಿಲ್ಲ", res.answer)

    def test_kannada_ambiguous_waste(self):
        """Test clarification request for ambiguous waste query in Kannada."""
        res = self.generator.process_query("ಕಸ ಸಂಗ್ರಹ ವೇಳಾಪಟ್ಟಿ ಏನು?", session_id="kn_test_6", language="kn")
        self.assertEqual(res.detected_intent, IntentType.WASTE_QUERY)
        self.assertTrue(res.clarification_needed)
        self.assertIn("ವಲಯ", res.answer)

    def test_kannada_out_of_scope(self):
        """Test redirection on out-of-scope services in Kannada."""
        res = self.generator.process_query("ನನ್ನ ಪಾಸ್‌ಪೋರ್ಟ್ ನವೀಕರಿಸುವುದು ಹೇಗೆ?", session_id="kn_test_7", language="kn")
        self.assertEqual(res.detected_intent, IntentType.UNKNOWN)
        self.assertIn("ಪಾಸ್‌ಪೋರ್ಟ್", res.answer)

    def test_kannada_greeting(self):
        """Test greeting response in Kannada."""
        res = self.generator.process_query("ನಮಸ್ಕಾರ", session_id="kn_test_8", language="kn")
        self.assertEqual(res.detected_intent, IntentType.GREETING)
        self.assertIn("ಸಿವಿಕ್ಅಸಿಸ್ಟ್", res.answer)

    # ------------------ HINDI TESTS ------------------

    def test_hindi_waste_query(self):
        """Test waste query in Hindi with Zone A."""
        res = self.generator.process_query("ज़ोन ए में कचरा कब उठाया जाता है?", session_id="hi_test_1", language="hi")
        self.assertEqual(res.detected_intent, IntentType.WASTE_QUERY)
        self.assertEqual(res.language, "hi")
        self.assertTrue("कचरा" in res.answer or "सफाई" in res.answer or "Zone A" in res.answer or "ज़ोन" in res.answer)
        self.assertGreater(len(res.sources), 0)
        self.assertEqual(res.sources[0].record_id, "Zone A")

    def test_hindi_permit_query(self):
        """Test food business permit requirements in Hindi."""
        res = self.generator.process_query("खाद्य व्यवसाय परमिट के लिए कौन से दस्तावेज़ चाहिए?", session_id="hi_test_2", language="hi")
        self.assertEqual(res.detected_intent, IntentType.PERMIT_QUERY)
        self.assertEqual(res.language, "hi")
        self.assertTrue("दस्तावेज़" in res.answer or "दस्तावेज" in res.answer or "परमिट" in res.answer or "आवेदन" in res.answer)
        self.assertGreater(len(res.sources), 0)
        self.assertEqual(res.sources[0].record_id, "PERMIT-002")

    def test_hindi_weather_advisory(self):
        """Test weather impact query on city marathon in Hindi."""
        res = self.generator.process_query("क्या मौसम सिटी मैराथन को प्रभावित करेगा?", session_id="hi_test_3", language="hi")
        self.assertEqual(res.detected_intent, IntentType.EVENT_WEATHER_QUERY)
        self.assertEqual(res.language, "hi")
        self.assertIsNotNone(res.weather_info)
        self.assertTrue("मौसम" in res.answer or "बारिश" in res.answer or "मैराथन" in res.answer)

    def test_hindi_edge_case_zone_z(self):
        """Test refusal to hallucinate non-existent Zone Z in Hindi."""
        res = self.generator.process_query("ज़ोन ज़ेड (Zone Z) के बारे में क्या?", session_id="hi_test_4", language="hi")
        self.assertEqual(res.detected_intent, IntentType.WASTE_QUERY)
        self.assertEqual(res.language, "hi")
        self.assertIn("Zone Z", res.answer)
        self.assertIn("रिकॉर्ड नहीं मिला", res.answer)

if __name__ == "__main__":
    unittest.main()
