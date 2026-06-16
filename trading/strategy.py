"""
策略引擎
根据AI信号生成交易指令
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime

from .models import Order, OrderSide, OrderType, OrderStatus, Position
from .simulator import SimulatedBroker
from signal_aggregator import SignalAggregator, PlatformSignal, SignalType, AggregatedSignal


class BaseStrategy(ABC):
    """策略基类
    
    所有策略都应继承此类，实现抽象方法。
    """

    def __init__(self, name: str):
        """
        初始化策略
        
        Args:
            name: 策略名称
        """
        self.name = name
        self.logger = logging.getLogger(f'Strategy.{name}')

    @abstractmethod
    def generate_signals(self, data: Dict) -> List[Dict]:
        """
        生成交易信号
        
        Args:
            data: 输入数据
            
        Returns:
            信号列表，每个信号包含:
            - stock_code: 股票代码
            - stock_name: 股票名称
            - side: 买卖方向 ('buy' / 'sell')
            - quantity: 数量
            - price: 价格（可选）
            - reason: 原因
        """
        pass


class SignalStrategy(BaseStrategy):
    """基于AI信号的策略
    
    根据信号聚合器的结果生成交易指令。
    """

    def __init__(
        self,
        name: str = "SignalStrategy",
        min_score: float = 70,
        max_position_pct: float = 0.2,  # 单只股票最大仓位比例
        position_size: int = 100,       # 基础交易数量
        buy_signal_types: List[SignalType] = None,
        sell_signal_types: List[SignalType] = None
    ):
        """
        初始化策略
        
        Args:
            name: 策略名称
            min_score: 最低买入评分
            max_position_pct: 单只股票最大仓位比例
            position_size: 基础交易数量（手，1手=100股）
            buy_signal_types: 触发买入的信号类型
            sell_signal_types: 触发卖出的信号类型
        """
        super().__init__(name)
        self.min_score = min_score
        self.max_position_pct = max_position_pct
        self.position_size = position_size * 100  # 转换为股数
        
        # 默认买入信号类型
        self.buy_signal_types = buy_signal_types or [
            SignalType.STRONG_BUY,
            SignalType.BUY
        ]
        
        # 默认卖出信号类型
        self.sell_signal_types = sell_signal_types or [
            SignalType.SELL,
            SignalType.STRONG_SELL
        ]

    def generate_signals(
        self,
        aggregated_signals: List[AggregatedSignal],
        current_positions: Dict[str, Position] = None,
        total_assets: float = 1000000
    ) -> List[Dict]:
        """
        根据聚合信号生成交易信号
        
        Args:
            aggregated_signals: 聚合信号列表
            current_positions: 当前持仓 {股票代码: Position}
            total_assets: 总资产
            
        Returns:
            交易信号列表
        """
        signals = []
        current_positions = current_positions or {}
        
        for agg_signal in aggregated_signals:
            stock_code = agg_signal.stock_code
            stock_name = agg_signal.stock_name
            
            # 检查是否需要买入
            if agg_signal.consensus in self.buy_signal_types:
                # 检查评分是否达到阈值
                if agg_signal.weighted_score >= self.min_score:
                    # 检查是否已有持仓
                    if stock_code not in current_positions:
                        # 计算买入数量
                        max_amount = total_assets * self.max_position_pct
                        quantity = min(
                            self.position_size,
                            int(max_amount / agg_signal.weighted_score) // 100 * 100
                        )
                        
                        if quantity >= 100:
                            signals.append({
                                'stock_code': stock_code,
                                'stock_name': stock_name,
                                'side': 'buy',
                                'quantity': quantity,
                                'score': agg_signal.weighted_score,
                                'reason': f"AI信号: {agg_signal.consensus.value}, 评分: {agg_signal.weighted_score:.1f}"
                            })
            
            # 检查是否需要卖出
            elif agg_signal.consensus in self.sell_signal_types:
                # 检查是否有持仓
                if stock_code in current_positions:
                    position = current_positions[stock_code]
                    signals.append({
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'side': 'sell',
                        'quantity': position.quantity,
                        'score': agg_signal.weighted_score,
                        'reason': f"AI信号: {agg_signal.consensus.value}, 评分: {agg_signal.weighted_score:.1f}"
                    })
        
        return signals


class StrategyEngine:
    """策略引擎
    
    管理和执行策略。
    """

    def __init__(self, broker: SimulatedBroker):
        """
        初始化策略引擎
        
        Args:
            broker: 模拟券商实例
        """
        self.broker = broker
        self.strategies: Dict[str, BaseStrategy] = {}
        self.logger = logging.getLogger('StrategyEngine')

    def add_strategy(self, strategy: BaseStrategy):
        """
        添加策略
        
        Args:
            strategy: 策略实例
        """
        self.strategies[strategy.name] = strategy
        self.logger.info(f"添加策略: {strategy.name}")

    def remove_strategy(self, name: str):
        """
        移除策略
        
        Args:
            name: 策略名称
        """
        self.strategies.pop(name, None)
        self.logger.info(f"移除策略: {name}")

    def execute_signals(
        self,
        aggregated_signals: List[AggregatedSignal],
        strategy_name: str = "SignalStrategy"
    ) -> List[Order]:
        """
        执行策略信号
        
        Args:
            aggregated_signals: 聚合信号列表
            strategy_name: 策略名称
            
        Returns:
            生成的订单列表
        """
        strategy = self.strategies.get(strategy_name)
        if not strategy:
            self.logger.error(f"策略不存在: {strategy_name}")
            return []
        
        # 获取当前持仓和资产
        positions = {p.stock_code: p for p in self.broker.get_positions()}
        account = self.broker.get_account()
        
        # 生成交易信号
        signals = strategy.generate_signals(
            aggregated_signals,
            current_positions=positions,
            total_assets=account.total_assets
        )
        
        # 执行交易信号
        orders = []
        for signal in signals:
            order = self.broker.submit_order(
                stock_code=signal['stock_code'],
                stock_name=signal['stock_name'],
                side=OrderSide.BUY if signal['side'] == 'buy' else OrderSide.SELL,
                quantity=signal['quantity'],
                strategy_name=strategy_name
            )
            
            if order:
                orders.append(order)
                self.logger.info(
                    f"策略信号执行: {signal['side']} {signal['stock_code']} "
                    f"{signal['quantity']}股 - {signal['reason']}"
                )
        
        return orders

    def get_strategy_summary(self) -> Dict:
        """
        获取策略执行摘要
        
        Returns:
            策略摘要字典
        """
        account = self.broker.get_account()
        
        # 按策略统计订单
        strategy_orders = {}
        for order in self.broker.get_orders():
            strategy_name = order.strategy_name or "default"
            if strategy_name not in strategy_orders:
                strategy_orders[strategy_name] = {
                    'total': 0,
                    'filled': 0,
                    'rejected': 0
                }
            
            strategy_orders[strategy_name]['total'] += 1
            if order.is_filled:
                strategy_orders[strategy_name]['filled'] += 1
            elif order.status == OrderStatus.REJECTED:
                strategy_orders[strategy_name]['rejected'] += 1
        
        return {
            'strategies': list(self.strategies.keys()),
            'strategy_orders': strategy_orders,
            'account': account.to_dict()
        }
