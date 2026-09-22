"""
Unit tests for UnifiedBroker asset-to-broker resolution.
"""

import unittest
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.broker_interface import UnifiedBroker


class TestUnifiedBrokerMapping(unittest.TestCase):
    """Asset-to-broker resolution must be configurable yet default to MT5."""

    def setUp(self):
        self.broker = UnifiedBroker()
        self.mock_connector = object()
        # Attach a fake broker directly (avoid real MT5 connection logic)
        self.broker.brokers['mt5'] = self.mock_connector

    def test_explicit_mapping_wins(self):
        self.broker.map_asset_to_broker('EURUSD', 'mt5')
        self.assertIs(self.broker.get_broker_for_asset('EURUSD'), self.mock_connector)

    def test_single_broker_is_default(self):
        # No mapping configured but exactly one broker is connected:
        # the broker must be used (default MT5 behavior).
        self.assertIs(self.broker.get_broker_for_asset('XAUUSD'), self.mock_connector)

    def test_no_brokers_returns_none(self):
        empty = UnifiedBroker()
        self.assertIsNone(empty.get_broker_for_asset('XAUUSD'))

    def test_mapping_to_missing_broker_returns_none(self):
        # Explicitly mapped to a broker that is not connected -> None.
        self.broker.map_asset_to_broker('EURUSD', 'rebell')
        self.assertIsNone(self.broker.get_broker_for_asset('EURUSD'))

    def test_multiple_brokers_require_explicit_mapping(self):
        self.broker.brokers['rebell'] = object()
        # Ambiguous: must not silently pick one.
        self.assertIsNone(self.broker.get_broker_for_asset('EURUSD'))
        # After mapping, resolves deterministically.
        self.broker.map_asset_to_broker('EURUSD', 'rebell')
        self.assertIsNotNone(self.broker.get_broker_for_asset('EURUSD'))


if __name__ == '__main__':
    unittest.main()