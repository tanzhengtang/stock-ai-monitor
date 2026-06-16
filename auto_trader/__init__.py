"""
自动交易模块
支持多种交易接口：模拟盘、easytrader、QMT
"""

from .base_broker import BaseBroker, Order, OrderSide, OrderStatus
from .simulator_broker import SimulatorBroker
from .easytrader_broker import EasyTraderBroker
from .qmt_broker import QMTBroker
from .order_manager import AutoOrderManager
from .risk_controller import RiskController

__all__ = [
    'BaseBroker',
    'Order',
    'OrderSide',
    'OrderStatus',
    'SimulatorBroker',
    'EasyTraderBroker',
    'QMTBroker',
    'AutoOrderManager',
    'RiskController'
]
