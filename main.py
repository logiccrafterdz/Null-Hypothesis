"""
Main Entry Point for Phoenix Protocol Trading System
Coordinates all components and runs the trading bot.
"""

import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import ASSETS, TIMEFRAMES
from src.api.broker_interface import UnifiedBroker
from src.core.data_fetcher import DataFetcher
from src.core.risk_manager import RiskManager
from src.core.trade_executor import TradeExecutor
from src.strategies.bad_luck_strategy import BadLuckStrategy
from src.utils.logger import get_logger
from config.credentials import get_mt5_credentials


def setup_system():
    """
    Setup and initialize all system components.
    
    Returns:
        Dictionary with initialized components
    """
    logger = get_logger()
    logger.info("Initializing Phoenix Protocol Trading System")
    
    # Initialize unified broker
    unified_broker = UnifiedBroker()
    
    # Add MT5 connection if credentials available
    mt5_creds = get_mt5_credentials()
    if mt5_creds.get('login') and mt5_creds.get('password'):
        unified_broker.add_broker('mt5', mt5_creds)
        
        # Map forex assets to MT5
        for asset, config in ASSETS.items():
            if config.get('broker') == 'mt5':
                unified_broker.map_asset_to_broker(asset, 'mt5')
    
    # Initialize core components
    data_fetcher = DataFetcher(unified_broker)
    risk_manager = RiskManager()
    trade_executor = TradeExecutor(unified_broker, risk_manager)
    
    # Initialize strategy
    strategy = BadLuckStrategy(
        unified_broker=unified_broker,
        data_fetcher=data_fetcher,
        risk_manager=risk_manager,
        trade_executor=trade_executor
    )
    
    logger.info("System initialization complete")
    
    return {
        'unified_broker': unified_broker,
        'data_fetcher': data_fetcher,
        'risk_manager': risk_manager,
        'trade_executor': trade_executor,
        'strategy': strategy
    }


def run_backtest_mode(components: dict, args):
    """
    Run backtesting mode.
    
    Args:
        components: System components
        args: Command line arguments
    """
    logger = get_logger()
    logger.info("Starting backtesting mode")
    
    from backtesting.backtester import Backtester
    from backtesting.walk_forward import WalkForwardAnalyzer
    from backtesting.monte_carlo import MonteCarloSimulator
    
    data_fetcher = components['data_fetcher']
    
    # Get data for backtesting
    asset = args.asset or list(ASSETS.keys())[0]
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    
    logger.info(f"Fetching data for {asset} from {start_date} to {end_date}")
    try:
        data = data_fetcher.get_data(asset, TIMEFRAMES['main'], start_date, end_date)
    except ValueError as e:
        logger.error(str(e))
        print(f"\nERROR: {e}", file=sys.stderr)
        return
    
    if data.empty:
        logger.error("No data available for backtesting")
        return
    
    # Run backtest
    backtester = Backtester(initial_capital=args.capital)
    result = backtester.run_backtest(data, asset, start_date, end_date)
    
    # Print results
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    print(f"Status: {result.status.value}")
    print(f"Total Trades: {result.total_trades}")
    print(f"Win Rate: {result.win_rate:.2%}")
    print(f"Profit Factor: {result.profit_factor:.2f}")
    print(f"Total Return: {result.total_return_pct:.2%}")
    print(f"Max Drawdown: {result.max_drawdown_pct:.2%}")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print("=" * 80)
    
    # Check success criteria
    criteria_check = backtester.check_success_criteria(result)
    print("\nSuccess Criteria Check:")
    for criterion, passed in criteria_check.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {criterion}: {passed}")
    
    # Run walk-forward if requested
    if args.walk_forward:
        logger.info("Running walk-forward analysis")
        walk_forward_analyzer = WalkForwardAnalyzer(backtester)
        wf_result = walk_forward_analyzer.run_walk_forward(data, asset, start_date, end_date)
        print(walk_forward_analyzer.generate_report(wf_result))
    
    # Run Monte Carlo if requested
    if args.monte_carlo:
        logger.info("Running Monte Carlo simulation")
        monte_carlo = MonteCarloSimulator(initial_capital=args.capital)
        mc_result = monte_carlo.run_simulation(result.trades)
        print(monte_carlo.generate_report(mc_result))


def run_live_mode(components: dict, args):
    """
    Run live trading mode.
    
    Args:
        components: System components
        args: Command line arguments
    """
    logger = get_logger()
    logger.info("Starting live trading mode")
    
    unified_broker = components['unified_broker']
    strategy = components['strategy']
    
    if not unified_broker.is_connected():
        logger.error("No broker connection available")
        return
    
    # Get account info
    broker = unified_broker.get_broker_for_asset(list(ASSETS.keys())[0])
    if broker:
        account_info = broker.get_account_info()
        logger.info(f"Account Balance: {account_info.balance:.2f}")
        logger.info(f"Account Equity: {account_info.equity:.2f}")
    
    # Main trading loop
    import time
    assets_to_trade = args.assets or list(ASSETS.keys())
    
    logger.info(f"Trading assets: {assets_to_trade}")
    
    try:
        while True:
            for asset in assets_to_trade:
                try:
                    if broker:
                        account_info = broker.get_account_info()
                        strategy.process_asset(asset, account_info)
                except Exception as e:
                    logger.error(f"Error processing {asset}: {e}")
            
            # Monitor positions
            trades_to_close = components['trade_executor'].monitor_positions()
            for trade, reason in trades_to_close:
                current_price = broker.get_current_price(trade.asset) if broker else trade.entry_price
                components['trade_executor'].close_trade(trade, current_price, reason)
            
            # Wait for next cycle
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        logger.info("Shutting down live trading")
        components['trade_executor'].close_all_trades("Manual Shutdown")
        unified_broker.disconnect_all()


def run_dashboard_mode(components: dict, args):
    """
    Run dashboard mode.
    
    Args:
        components: System components
        args: Command line arguments
    """
    logger = get_logger()
    logger.info("Starting dashboard mode")
    
    import subprocess
    import sys
    
    # Run Streamlit dashboard
    dashboard_path = Path(__file__).parent / "dashboard" / "app.py"
    
    if not dashboard_path.exists():
        logger.error(f"Dashboard not found at {dashboard_path}")
        return
    
    logger.info(f"Launching dashboard from {dashboard_path}")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard_path)])


def generate_sample_data_mode(components: dict, args):
    """
    Generate synthetic OHLCV data into the local data cache.

    Args:
        components: System components
        args: Command line arguments
    """
    logger = get_logger()
    data_fetcher = components['data_fetcher']

    asset = args.asset or list(ASSETS.keys())[0]
    timeframe = args.timeframe or TIMEFRAMES['main']
    days = args.sample_days

    from src.utils.helpers import generate_sample_data
    df = generate_sample_data(
        asset=asset,
        days=days,
        timeframe=timeframe,
        seed=args.sample_seed
    )

    saved = data_fetcher.save_cached_data(df, asset, timeframe, "raw")
    if saved:
        path = data_fetcher.get_data_path(asset, timeframe, "raw")
        logger.info(f"Generated {len(df)} sample candles for {asset} {timeframe}")
        print(f"Sample data saved: {path}")
    else:
        logger.error("Failed to save sample data")
    return saved


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Phoenix Protocol Trading System")
    
    # Mode selection
    parser.add_argument(
        '--mode',
        choices=['backtest', 'live', 'dashboard'],
        default='backtest',
        help='Operation mode'
    )
    
    # Backtesting arguments
    parser.add_argument('--asset', help='Asset to backtest')
    parser.add_argument('--days', type=int, default=365, help='Days of data to backtest')
    parser.add_argument('--capital', type=float, default=10000, help='Initial capital')
    parser.add_argument('--walk-forward', action='store_true', help='Run walk-forward analysis')
    parser.add_argument('--monte-carlo', action='store_true', help='Run Monte Carlo simulation')
    
    # Live trading arguments
    parser.add_argument('--assets', nargs='+', help='Assets to trade')
    parser.add_argument('--interval', type=int, default=60, help='Trading interval in seconds')
    
    # Local data fixtures
    parser.add_argument(
        '--generate-sample-data',
        action='store_true',
        help='Generate synthetic OHLCV data into the local data cache and exit'
    )
    parser.add_argument(
        '--timeframe',
        help='Timeframe for sample data generation (defaults to main timeframe)'
    )
    parser.add_argument(
        '--sample-days',
        type=int,
        default=365,
        help='Days of sample data to generate'
    )
    parser.add_argument(
        '--sample-seed',
        type=int,
        default=42,
        help='Random seed for sample data generation'
    )
    
    args = parser.parse_args()
    
    # Setup system
    components = setup_system()
    
    # Local data fixtures
    if args.generate_sample_data:
        generate_sample_data_mode(components, args)
        return
    
    # Run selected mode
    if args.mode == 'backtest':
        run_backtest_mode(components, args)
    elif args.mode == 'live':
        run_live_mode(components, args)
    elif args.mode == 'dashboard':
        run_dashboard_mode(components, args)


if __name__ == "__main__":
    main()
