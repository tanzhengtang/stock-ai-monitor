"""
交易接口基类
定义所有交易接口的通用接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import logging


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"    # 市价单
    LIMIT = "limit"      # 限价单


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"          # 待提交
    SUBMITTED = "submitted"      # 已提交
    FILLED = "filled"            # 已成交
    PARTIAL = "partial"          # 部分成交
    CANCELLED = "cancelled"      # 已取消
    REJECTED = "rejected"        # 已拒绝
    FAILED = "failed"            # 失败


@dataclass
class Order:
    """订单"""
    order_id: str
    stock_code: str
    stock_name: str
    side: OrderSide
    price: float
    quantity: int
    order_type: OrderType = OrderType.MARKET
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    filled_price: float = 0
    commission: float = 0
    tax: float = 0
    created_time: datetime = field(default_factory=datetime.now)
    updated_time: datetime = field(default_factory=datetime.now)
    remark: str = ""
    broker_order_id: str = ""  # 券商订单ID

    @property
    def amount(self) -> float:
        return self.price * self.quantity

    @property
    def filled_amount(self) -> float:
        return self.filled_price * self.filled_quantity

    @property
    def is_buy(self) -> bool:
        return self.side == OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        return self.side == OrderSide.SELL

    def to_dict(self) -> Dict:
        return {
            'order_id': self.order_id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'side': self.side.value,
            'price': self.price,
            'quantity': self.quantity,
            'order_type': self.order_type.value,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'commission': self.commission,
            'tax': self.tax,
            'created_time': self.created_time.isoformat(),
            'remark': self.remark
        }


@dataclass
class Position:
    """持仓"""
    stock_code: str
    stock_name: str
    quantity: int
    avg_cost: float
    current_price: float = 0
    market_value: float = 0
    unrealized_pnl: float = 0
    unrealized_pnl_pct: float = 0
    available_quantity: int = 0  # 可卖数量（T+1限制）
    buy_date: str = ""  # 买入日期

    def update_price(self, price: float):
        self.current_price = price
        self.market_value = self.quantity * price
        if self.avg_cost > 0:
            self.unrealized_pnl = (price - self.avg_cost) * self.quantity
            self.unrealized_pnl_pct = (price - self.avg_cost) / self.avg_cost * 100


@dataclass
class Account:
    """账户"""
    account_id: str
    cash: float
    frozen_cash: float = 0
    market_value: float = 0
    total_assets: float = 0
    positions: Dict[str, Position] = field(default_factory=dict)

    def update_assets(self):
        self.market_value = sum(p.market_value for p in self.positions.values())
        self.total_assets = self.cash + self.frozen_cash + self.market_value


class BaseBroker(ABC):
    """交易接口基类"""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f'Broker.{name}')
        self.connected = False

    @abstractmethod
    def connect(self, **kwargs) -> bool:
        """连接交易接口"""
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    def get_account(self) -> Account:
        """获取账户信息"""
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """获取持仓"""
        pass

    @abstractmethod
    def get_current_price(self, stock_code: str) -> float:
        """获取当前价格"""
        pass

    @abstractmethod
    def submit_order(self, order: Order) -> Order:
        """提交订单"""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        pass

    @abstractmethod
    def query_order(self, order_id: str) -> Optional[Order]:
        """查询订单状态"""
        pass

    def buy(
        self,
        stock_code: str,
        stock_name: str,
        price: float,
        quantity: int,
        order_type: OrderType = OrderType.MARKET
    ) -> Order:
        """买入"""
        import uuid
        order = Order(
            order_id=f"ORD_{uuid.uuid4().hex[:8].upper()}",
            stock_code=stock_code,
            stock_name=stock_name,
            side=OrderSide.BUY,
            price=price,
            quantity=quantity,
            order_type=order_type
        )
        return self.submit_order(order)

    def sell(
        self,
        stock_code: str,
        price: float,
        quantity: int,
        order_type: OrderType = OrderType.MARKET
    ) -> Order:
        """卖出"""
        import uuid
        order = Order(
            order_id=f"ORD_{uuid.uuid4().hex[:8].upper()}",
            stock_code=stock_code,
            stock_name="",
            side=OrderSide.SELL,
            price=price,
            quantity=quantity,
            order_type=order_type
        )
        return self.submit_order(order)

    def is_connected(self) -> bool:
        """是否已连接"""
        return self.connected
