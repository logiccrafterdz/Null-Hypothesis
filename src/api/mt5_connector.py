"""
MetaTrader 5 Connector for Null Hypothesis Trading System
Implements broker interface for MetaTrader 5 platform.
"""

import MetaTrader5 as mt5
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import pytz

from src.api.broker_interface import (
    BrokerInterface,
    AssetInfo,
    Order,
    Position,
    AccountInfo
)
from src.utils.logger import get_logger

logger = get_logger()


class MT5Connector(BrokerInterface):
    """MetaTrader 5 broker connector."""
    
    def __init__(self, credentials: Dict[str, str]):
        """
        Initialize MT5 connector.
        
        Args:
            credentials: MT5 credentials (login, password, server)
        """
        super().__init__(credentials)
        self.login = credentials.get('login', '')
        self.password = credentials.get('password', '')
        self.server = credentials.get('server', '')
        
        # MT5 timeframe mapping
        self.timeframe_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1,
        }
    
    def connect(self) -> bool:
        """
        Connect to MT5 terminal.
        
        Returns:
            True if successful
        """
        try:
            if not mt5.initialize():
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False
            
            if self.login and self.password and self.server:
                if not mt5.login(int(self.login), self.password, self.server):
                    logger.error(f"MT5 login failed: {mt5.last_error()}")
                    mt5.shutdown()
                    return False
            
            self.connected = True
            logger.info("MT5 connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            return False
    
    def disconnect(self) -> bool:
        """
        Disconnect from MT5 terminal.
        
        Returns:
            True if successful
        """
        try:
            mt5.shutdown()
            self.connected = False
            logger.info("MT5 disconnected")
            return True
        except Exception as e:
            logger.error(f"MT5 disconnect error: {e}")
            return False
    
    def is_connected(self) -> bool:
        """
        Check if connected to MT5.
        
        Returns:
            True if connected
        """
        return self.connected and mt5.terminal_info() is not None
    
    def get_account_info(self) -> AccountInfo:
        """
        Get MT5 account information.
        
        Returns:
            AccountInfo object
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MT5")
        
        account_info = mt5.account_info()
        if account_info is None:
            raise Exception(f"Failed to get account info: {mt5.last_error()}")
        
        return AccountInfo(
            balance=account_info.balance,
            equity=account_info.equity,
            margin=account_info.margin,
            free_margin=account_info.margin_free,
            margin_level=account_info.margin_level,
            open_positions=account_info.positions,
            total_trades=account_info.trades
        )
    
    def get_asset_info(self, symbol: str) -> AssetInfo:
        """
        Get MT5 asset information.
        
        Args:
            symbol: Asset symbol
            
        Returns:
            AssetInfo object
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MT5")
        
        tick_info = mt5.symbol_info_tick(symbol)
        symbol_info = mt5.symbol_info(symbol)
        
        if tick_info is None or symbol_info is None:
            raise Exception(f"Failed to get asset info for {symbol}")
        
        return AssetInfo(
            symbol=symbol,
            broker='mt5',
            asset_type='forex',
            tick_size=symbol_info.trade_tick_size,
            tick_value=symbol_info.trade_tick_value,
            lot_size=symbol_info.volume_min,
            contract_size=symbol_info.trade_contract_size
        )
    
    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data from MT5.
        
        Args:
            symbol: Asset symbol
            timeframe: Timeframe (e.g., 'M5', 'M15', 'H1')
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame with OHLCV data
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MT5")
        
        mt5_timeframe = self.timeframe_map.get(timeframe, mt5.TIMEFRAME_M15)
        
        # Convert to UTC for MT5
        utc = pytz.UTC
        start_date = utc.localize(start_date) if start_date.tzinfo is None else start_date.astimezone(utc)
        end_date = utc.localize(end_date) if end_date.tzinfo is None else end_date.astimezone(utc)
        
        rates = mt5.copy_rates_range(symbol, mt5_timeframe, start_date, end_date)
        
        if rates is None or len(rates) == 0:
            logger.warning(f"No data retrieved for {symbol} from {start_date} to {end_date}")
            return pd.DataFrame()
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        df.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'tick_volume': 'volume',
            'spread': 'spread',
            'real_volume': 'real_volume'
        }, inplace=True)
        
        return df[['open', 'high', 'low', 'close', 'volume']]
    
    def get_current_price(self, symbol: str) -> float:
        """
        Get current price from MT5.
        
        Args:
            symbol: Asset symbol
            
        Returns:
            Current price (bid)
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MT5")
        
        tick_info = mt5.symbol_info_tick(symbol)
        if tick_info is None:
            raise Exception(f"Failed to get price for {symbol}")
        
        return tick_info.bid
    
    def _validate_lot(
        self,
        symbol: str,
        volume: float,
        symbol_info
    ) -> float:
        """
        Validate and normalize an order volume against broker constraints.

        Args:
            symbol: Asset symbol
            volume: Requested volume in lots
            symbol_info: MT5 symbol info

        Returns:
            Volume rounded/clamped to broker lot step and limits

        Raises:
            Exception: if volume is below the broker minimum lot
        """
        if volume < symbol_info.volume_min:
            raise Exception(
                f"Volume {volume} below minimum {symbol_info.volume_min} for {symbol}"
            )
        if volume > symbol_info.volume_max:
            logger.warning(
                f"Volume {volume} above maximum {symbol_info.volume_max} for {symbol}, clamping"
            )
            volume = symbol_info.volume_max

        if symbol_info.volume_step and symbol_info.volume_step > 0:
            volume = round(volume / symbol_info.volume_step) * symbol_info.volume_step

        return volume

    def place_order(self, order: Order) -> str:
        """
        Place order on MT5.

        Args:
            order: Order object

        Returns:
            Order ID
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MT5")
        
        symbol_info = mt5.symbol_info(order.symbol)
        if symbol_info is None:
            raise Exception(f"Symbol {order.symbol} not found")
        
        volume = self._validate_lot(order.symbol, order.size, symbol_info)
        
        # Determine order type
        if order.direction == 'BUY':
            trade_type = mt5.ORDER_TYPE_BUY if order.order_type == 'MARKET' else mt5.ORDER_TYPE_BUY_LIMIT
            price = mt5.symbol_info_tick(order.symbol).ask
        else:
            trade_type = mt5.ORDER_TYPE_SELL if order.order_type == 'MARKET' else mt5.ORDER_TYPE_SELL_LIMIT
            price = mt5.symbol_info_tick(order.symbol).bid
        
        # Create order request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": volume,
            "type": trade_type,
            "price": price,
            "sl": order.stop_loss,
            "tp": order.take_profit,
            "deviation": 20,
            "magic": 234000,
            "comment": "Null Hypothesis",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Order failed: {result.retcode} - {result.comment}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        logger.info(f"Order placed successfully: {result.order}")
        return str(result.order)
    
    def modify_order(
        self,
        order_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """
        Modify existing order on MT5.
        
        Args:
            order_id: Order ID
            stop_loss: New stop loss price
            take_profit: New take profit price
            
        Returns:
            True if successful
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MT5")
        
        # Get position
        position = mt5.positions_get(ticket=int(order_id))
        if position is None or len(position) == 0:
            logger.error(f"Position {order_id} not found")
            return False
        
        position = position[0]
        
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(order_id),
            "sl": stop_loss if stop_loss is not None else position.sl,
            "tp": take_profit if take_profit is not None else position.tp,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order modification failed: {result.retcode} - {result.comment}")
            return False
        
        logger.info(f"Order {order_id} modified successfully")
        return True
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order on MT5.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if successful
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MT5")
        
        # Get order
        order = mt5.orders_get(ticket=int(order_id))
        if order is None or len(order) == 0:
            logger.error(f"Order {order_id} not found")
            return False
        
        order = order[0]
        
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": int(order_id),
            "price": order.price,
            "volume": order.volume,
            "type": order.type,
            "symbol": order.symbol,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order cancellation failed: {result.retcode} - {result.comment}")
            return False
        
        logger.info(f"Order {order_id} cancelled successfully")
        return True
    
    def get_open_positions(self) -> List[Position]:
        """
        Get all open positions from MT5.
        
        Returns:
            List of Position objects
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MT5")
        
        positions = mt5.positions_get()
        if positions is None:
            return []
        
        position_list = []
        for pos in positions:
            direction = 'LONG' if pos.type == mt5.POSITION_TYPE_BUY else 'SHORT'
            
            position = Position(
                position_id=str(pos.ticket),
                symbol=pos.symbol,
                direction=direction,
                entry_price=pos.price_open,
                current_price=pos.price_current,
                size=pos.volume,
                stop_loss=pos.sl,
                take_profit=pos.tp,
                unrealized_pnl=pos.profit,
                open_time=datetime.fromtimestamp(pos.time, pytz.UTC)
            )
            position_list.append(position)
        
        return position_list
    
    def close_position(self, position_id: str) -> bool:
        """
        Close position on MT5.
        
        Args:
            position_id: Position ID
            
        Returns:
            True if successful
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MT5")
        
        # Get position
        position = mt5.positions_get(ticket=int(position_id))
        if position is None or len(position) == 0:
            logger.error(f"Position {position_id} not found")
            return False
        
        position = position[0]
        
        # Determine close type
        if position.type == mt5.POSITION_TYPE_BUY:
            close_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(position.symbol).bid
        else:
            close_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(position.symbol).ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": close_type,
            "position": int(position_id),
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "Null Hypothesis Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Position close failed: {result.retcode} - {result.comment}")
            return False
        
        logger.info(f"Position {position_id} closed successfully")
        return True
    
    def get_position_pnl(self, position_id: str) -> float:
        """
        Get position PnL from MT5.
        
        Args:
            position_id: Position ID
            
        Returns:
            PnL value
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MT5")
        
        position = mt5.positions_get(ticket=int(position_id))
        if position is None or len(position) == 0:
            return 0.0
        
        return position[0].profit
