"""
自动订单管理器
管理订单的创建、执行和监控
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable
from collections import defaultdict

from .base_broker import (
    BaseBroker, Order, OrderSide, OrderType, OrderStatus,
    Position, Account
)


class AutoOrderManager:
    """自动订单管理器
    
    功能：
    1. 创建和提交订单
    2. 订单状态跟踪
    3. 订单历史记录
    4. 批量订单管理
    5. 订单回调通知
    """

    def __init__(self, broker: BaseBroker):
        """
        初始化订单管理器
        
        Args:
            broker: 交易接口实例
        """
        self.broker = broker
        self.logger = logging.getLogger('AutoOrderManager')
        
        # 订单存储
        self.orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []
        
        # 回调函数
        self.on_order_filled: Optional[Callable] = None
        self.on_order_failed: Optional[Callable] = None
        self.on_order_cancelled: Optional[Callable] = None
        
        # 统计
        self.stats = {
            'total_orders': 0,
            'filled_orders': 0,
            'failed_orders': 0,
            'cancelled_orders': 0,
            'total_buy_amount': 0,
            'total_sell_amount': 0,
            'total_commission': 0,
            'total_tax': 0
        }

    def create_buy_order(
        self,
        stock_code: str,
        stock_name: str,
        price: float,
        quantity: int,
        order_type: OrderType = OrderType.MARKET
    ) -> Order:
        """
        创建买入订单
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            price: 价格
            quantity: 数量
            order_type: 订单类型
            
        Returns:
            订单对象
        """
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

    def create_sell_order(
        self,
        stock_code: str,
        price: float,
        quantity: int,
        order_type: OrderType = OrderType.MARKET
    ) -> Order:
        """
        创建卖出订单
        
        Args:
            stock_code: 股票代码
            price: 价格
            quantity: 数量
            order_type: 订单类型
            
        Returns:
            订单对象
        """
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

    def submit_order(self, order: Order) -> Order:
        """
        提交订单
        
        Args:
            order: 订单对象
            
        Returns:
            更新后的订单对象
        """
        # 提交到券商
        result = self.broker.submit_order(order)
        
        # 保存订单
        self.orders[order.order_id] = order
        self.order_history.append(order)
        
        # 更新统计
        self.stats['total_orders'] += 1
        
        if result.status == OrderStatus.FILLED:
            self._on_order_filled(result)
        elif result.status == OrderStatus.FAILED:
            self._on_order_failed(result)
        
        return result

    def cancel_order(self, order_id: str) -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            是否成功
        """
        order = self.orders.get(order_id)
        if not order:
            return False
        
        result = self.broker.cancel_order(order_id)
        
        if result:
            order.status = OrderStatus.CANCELLED
            self.stats['cancelled_orders'] += 1
            
            if self.on_order_cancelled:
                self.on_order_cancelled(order)
        
        return result

    def _on_order_filled(self, order: Order):
        """订单成交回调"""
        self.stats['filled_orders'] += 1
        
        if order.is_buy:
            self.stats['total_buy_amount'] += order.filled_amount
        else:
            self.stats['total_sell_amount'] += order.filled_amount
        
        self.stats['total_commission'] += order.commission
        self.stats['total_tax'] += order.tax
        
        if self.on_order_filled:
            self.on_order_filled(order)

    def _on_order_failed(self, order: Order):
        """订单失败回调"""
        self.stats['failed_orders'] += 1
        
        if self.on_order_failed:
            self.on_order_failed(order)

    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单"""
        return self.orders.get(order_id)

    def get_orders(self, status: Optional[OrderStatus] = None) -> List[Order]:
        """
        获取订单列表
        
        Args:
            status: 筛选状态
            
        Returns:
            订单列表
        """
        if status:
            return [o for o in self.orders.values() if o.status == status]
        return list(self.orders.values())

    def get_filled_orders(self) -> List[Order]:
        """获取已成交订单"""
        return self.get_orders(OrderStatus.FILLED)

    def get_pending_orders(self) -> List[Order]:
        """获取待处理订单"""
        return self.get_orders(OrderStatus.PENDING) + self.get_orders(OrderStatus.SUBMITTED)

    def get_account(self) -> Account:
        """获取账户信息"""
        return self.broker.get_account()

    def get_positions(self) -> List[Position]:
        """获取持仓"""
        return self.broker.get_positions()

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            'pending_orders': len(self.get_pending_orders()),
            'account': self.broker.get_account().to_dict() if hasattr(self.broker.get_account(), 'to_dict') else {}
        }

    def format_statistics(self) -> str:
        """格式化统计信息"""
        stats = self.get_statistics()
        
        return f"""
订单统计:
  总订单数: {stats['total_orders']}
  已成交: {stats['filled_orders']}
  失败: {stats['failed_orders']}
  已取消: {stats['cancelled_orders']}
  待处理: {stats['pending_orders']}

交易统计:
  买入金额: {stats['total_buy_amount']:,.2f}
  卖出金额: {stats['total_sell_amount']:,.2f}
  佣金: {stats['total_commission']:,.2f}
  印花税: {stats['total_tax']:,.2f}
"""
