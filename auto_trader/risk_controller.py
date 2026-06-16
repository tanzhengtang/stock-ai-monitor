"""
风险控制器
控制交易风险，防止过度交易和重大亏损
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .base_broker import Order, OrderSide, OrderStatus, Account, Position


@dataclass
class RiskConfig:
    """风险配置"""
    # 仓位限制
    max_position_pct: float = 0.2        # 单只股票最大仓位
    max_total_position_pct: float = 0.8  # 最大总仓位
    min_cash_ratio: float = 0.2          # 最小现金比例
    
    # 亏损限制
    max_daily_loss_pct: float = 0.03     # 单日最大亏损
    max_drawdown_pct: float = 0.1        # 最大回撤
    stop_loss_pct: float = 0.05          # 止损比例
    take_profit_pct: float = 0.15        # 止盈比例
    
    # 交易限制
    max_orders_per_day: int = 10         # 每日最大订单数
    max_buy_per_stock: int = 3           # 单只股票最大买入次数
    min_order_interval: int = 60         # 最小下单间隔（秒）
    
    # 价格限制
    max_price_deviation: float = 0.05    # 最大价格偏离
    min_volume: int = 100000             # 最小成交量


class RiskController:
    """风险控制器
    
    功能：
    1. 订单审核
    2. 仓位控制
    3. 止损止盈
    4. 交易限制
    5. 风险告警
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        """
        初始化风险控制器
        
        Args:
            config: 风险配置
        """
        self.config = config or RiskConfig()
        self.logger = logging.getLogger('RiskController')
        
        # 状态
        self.initial_assets = 0
        self.max_assets = 0
        self.daily_start_assets = 0
        
        # 统计
        self.daily_order_count = 0
        self.daily_buy_count: Dict[str, int] = {}  # {stock_code: count}
        self.last_order_time: Dict[str, datetime] = {}  # {stock_code: time}
        
        # 告警
        self.warnings: List[str] = []

    def reset_daily(self):
        """重置每日统计"""
        self.daily_order_count = 0
        self.daily_buy_count = {}
        self.warnings = []

    def set_initial_assets(self, assets: float):
        """设置初始资产"""
        self.initial_assets = assets
        self.max_assets = assets
        self.daily_start_assets = assets

    def check_order(
        self,
        order: Order,
        account: Account,
        current_price: float
    ) -> Tuple[bool, str]:
        """
        审核订单
        
        Args:
            order: 订单
            account: 账户
            current_price: 当前价格
            
        Returns:
            (是否通过, 原因)
        """
        # 检查每日订单数
        if self.daily_order_count >= self.config.max_orders_per_day:
            return False, f"超过每日最大订单数: {self.config.max_orders_per_day}"
        
        # 买入检查
        if order.is_buy:
            return self._check_buy_order(order, account, current_price)
        
        # 卖出检查
        return self._check_sell_order(order, account, current_price)

    def _check_buy_order(
        self,
        order: Order,
        account: Account,
        current_price: float
    ) -> Tuple[bool, str]:
        """检查买入订单"""
        # 检查单只股票买入次数
        buy_count = self.daily_buy_count.get(order.stock_code, 0)
        if buy_count >= self.config.max_buy_per_stock:
            return False, f"单只股票买入次数过多: {buy_count}"
        
        # 检查下单间隔
        last_time = self.last_order_time.get(order.stock_code)
        if last_time:
            interval = (datetime.now() - last_time).seconds
            if interval < self.config.min_order_interval:
                return False, f"下单间隔过短: {interval}秒"
        
        # 计算订单金额
        order_amount = current_price * order.quantity
        
        # 检查现金
        if order_amount > account.cash:
            return False, f"资金不足"
        
        # 检查单只股票仓位
        position = account.positions.get(order.stock_code)
        current_value = position.market_value if position else 0
        new_value = current_value + order_amount
        position_pct = new_value / account.total_assets if account.total_assets > 0 else 0
        
        if position_pct > self.config.max_position_pct:
            return False, f"超过单只股票最大仓位: {position_pct:.1%}"
        
        # 检查总仓位
        new_total_position = account.market_value + order_amount
        total_pct = new_total_position / account.total_assets if account.total_assets > 0 else 0
        
        if total_pct > self.config.max_total_position_pct:
            return False, f"超过最大总仓位: {total_pct:.1%}"
        
        # 检查现金比例
        new_cash = account.cash - order_amount
        cash_ratio = new_cash / account.total_assets if account.total_assets > 0 else 0
        
        if cash_ratio < self.config.min_cash_ratio:
            return False, f"低于最小现金比例: {cash_ratio:.1%}"
        
        return True, "通过"

    def _check_sell_order(
        self,
        order: Order,
        account: Account,
        current_price: float
    ) -> Tuple[bool, str]:
        """检查卖出订单"""
        position = account.positions.get(order.stock_code)
        
        if not position:
            return False, "没有持仓"
        
        if position.quantity < order.quantity:
            return False, f"持仓不足"
        
        return True, "通过"

    def check_stop_loss(self, positions: List[Position]) -> List[Dict]:
        """
        检查止损
        
        Args:
            positions: 持仓列表
            
        Returns:
            需要止损的信号
        """
        signals = []
        
        for pos in positions:
            if pos.quantity <= 0 or pos.avg_cost <= 0:
                continue
            
            loss_pct = (pos.avg_cost - pos.current_price) / pos.avg_cost
            
            if loss_pct >= self.config.stop_loss_pct:
                signals.append({
                    'stock_code': pos.stock_code,
                    'stock_name': pos.stock_name,
                    'action': 'sell',
                    'reason': f"触发止损: 亏损{loss_pct:.1%}",
                    'price': pos.current_price,
                    'quantity': pos.quantity
                })
                
                self.logger.warning(f"止损信号: {pos.stock_code} 亏损{loss_pct:.1%}")
        
        return signals

    def check_take_profit(self, positions: List[Position]) -> List[Dict]:
        """
        检查止盈
        
        Args:
            positions: 持仓列表
            
        Returns:
            需要止盈的信号
        """
        signals = []
        
        for pos in positions:
            if pos.quantity <= 0 or pos.avg_cost <= 0:
                continue
            
            profit_pct = (pos.current_price - pos.avg_cost) / pos.avg_cost
            
            if profit_pct >= self.config.take_profit_pct:
                signals.append({
                    'stock_code': pos.stock_code,
                    'stock_name': pos.stock_name,
                    'action': 'sell',
                    'reason': f"触发止盈: 盈利{profit_pct:.1%}",
                    'price': pos.current_price,
                    'quantity': pos.quantity
                })
                
                self.logger.info(f"止盈信号: {pos.stock_code} 盈利{profit_pct:.1%}")
        
        return signals

    def check_daily_loss(self, current_assets: float) -> bool:
        """
        检查日亏损
        
        Args:
            current_assets: 当前资产
            
        Returns:
            是否触发日亏损限制
        """
        if self.daily_start_assets <= 0:
            return False
        
        loss = self.daily_start_assets - current_assets
        loss_pct = loss / self.daily_start_assets
        
        if loss_pct >= self.config.max_daily_loss_pct:
            self.logger.warning(f"触发日亏损限制: {loss_pct:.1%}")
            return True
        
        return False

    def check_drawdown(self, current_assets: float) -> bool:
        """
        检查回撤
        
        Args:
            current_assets: 当前资产
            
        Returns:
            是否触发回撤限制
        """
        if current_assets > self.max_assets:
            self.max_assets = current_assets
        
        drawdown = self.max_assets - current_assets
        drawdown_pct = drawdown / self.max_assets if self.max_assets > 0 else 0
        
        if drawdown_pct >= self.config.max_drawdown_pct:
            self.logger.warning(f"触发回撤限制: {drawdown_pct:.1%}")
            return True
        
        return False

    def on_order_submitted(self, order: Order):
        """订单提交回调"""
        self.daily_order_count += 1
        self.last_order_time[order.stock_code] = datetime.now()
        
        if order.is_buy:
            count = self.daily_buy_count.get(order.stock_code, 0)
            self.daily_buy_count[order.stock_code] = count + 1

    def get_risk_status(self, account: Account) -> Dict:
        """
        获取风险状态
        
        Args:
            account: 账户
            
        Returns:
            风险状态
        """
        position_pct = account.market_value / account.total_assets if account.total_assets > 0 else 0
        cash_ratio = account.cash / account.total_assets if account.total_assets > 0 else 0
        
        drawdown_pct = 0
        if self.max_assets > 0:
            drawdown_pct = (self.max_assets - account.total_assets) / self.max_assets
        
        daily_loss_pct = 0
        if self.daily_start_assets > 0:
            daily_loss_pct = (self.daily_start_assets - account.total_assets) / self.daily_start_assets
        
        return {
            'position_pct': position_pct,
            'cash_ratio': cash_ratio,
            'drawdown_pct': drawdown_pct,
            'daily_loss_pct': daily_loss_pct,
            'daily_order_count': self.daily_order_count,
            'warnings': self.warnings,
            'is_position_warning': position_pct > self.config.max_total_position_pct * 0.8,
            'is_daily_loss_warning': daily_loss_pct > self.config.max_daily_loss_pct * 0.8,
            'is_drawdown_warning': drawdown_pct > self.config.max_drawdown_pct * 0.8
        }
