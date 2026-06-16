"""
模拟交易引擎
提供模拟交易环境，用于测试策略
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable

from .models import (
    Order, OrderSide, OrderType, OrderStatus,
    Position, PositionSide, Account, Trade
)


class SimulatedBroker:
    """模拟券商
    
    提供模拟交易环境，支持：
    - 市价单和限价单
    - 佣金和印花税计算
    - 持仓管理
    - 账户资产计算
    """

    def __init__(
        self,
        initial_capital: float = 1000000,
        commission_rate: float = 0.0003,  # 佣金费率万分之三
        min_commission: float = 5,         # 最低佣金5元
        tax_rate: float = 0.001,           # 印花税千分之一（仅卖出）
        slippage: float = 0.001            # 滑点千分之一
    ):
        """
        初始化模拟券商
        
        Args:
            initial_capital: 初始资金
            commission_rate: 佣金费率
            min_commission: 最低佣金
            tax_rate: 印花税费率（仅卖出收取）
            slippage: 滑点比例
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.tax_rate = tax_rate
        self.slippage = slippage
        
        # 创建账户
        self.account = Account(
            account_id="SIM_001",
            initial_capital=initial_capital,
            cash=initial_capital
        )
        
        # 订单和成交记录
        self.orders: Dict[str, Order] = {}
        self.trades: List[Trade] = []
        
        # 价格回调函数
        self.price_callback: Optional[Callable[[str], float]] = None
        
        # 日志
        self.logger = logging.getLogger('SimulatedBroker')

    def set_price_callback(self, callback: Callable[[str], float]):
        """
        设置价格回调函数
        
        Args:
            callback: 获取股票价格的回调函数，参数为股票代码，返回当前价格
        """
        self.price_callback = callback

    def get_current_price(self, stock_code: str) -> float:
        """
        获取当前价格
        
        Args:
            stock_code: 股票代码
            
        Returns:
            当前价格
        """
        if self.price_callback:
            return self.price_callback(stock_code)
        
        # 如果没有设置回调，返回持仓中的价格
        position = self.account.get_position(stock_code)
        if position:
            return position.current_price
        
        return 0

    def submit_order(
        self,
        stock_code: str,
        stock_name: str,
        side: OrderSide,
        quantity: int,
        price: float = 0,
        order_type: OrderType = OrderType.MARKET,
        strategy_name: str = ""
    ) -> Optional[Order]:
        """
        提交订单
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            side: 买卖方向
            quantity: 数量（必须是100的整数倍）
            price: 价格（限价单时有效）
            order_type: 订单类型
            strategy_name: 策略名称
            
        Returns:
            订单对象
        """
        # 验证数量
        if quantity <= 0 or quantity % 100 != 0:
            self.logger.error(f"无效的数量: {quantity}，必须是100的整数倍")
            return None
        
        # 获取当前价格
        current_price = self.get_current_price(stock_code)
        if current_price <= 0:
            current_price = price if price > 0 else 0
        
        if current_price <= 0:
            self.logger.error(f"无法获取价格: {stock_code}")
            return None
        
        # 计算滑点后的价格
        if side == OrderSide.BUY:
            exec_price = current_price * (1 + self.slippage)
        else:
            exec_price = current_price * (1 - self.slippage)
        
        # 创建订单
        order = Order(
            order_id=f"ORD_{uuid.uuid4().hex[:8].upper()}",
            stock_code=stock_code,
            stock_name=stock_name,
            side=side,
            order_type=order_type,
            price=exec_price,
            quantity=quantity,
            status=OrderStatus.SUBMITTED,
            strategy_name=strategy_name
        )
        
        # 检查资金/持仓
        if side == OrderSide.BUY:
            required_cash = exec_price * quantity
            if required_cash > self.account.cash:
                order.status = OrderStatus.REJECTED
                order.remark = f"资金不足: 需要{required_cash:.2f}，可用{self.account.cash:.2f}"
                self.orders[order.order_id] = order
                self.logger.warning(order.remark)
                return order
        else:
            position = self.account.get_position(stock_code)
            if not position or position.quantity < quantity:
                order.status = OrderStatus.REJECTED
                avail = position.quantity if position else 0
                order.remark = f"持仓不足: 需要{quantity}股，可用{avail}股"
                self.orders[order.order_id] = order
                self.logger.warning(order.remark)
                return order
        
        # 执行订单
        self._execute_order(order)
        
        return order

    def _execute_order(self, order: Order):
        """
        执行订单
        
        Args:
            order: 订单对象
        """
        # 计算成交金额
        trade_amount = order.price * order.quantity
        
        # 计算佣金
        commission = max(trade_amount * self.commission_rate, self.min_commission)
        
        # 计算印花税（仅卖出）
        tax = 0
        if order.side == OrderSide.SELL:
            tax = trade_amount * self.tax_rate
        
        # 创建成交记录
        trade = Trade(
            trade_id=f"TRD_{uuid.uuid4().hex[:8].upper()}",
            order_id=order.order_id,
            stock_code=order.stock_code,
            stock_name=order.stock_name,
            side=order.side,
            price=order.price,
            quantity=order.quantity,
            amount=trade_amount,
            commission=commission,
            tax=tax,
            trade_time=datetime.now()
        )
        
        # 更新订单状态
        order.filled_quantity = order.quantity
        order.filled_price = order.price
        order.status = OrderStatus.FILLED
        order.updated_time = datetime.now()
        
        # 更新账户
        if order.side == OrderSide.BUY:
            self._process_buy(order, trade)
        else:
            self._process_sell(order, trade)
        
        # 保存订单和成交记录
        self.orders[order.order_id] = order
        self.trades.append(trade)
        
        # 更新账户资产
        self.account.update_assets()
        
        self.logger.info(
            f"订单成交: {order.side.value} {order.stock_code} "
            f"{order.quantity}股 @ {order.price:.2f} "
            f"金额:{trade_amount:.2f} 佣金:{commission:.2f} 税:{tax:.2f}"
        )

    def _process_buy(self, order: Order, trade: Trade):
        """处理买入"""
        # 扣除资金
        total_cost = trade.amount + trade.commission
        self.account.cash -= total_cost
        
        # 更新持仓
        position = self.account.get_position(order.stock_code)
        if position:
            # 加仓
            total_quantity = position.quantity + order.quantity
            total_cost = position.avg_cost * position.quantity + order.price * order.quantity
            position.avg_cost = total_cost / total_quantity
            position.quantity = total_quantity
            position.update_price(order.price)
        else:
            # 新建持仓
            position = Position(
                stock_code=order.stock_code,
                stock_name=order.stock_name,
                quantity=order.quantity,
                avg_cost=order.price,
                current_price=order.price
            )
            position.update_price(order.price)
            self.account.add_position(position)
        
        # 更新佣金
        self.account.commission += trade.commission

    def _process_sell(self, order: Order, trade: Trade):
        """处理卖出"""
        # 增加资金
        total_income = trade.amount - trade.commission - trade.tax
        self.account.cash += total_income
        
        # 更新持仓
        position = self.account.get_position(order.stock_code)
        if position:
            position.quantity -= order.quantity
            if position.quantity <= 0:
                self.account.remove_position(order.stock_code)
            else:
                position.update_price(order.price)
        
        # 更新佣金和税
        self.account.commission += trade.commission
        self.account.tax += trade.tax

    def cancel_order(self, order_id: str) -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            是否取消成功
        """
        order = self.orders.get(order_id)
        if not order:
            return False
        
        if not order.is_active:
            return False
        
        order.status = OrderStatus.CANCELLED
        order.updated_time = datetime.now()
        
        self.logger.info(f"订单取消: {order_id}")
        return True

    def get_account(self) -> Account:
        """获取账户信息"""
        self.account.update_assets()
        return self.account

    def get_positions(self) -> List[Position]:
        """获取所有持仓"""
        return list(self.account.positions.values())

    def get_position(self, stock_code: str) -> Optional[Position]:
        """获取指定股票的持仓"""
        return self.account.get_position(stock_code)

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

    def get_trades(self) -> List[Trade]:
        """获取成交记录"""
        return self.trades

    def update_position_prices(self, prices: Dict[str, float]):
        """
        更新持仓价格
        
        Args:
            prices: {股票代码: 当前价格}
        """
        for stock_code, price in prices.items():
            position = self.account.get_position(stock_code)
            if position:
                position.update_price(price)
        
        self.account.update_assets()

    def get_summary(self) -> Dict:
        """
        获取账户摘要
        
        Returns:
            账户摘要字典
        """
        self.account.update_assets()
        
        return {
            'account_id': self.account.account_id,
            'initial_capital': self.initial_capital,
            'total_assets': self.account.total_assets,
            'cash': self.account.cash,
            'market_value': self.account.market_value,
            'total_pnl': self.account.total_pnl,
            'total_pnl_pct': (self.account.total_pnl / self.initial_capital) * 100,
            'commission': self.account.commission,
            'tax': self.account.tax,
            'position_count': len(self.account.positions),
            'trade_count': len(self.trades)
        }
