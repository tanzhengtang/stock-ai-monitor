"""
模拟交易接口
用于测试和验证策略
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from .base_broker import (
    BaseBroker, Order, OrderSide, OrderType, OrderStatus,
    Position, Account
)


class SimulatorBroker(BaseBroker):
    """模拟券商
    
    特点：
    - 无需真实券商账号
    - 模拟真实交易流程
    - 支持佣金和印花税计算
    - 适合策略验证和测试
    """

    def __init__(
        self,
        initial_capital: float = 1000000,
        commission_rate: float = 0.0003,
        min_commission: float = 5,
        tax_rate: float = 0.001,
        slippage: float = 0.001
    ):
        super().__init__("Simulator")
        
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.tax_rate = tax_rate
        self.slippage = slippage
        
        # 账户
        self.account = Account(
            account_id="SIM_001",
            cash=initial_capital
        )
        
        # 订单记录
        self.orders: Dict[str, Order] = {}
        
        # 价格回调（用于获取实时价格）
        self.price_callback = None

    def connect(self, **kwargs) -> bool:
        """连接（模拟总是成功）"""
        self.connected = True
        self.logger.info("模拟券商已连接")
        return True

    def disconnect(self):
        """断开连接"""
        self.connected = False
        self.logger.info("模拟券商已断开")

    def set_price_callback(self, callback):
        """设置价格回调函数"""
        self.price_callback = callback

    def get_account(self) -> Account:
        """获取账户信息"""
        self.account.update_assets()
        return self.account

    def get_positions(self) -> List[Position]:
        """获取持仓"""
        return list(self.account.positions.values())

    def get_current_price(self, stock_code: str) -> float:
        """获取当前价格"""
        if self.price_callback:
            return self.price_callback(stock_code)
        
        # 如果有持仓，返回持仓中的价格
        if stock_code in self.account.positions:
            return self.account.positions[stock_code].current_price
        
        return 0

    def submit_order(self, order: Order) -> Order:
        """提交订单"""
        if not self.connected:
            order.status = OrderStatus.FAILED
            order.remark = "未连接"
            return order
        
        # 获取当前价格
        current_price = self.get_current_price(order.stock_code)
        if current_price <= 0:
            current_price = order.price
        
        if current_price <= 0:
            order.status = OrderStatus.REJECTED
            order.remark = "无法获取价格"
            return order
        
        # 计算滑点
        if order.is_buy:
            exec_price = current_price * (1 + self.slippage)
        else:
            exec_price = current_price * (1 - self.slippage)
        
        # 检查资金/持仓
        if order.is_buy:
            required = exec_price * order.quantity
            commission = max(required * self.commission_rate, self.min_commission)
            if required + commission > self.account.cash:
                order.status = OrderStatus.REJECTED
                order.remark = f"资金不足"
                return order
        else:
            position = self.account.positions.get(order.stock_code)
            if not position:
                order.status = OrderStatus.REJECTED
                order.remark = f"没有持仓"
                return order
            # T+1: 检查可卖数量
            if position.available_quantity < order.quantity:
                order.status = OrderStatus.REJECTED
                order.remark = f"T+1限制: 可卖{position.available_quantity}股, 欲卖{order.quantity}股"
                return order
        
        # 执行订单
        order.price = exec_price
        order.filled_quantity = order.quantity
        order.filled_price = exec_price
        order.status = OrderStatus.FILLED
        order.updated_time = datetime.now()
        
        # 计算费用
        amount = exec_price * order.quantity
        order.commission = max(amount * self.commission_rate, self.min_commission)
        if order.is_sell:
            order.tax = amount * self.tax_rate
        
        # 更新账户
        if order.is_buy:
            self._process_buy(order)
        else:
            self._process_sell(order)
        
        self.orders[order.order_id] = order
        self.logger.info(f"订单成交: {order.side.value} {order.stock_code} {order.quantity}股 @ {exec_price:.2f}")
        
        return order

    def _process_buy(self, order: Order):
        """处理买入"""
        amount = order.filled_amount + order.commission
        self.account.cash -= amount
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        if order.stock_code in self.account.positions:
            pos = self.account.positions[order.stock_code]
            total_qty = pos.quantity + order.quantity
            total_cost = pos.avg_cost * pos.quantity + order.filled_price * order.quantity
            pos.avg_cost = total_cost / total_qty
            pos.quantity = total_qty
            # T+1: 今日买入不可卖
            # available_quantity 不变，只有之前的部分可卖
        else:
            self.account.positions[order.stock_code] = Position(
                stock_code=order.stock_code,
                stock_name=order.stock_name,
                quantity=order.quantity,
                avg_cost=order.filled_price,
                current_price=order.filled_price,
                available_quantity=0,  # T+1: 今日买入不可卖
                buy_date=today
            )
        
        self.account.update_assets()

    def _process_sell(self, order: Order):
        """处理卖出"""
        amount = order.filled_amount - order.commission - order.tax
        self.account.cash += amount
        
        pos = self.account.positions.get(order.stock_code)
        if pos:
            pos.quantity -= order.quantity
            pos.available_quantity -= order.quantity
            if pos.quantity <= 0:
                del self.account.positions[order.stock_code]
        
        self.account.update_assets()

    def update_available_quantity(self):
        """
        更新可卖数量（T+1）
        每日开盘时调用，将所有持仓的可卖数量设为总数量
        """
        for pos in self.account.positions.values():
            # 所有历史持仓都可以卖出
            pos.available_quantity = pos.quantity

    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                order.status = OrderStatus.CANCELLED
                return True
        return False

    def query_order(self, order_id: str) -> Optional[Order]:
        """查询订单"""
        return self.orders.get(order_id)
