"""
订单管理器
管理订单的生命周期
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

from .models import Order, OrderSide, OrderType, OrderStatus, Trade
from .simulator import SimulatedBroker


class OrderManager:
    """订单管理器
    
    管理订单的创建、提交、撤销和查询。
    """

    def __init__(self, broker: SimulatedBroker):
        """
        初始化订单管理器
        
        Args:
            broker: 模拟券商实例
        """
        self.broker = broker
        self.logger = logging.getLogger('OrderManager')

    def create_buy_order(
        self,
        stock_code: str,
        stock_name: str,
        quantity: int,
        price: float = 0,
        order_type: OrderType = OrderType.MARKET,
        strategy_name: str = ""
    ) -> Optional[Order]:
        """
        创建买入订单
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            quantity: 数量
            price: 价格（限价单时有效）
            order_type: 订单类型
            strategy_name: 策略名称
            
        Returns:
            订单对象
        """
        return self.broker.submit_order(
            stock_code=stock_code,
            stock_name=stock_name,
            side=OrderSide.BUY,
            quantity=quantity,
            price=price,
            order_type=order_type,
            strategy_name=strategy_name
        )

    def create_sell_order(
        self,
        stock_code: str,
        stock_name: str,
        quantity: int,
        price: float = 0,
        order_type: OrderType = OrderType.MARKET,
        strategy_name: str = ""
    ) -> Optional[Order]:
        """
        创建卖出订单
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            quantity: 数量
            price: 价格（限价单时有效）
            order_type: 订单类型
            strategy_name: 策略名称
            
        Returns:
            订单对象
        """
        return self.broker.submit_order(
            stock_code=stock_code,
            stock_name=stock_name,
            side=OrderSide.SELL,
            quantity=quantity,
            price=price,
            order_type=order_type,
            strategy_name=strategy_name
        )

    def cancel_order(self, order_id: str) -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            是否取消成功
        """
        return self.broker.cancel_order(order_id)

    def get_order(self, order_id: str) -> Optional[Order]:
        """
        获取订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            订单对象
        """
        return self.broker.orders.get(order_id)

    def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        stock_code: Optional[str] = None,
        strategy_name: Optional[str] = None
    ) -> List[Order]:
        """
        获取订单列表
        
        Args:
            status: 筛选状态
            stock_code: 筛选股票代码
            strategy_name: 筛选策略名称
            
        Returns:
            订单列表
        """
        orders = self.broker.get_orders(status)
        
        if stock_code:
            orders = [o for o in orders if o.stock_code == stock_code]
        
        if strategy_name:
            orders = [o for o in orders if o.strategy_name == strategy_name]
        
        return orders

    def get_active_orders(self) -> List[Order]:
        """获取活跃订单"""
        return [
            o for o in self.broker.get_orders()
            if o.is_active
        ]

    def get_filled_orders(self) -> List[Order]:
        """获取已成交订单"""
        return self.broker.get_orders(OrderStatus.FILLED)

    def get_trades(self) -> List[Trade]:
        """获取成交记录"""
        return self.broker.get_trades()

    def get_order_summary(self) -> Dict:
        """
        获取订单摘要
        
        Returns:
            订单摘要字典
        """
        orders = self.broker.get_orders()
        
        # 统计各状态订单数量
        status_counts = {}
        for status in OrderStatus:
            status_counts[status.value] = 0
        
        for order in orders:
            status_counts[order.status.value] += 1
        
        # 统计各方向订单数量
        buy_count = sum(1 for o in orders if o.is_buy)
        sell_count = sum(1 for o in orders if o.is_sell)
        
        # 计算成交金额
        total_buy_amount = sum(
            o.filled_amount for o in orders
            if o.is_buy and o.is_filled
        )
        total_sell_amount = sum(
            o.filled_amount for o in orders
            if o.is_sell and o.is_filled
        )
        
        return {
            'total_orders': len(orders),
            'status_counts': status_counts,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'total_buy_amount': total_buy_amount,
            'total_sell_amount': total_sell_amount,
            'trades_count': len(self.broker.trades)
        }
