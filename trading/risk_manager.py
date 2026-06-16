"""
风险管理模块
控制交易风险
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from .models import Order, OrderSide, Position, Account


@dataclass
class RiskConfig:
    """风险配置
    
    Attributes:
        max_position_pct: 单只股票最大仓位比例
        max_total_position_pct: 最大总仓位比例
        max_daily_loss_pct: 单日最大亏损比例
        max_drawdown_pct: 最大回撤比例
        stop_loss_pct: 止损比例
        take_profit_pct: 止盈比例
        max_orders_per_day: 每日最大订单数
        min_cash_ratio: 最小现金比例
    """
    max_position_pct: float = 0.2        # 单只股票最大仓位20%
    max_total_position_pct: float = 0.8  # 最大总仓位80%
    max_daily_loss_pct: float = 0.03     # 单日最大亏损3%
    max_drawdown_pct: float = 0.1        # 最大回撤10%
    stop_loss_pct: float = 0.05          # 止损5%
    take_profit_pct: float = 0.15        # 止盈15%
    max_orders_per_day: int = 10         # 每日最大订单数
    min_cash_ratio: float = 0.2          # 最小现金比例20%


class RiskManager:
    """风险管理器
    
    提供风险控制功能：
    - 仓位控制
    - 止损止盈
    - 日亏损限制
    - 回撤控制
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        """
        初始化风险管理器
        
        Args:
            config: 风险配置
        """
        self.config = config or RiskConfig()
        self.logger = logging.getLogger('RiskManager')
        
        # 当日订单计数
        self.daily_order_count = 0
        
        # 初始资产（用于计算回撤）
        self.initial_assets = 0
        self.max_assets = 0

    def reset_daily(self):
        """重置每日统计"""
        self.daily_order_count = 0

    def set_initial_assets(self, assets: float):
        """
        设置初始资产
        
        Args:
            assets: 初始资产
        """
        self.initial_assets = assets
        self.max_assets = assets

    def check_order(
        self,
        order: Order,
        account: Account,
        current_price: float
    ) -> tuple[bool, str]:
        """
        检查订单是否符合风险控制
        
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
        if order.side == OrderSide.BUY:
            return self._check_buy_order(order, account, current_price)
        
        # 卖出检查
        return self._check_sell_order(order, account, current_price)

    def _check_buy_order(
        self,
        order: Order,
        account: Account,
        current_price: float
    ) -> tuple[bool, str]:
        """检查买入订单"""
        # 计算订单金额
        order_amount = current_price * order.quantity
        
        # 检查现金是否充足
        if order_amount > account.cash:
            return False, f"资金不足: 需要{order_amount:.2f}, 可用{account.cash:.2f}"
        
        # 检查单只股票仓位
        position = account.get_position(order.stock_code)
        current_position_value = position.market_value if position else 0
        new_position_value = current_position_value + order_amount
        position_pct = new_position_value / account.total_assets
        
        if position_pct > self.config.max_position_pct:
            return False, f"超过单只股票最大仓位: {position_pct:.1%} > {self.config.max_position_pct:.1%}"
        
        # 检查总仓位
        new_total_position = account.market_value + order_amount
        total_position_pct = new_total_position / account.total_assets
        
        if total_position_pct > self.config.max_total_position_pct:
            return False, f"超过最大总仓位: {total_position_pct:.1%} > {self.config.max_total_position_pct:.1%}"
        
        # 检查最小现金比例
        new_cash = account.cash - order_amount
        cash_ratio = new_cash / account.total_assets
        
        if cash_ratio < self.config.min_cash_ratio:
            return False, f"低于最小现金比例: {cash_ratio:.1%} < {self.config.min_cash_ratio:.1%}"
        
        return True, "通过"

    def _check_sell_order(
        self,
        order: Order,
        account: Account,
        current_price: float
    ) -> tuple[bool, str]:
        """检查卖出订单"""
        # 检查持仓
        position = account.get_position(order.stock_code)
        
        if not position:
            return False, f"没有持仓: {order.stock_code}"
        
        if position.quantity < order.quantity:
            return False, f"持仓不足: 需要{order.quantity}股, 可用{position.quantity}股"
        
        return True, "通过"

    def check_stop_loss(self, positions: List[Position]) -> List[Dict]:
        """
        检查止损
        
        Args:
            positions: 持仓列表
            
        Returns:
            需要止损的信号列表
        """
        stop_loss_signals = []
        
        for position in positions:
            if position.quantity <= 0:
                continue
            
            # 计算亏损比例
            loss_pct = (position.avg_cost - position.current_price) / position.avg_cost
            
            if loss_pct >= self.config.stop_loss_pct:
                stop_loss_signals.append({
                    'stock_code': position.stock_code,
                    'stock_name': position.stock_name,
                    'side': 'sell',
                    'quantity': position.quantity,
                    'reason': f"触发止损: 亏损{loss_pct:.1%} >= {self.config.stop_loss_pct:.1%}",
                    'loss_pct': loss_pct
                })
                
                self.logger.warning(
                    f"止损信号: {position.stock_code} {position.stock_name} "
                    f"亏损{loss_pct:.1%}"
                )
        
        return stop_loss_signals

    def check_take_profit(self, positions: List[Position]) -> List[Dict]:
        """
        检查止盈
        
        Args:
            positions: 持仓列表
            
        Returns:
            需要止盈的信号列表
        """
        take_profit_signals = []
        
        for position in positions:
            if position.quantity <= 0:
                continue
            
            # 计算盈利比例
            profit_pct = (position.current_price - position.avg_cost) / position.avg_cost
            
            if profit_pct >= self.config.take_profit_pct:
                take_profit_signals.append({
                    'stock_code': position.stock_code,
                    'stock_name': position.stock_name,
                    'side': 'sell',
                    'quantity': position.quantity,
                    'reason': f"触发止盈: 盈利{profit_pct:.1%} >= {self.config.take_profit_pct:.1%}",
                    'profit_pct': profit_pct
                })
                
                self.logger.info(
                    f"止盈信号: {position.stock_code} {position.stock_name} "
                    f"盈利{profit_pct:.1%}"
                )
        
        return take_profit_signals

    def check_daily_loss(self, account: Account) -> bool:
        """
        检查日亏损
        
        Args:
            account: 账户
            
        Returns:
            是否触发日亏损限制
        """
        if self.initial_assets <= 0:
            return False
        
        daily_loss = self.initial_assets - account.total_assets
        daily_loss_pct = daily_loss / self.initial_assets
        
        if daily_loss_pct >= self.config.max_daily_loss_pct:
            self.logger.warning(
                f"触发日亏损限制: 亏损{daily_loss_pct:.1%} >= {self.config.max_daily_loss_pct:.1%}"
            )
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
        # 更新最高资产
        if current_assets > self.max_assets:
            self.max_assets = current_assets
        
        # 计算回撤
        drawdown = self.max_assets - current_assets
        drawdown_pct = drawdown / self.max_assets
        
        if drawdown_pct >= self.config.max_drawdown_pct:
            self.logger.warning(
                f"触发回撤限制: 回撤{drawdown_pct:.1%} >= {self.config.max_drawdown_pct:.1%}"
            )
            return True
        
        return False

    def get_risk_status(self, account: Account) -> Dict:
        """
        获取风险状态
        
        Args:
            account: 账户
            
        Returns:
            风险状态字典
        """
        # 计算各项指标
        position_pct = account.market_value / account.total_assets if account.total_assets > 0 else 0
        cash_ratio = account.cash / account.total_assets if account.total_assets > 0 else 0
        
        # 计算回撤
        drawdown_pct = 0
        if self.max_assets > 0:
            drawdown_pct = (self.max_assets - account.total_assets) / self.max_assets
        
        # 计算日亏损
        daily_loss_pct = 0
        if self.initial_assets > 0:
            daily_loss_pct = (self.initial_assets - account.total_assets) / self.initial_assets
        
        return {
            'position_pct': position_pct,
            'cash_ratio': cash_ratio,
            'drawdown_pct': drawdown_pct,
            'daily_loss_pct': daily_loss_pct,
            'daily_order_count': self.daily_order_count,
            'max_daily_orders': self.config.max_orders_per_day,
            'is_position_warning': position_pct > self.config.max_total_position_pct * 0.8,
            'is_daily_loss_warning': daily_loss_pct > self.config.max_daily_loss_pct * 0.8,
            'is_drawdown_warning': drawdown_pct > self.config.max_drawdown_pct * 0.8
        }
