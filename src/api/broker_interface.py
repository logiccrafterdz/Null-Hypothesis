"""
Unified Broker Interface for Null Hypothesis Trading System
Provides a unified interface for MetaTrader 5 trading platform.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger()


@dataclass
class AssetInfo:
    """Asset information."""
    symbol: str
    broker: str
    asset_type: str
    tick_size: float
    tick_value: float
    lot_size: float
    contract_size: float


@dataclass
class Order:
    """Order information."""
    order_id: str
    symbol: str
    direction: str  # 'BUY' or 'SELL'
    order_type: str  # 'MARKET' or 'PENDING'
    price: float
    size: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: str = 'PENDING'
    timestamp: datetime = None


@dataclass
class Position:
    """Position information."""
    position_id: str
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    current_price: float
    size: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_pnl: float = 0.0
    open_time: datetime = None


@dataclass
class AccountInfo:
    """Account information."""
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    open_positions: int
    total_trades: int


class BrokerInterface(ABC):
    """Abstract base class for broker interfaces."""
    
    def __init__(self, credentials: Dict[str, str]):
        """
        Initialize broker interface.
        
        Args:
            credentials: Broker credentials
        """
        self.credentials = credentials
        self.connected = False
        self.logger = get_logger()
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to broker.
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from broker.
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if connected to broker.
        
        Returns:
            True if connected
        """
        pass
    
    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """
        Get account information.
        
        Returns:
            AccountInfo object
        """
        pass
    
    @abstractmethod
    def get_asset_info(self, symbol: str) -> AssetInfo:
        """
        Get asset information.
        
        Args:
            symbol: Asset symbol
            
        Returns:
            AssetInfo object
        """
        pass
    
    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data.
        
        Args:
            symbol: Asset symbol
            timeframe: Timeframe (e.g., 'M5', 'M15', 'H1')
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame with OHLCV data
        """
        pass
    
    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """
        Get current price for symbol.
        
        Args:
            symbol: Asset symbol
            
        Returns:
            Current price
        """
        pass
    
    @abstractmethod
    def place_order(self, order: Order) -> str:
        """
        Place order.
        
        Args:
            order: Order object
            
        Returns:
            Order ID
        """
        pass
    
    @abstractmethod
    def modify_order(
        self,
        order_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """
        Modify existing order.
        
        Args:
            order_id: Order ID
            stop_loss: New stop loss price
            take_profit: New take profit price
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_open_positions(self) -> List[Position]:
        """
        Get all open positions.
        
        Returns:
            List of Position objects
        """
        pass
    
    @abstractmethod
    def close_position(self, position_id: str) -> bool:
        """
        Close position.
        
        Args:
            position_id: Position ID
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_position_pnl(self, position_id: str) -> float:
        """
        Get position PnL.
        
        Args:
            position_id: Position ID
            
        Returns:
            PnL value
        """
        pass


class BrokerFactory:
    """Factory for creating broker instances."""
    
    @staticmethod
    def create_broker(broker_type: str, credentials: Dict[str, str]) -> BrokerInterface:
        """
        Create broker instance based on type.
        
        Args:
            broker_type: Broker type ('mt5')
            credentials: Broker credentials
            
        Returns:
            BrokerInterface instance
        """
        if broker_type == 'mt5':
            from src.api.mt5_connector import MT5Connector
            return MT5Connector(credentials)
        else:
            raise ValueError(f"Unknown broker type: {broker_type}. Supported: 'mt5'")


class UnifiedBroker:
    """
    Unified broker interface that manages multiple broker connections.
    Provides a single interface for trading across different platforms.
    """
    
    def __init__(self):
        """Initialize unified broker."""
        self.brokers: Dict[str, BrokerInterface] = {}
        self.asset_mapping: Dict[str, str] = {}  # symbol -> broker_type
        self.logger = get_logger()
    
    def add_broker(self, broker_type: str, credentials: Dict[str, str]) -> bool:
        """
        Add broker connection.
        
        Args:
            broker_type: Broker type
            credentials: Broker credentials
            
        Returns:
            True if successful
        """
        try:
            broker = BrokerFactory.create_broker(broker_type, credentials)
            if broker.connect():
                self.brokers[broker_type] = broker
                self.logger.info(f"Connected to {broker_type} broker")
                return True
            else:
                self.logger.error(f"Failed to connect to {broker_type} broker")
                return False
        except Exception as e:
            self.logger.error(f"Error adding broker: {e}")
            return False
    
    def remove_broker(self, broker_type: str) -> bool:
        """
        Remove broker connection.
        
        Args:
            broker_type: Broker type
            
        Returns:
            True if successful
        """
        if broker_type in self.brokers:
            self.brokers[broker_type].disconnect()
            del self.brokers[broker_type]
            self.logger.info(f"Disconnected from {broker_type} broker")
            return True
        return False
    
    def map_asset_to_broker(self, symbol: str, broker_type: str) -> None:
        """
        Map asset to specific broker.
        
        Args:
            symbol: Asset symbol
            broker_type: Broker type
        """
        self.asset_mapping[symbol] = broker_type
    
    def get_broker_for_asset(self, symbol: str) -> Optional[BrokerInterface]:
        """
        Get broker instance for asset.
        
        Args:
            symbol: Asset symbol
            
        Returns:
            BrokerInterface instance or None
        """
        broker_type = self.asset_mapping.get(symbol)
        if broker_type:
            if broker_type in self.brokers:
                return self.brokers[broker_type]
            self.logger.warning(
                f"Symbol {symbol} mapped to '{broker_type}' but that broker is not connected"
            )
            return None

        # No explicit mapping: default to the single connected broker so a
        # fresh install with one MT5 account works without configuration.
        if len(self.brokers) == 1:
            return next(iter(self.brokers.values()))

        if len(self.brokers) > 1:
            self.logger.warning(
                f"Symbol {symbol} has no broker mapping and multiple brokers "
                f"are connected; call map_asset_to_broker() explicitly"
            )

        return None
    
    def is_connected(self) -> bool:
        """
        Check if any broker is connected.
        
        Returns:
            True if at least one broker is connected
        """
        return any(broker.is_connected() for broker in self.brokers.values())
    
    def disconnect_all(self) -> None:
        """Disconnect all brokers."""
        for broker_type, broker in self.brokers.items():
            broker.disconnect()
            self.logger.info(f"Disconnected from {broker_type}")
        self.brokers.clear()
        self.asset_mapping.clear()
