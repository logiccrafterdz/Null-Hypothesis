"""
Regression tests for optional modules importing cleanly on all Python
versions (annotations are lazily evaluated only on 3.14+; older versions
raise NameError unless typing.Optional is imported).
"""

import unittest
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestBacktestModulesImport(unittest.TestCase):
    """Monte Carlo and walk-forward modules must import and construct."""

    def test_monte_carlo_imports_and_constructs(self):
        from backtesting.monte_carlo import MonteCarloSimulator
        simulator = MonteCarloSimulator(initial_capital=10000.0)
        self.assertIsNotNone(simulator)

    def test_walk_forward_imports_and_constructs(self):
        from backtesting.walk_forward import WalkForwardAnalyzer
        from backtesting.backtester import Backtester
        backtester = Backtester(initial_capital=10000.0)
        analyzer = WalkForwardAnalyzer(backtester)
        self.assertIsNotNone(analyzer)

    def test_typing_optional_imported(self):
        """typing.Optional must be imported in monte_carlo for pre-3.14 pythons."""
        import backtesting.monte_carlo as mc
        self.assertIn('Optional', mc.__dict__)


if __name__ == '__main__':
    unittest.main()