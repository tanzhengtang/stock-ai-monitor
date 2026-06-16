"""
量化交易数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"          # 买入
    SELL = "sell"        # 卖出


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"    # 市价单
    LIMIT = "limit"      # 限价单


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"          # 待提交
    SUBMITTED = "submitted"      # 已提交
    PARTIAL = "partial"          # 部分成交
    FILLED = "filled"            # 完全成交
    CANCELLED = "cancelled"      # 已取消
    REJECTED = "rejected"        # 已拒绝


class PositionSide(Enum):
    """持仓方向"""
    LONG = "long"        # 多头
    SHORT = "short"      # 空头（A股不支持）


@dataclass
class Order:
    """订单
    
    Attributes:
        order_id: 订单ID
        stock_code: 股票代码
        stock_name: 股票名称
        side: 买卖方向
        order_type: 订单类型
        price: 委托价格
        quantity: 委托数量
        filled_quantity: 成交数量
        filled_price: 成交均价
        status: 订单状态
        created_time: 创建时间
        updated_time: 更新时间
        strategy_name: 策略名称
        remark: 备注
    """
    order_id: str
    stock_code: str
    stock_name: str
    side: OrderSide
    order_type: OrderType
    price: float
    quantity: int
    filled_quantity: int = 0
    filled_price: float = 0
    status: OrderStatus = OrderStatus.PENDING
    created_time: datetime = field(default_factory=datetime.now)
    updated_time: datetime = field(default_factory=datetime.now)
    strategy_name: str = ""
    remark: str = ""

    @property
    def is_buy(self) -> bool:
        """是否是买入订单"""
        return self.side == OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        """是否是卖出订单"""
        return self.side == OrderSide.SELL

    @property
    def is_filled(self) -> bool:
        """是否完全成交"""
        return self.status == OrderStatus.FILLED

    @property
    def is_active(self) -> bool:
        """是否是活跃订单"""
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL]

    @property
    def amount(self) -> float:
        """订单金额"""
        return self.price * self.quantity

    @property
    def filled_amount(self) -> float:
        """成交金额"""
        return self.filled_price * self.filled_quantity

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'order_id': self.order_id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'price': self.price,
            'quantity': self.quantity,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'status': self.status.value,
            'created_time': self.created_time.isoformat(),
            'updated_time': self.updated_time.isoformat(),
            'strategy_name': self.strategy_name,
            'remark': self.remark
        }


@dataclass
class Position:
    """持仓
    
    Attributes:
        stock_code: 股票代码
        stock_name: 股票名称
        side: 持仓方向
        quantity: 持仓数量
        avg_cost: 持仓成本
        current_price: 当前价格
        market_value: 市值
        unrealized_pnl: 未实现盈亏
        unrealized_pnl_pct: 未实现盈亏百分比
        created_time: 创建时间
        updated_time: 更新时间
    """
    stock_code: str
    stock_name: str
    side: PositionSide = PositionSide.LONG
    quantity: int = 0
    avg_cost: float = 0
    current_price: float = 0
    market_value: float = 0
    unrealized_pnl: float = 0
    unrealized_pnl_pct: float = 0
    created_time: datetime = field(default_factory=datetime.now)
    updated_time: datetime = field(default_factory=datetime.now)

    def update_price(self, current_price: float):
        """更新价格和盈亏"""
        self.current_price = current_price
        self.market_value = self.quantity * current_price
        if self.quantity > 0:
            self.unrealized_pnl = (current_price - self.avg_cost) * self.quantity
            self.unrealized_pnl_pct = (current_price - self.avg_cost) / self.avg_cost * 100
        self.updated_time = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'side': self.side.value,
            'quantity': self.quantity,
            'avg_cost': self.avg_cost,
            'current_price': self.current_price,
            'market_value': self.market_value,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'created_time': self.created_time.isoformat(),
            'updated_time': self.updated_time.isoformat()
        }


@dataclass
class Trade:
    """成交记录
    
    Attributes:
        trade_id: 成交ID
        order_id: 订单ID
        stock_code: 股票代码
        stock_name: 股票名称
        side: 买卖方向
        price: 成交价格
        quantity: 成交数量
        amount: 成交金额
        commission: 佣金
        tax: 印花税
        trade_time: 成交时间
    """
    trade_id: str
    order_id: str
    stock_code: str
    stock_name: str
    side: OrderSide
    price: float
    quantity: int
    amount: float = 0
    commission: float = 0
    tax: float = 0
    trade_time: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """计算成交金额"""
        if self.amount == 0:
            self.amount = self.price * self.quantity

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'trade_id': self.trade_id,
            'order_id': self.order_id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'side': self.side.value,
            'price': self.price,
            'quantity': self.quantity,
            'amount': self.amount,
            'commission': self.commission,
            'tax': self.tax,
            'trade_time': self.trade_time.isoformat()
        }


@dataclass
class Account:
    """账户
    
    Attributes:
        account_id: 账户ID
        initial_capital: 初始资金
        cash: 可用资金
        frozen_cash: 冻结资金
        market_value: 持仓市值
        total_assets: 总资产
        total_pnl: 总盈亏
        daily_pnl: 当日盈亏
        commission: 总佣金
        tax: 总印花税
        positions: 持仓列表
        created_time: 创建时间
        updated_time: 更新时间
    """
    account_id: str
    initial_capital: float
    cash: float
    frozen_cash: float = 0
    market_value: float = 0
    total_assets: float = 0
    total_pnl: float = 0
    daily_pnl: float = 0
    commission: float = 0
    tax: float = 0
    positions: Dict[str, Position] = field(default_factory=dict)
    created_time: datetime = field(default_factory=datetime.now)
    updated_time: datetime = field(default_factory=datetime.now)

    def update_assets(self):
        """更新资产"""
        self.market_value = sum(p.market_value for p in self.positions.values())
        self.total_assets = self.cash + self.frozen_cash + self.market_value
        self.total_pnl = self.total_assets - self.initial_capital
        self.updated_time = datetime.now()

    def get_position(self, stock_code: str) -> Optional[Position]:
        """获取持仓"""
        return self.positions.get(stock_code)

    def add_position(self, position: Position):
        """添加持仓"""
        self.positions[position.stock_code] = position

    def remove_position(self, stock_code: str):
        """移除持仓"""
        self.positions.pop(stock_code, None)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'account_id': self.account_id,
            'initial_capital': self.initial_capital,
            'cash': self.cash,
            'frozen_cash': self.frozen_cash,
            'market_value': self.market_value,
            'total_assets': self.total_assets,
            'total_pnl': self.total_pnl,
            'daily_pnl': self.daily_pnl,
            'commission': self.commission,
            'tax': self.tax,
            'positions': {code: pos.to_dict() for code, pos in self.positions.items()},
            'created_time': self.created_time.isoformat(),
            'updated_time': self.updated_time.isoformat()
        }
