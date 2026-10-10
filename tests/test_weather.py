"""
Unit tests for Weather Service integration & fallback.
"""

import unittest
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.weather_service import WeatherService

class TestWeatherService(unittest.TestCase):
    def setUp(self):
        self.weather = WeatherService()

    def test_marathon_weather_advisory(self):
        adv = self.weather.get_weather_for_event(
            event_name="City Marathon",
            event_date="2026-10-12",
            location="Central Park, Greenfield",
            is_outdoor=True
        )
        self.assertEqual(adv.event_name, "City Marathon")
        self.assertIn("Central Park", adv.location)
        self.assertGreaterEqual(adv.rain_probability, 0)
        self.assertIn("forecast", adv.advisory_note.lower())

    def test_outdoor_concert_weather(self):
        adv = self.weather.get_weather_for_event(
            event_name="Summer Park Jazz Concert Series",
            event_date="2026-10-11",
            location="Elm Park Amphitheater",
            is_outdoor=True
        )
        self.assertEqual(adv.event_name, "Summer Park Jazz Concert Series")
        self.assertIsNotNone(adv.forecast_summary)

if __name__ == "__main__":
    unittest.main()
