"""
量化交易模块测试用例
"""

import unittest
from datetime import datetime

from trading.models import (
    Order, OrderSide, OrderType, OrderStatus,
    Position, PositionSide, Account, Trade
)
from trading.simulator import SimulatedBroker
from trading.strategy import SignalStrategy, StrategyEngine
from trading.risk_manager import RiskManager, RiskConfig
from trading.order_manager import OrderManager
from signal_aggregator import SignalType, AggregatedSignal


class TestModels(unittest.TestCase):
    """测试数据模型"""

    def test_order_creation(self):
        """测试创建订单"""
        order = Order(
            order_id="ORD_001",
            stock_code="600519",
            stock_name="贵州茅台",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=1800.0,
            quantity=100
        )
        
        self.assertEqual(order.order_id, "ORD_001")
        self.assertEqual(order.stock_code, "600519")
        self.assertTrue(order.is_buy)
        self.assertFalse(order.is_sell)
        self.assertEqual(order.amount, 180000)

    def test_position_update(self):
        """测试更新持仓"""
        position = Position(
            stock_code="600519",
            stock_name="贵州茅台",
            quantity=100,
            avg_cost=1800.0,
            current_price=1800.0
        )
        
        # 更新价格上涨
        position.update_price(1900.0)
        self.assertEqual(position.market_value, 190000)
        self.assertEqual(position.unrealized_pnl, 10000)
        self.assertAlmostEqual(position.unrealized_pnl_pct, 5.56, places=2)
        
        # 更新价格下跌
        position.update_price(1700.0)
        self.assertEqual(position.unrealized_pnl, -10000)

    def test_account_update(self):
        """测试更新账户"""
        account = Account(
            account_id="TEST_001",
            initial_capital=1000000,
            cash=1000000
        )
        
        # 添加持仓
        position = Position(
            stock_code="600519",
            stock_name="贵州茅台",
            quantity=100,
            avg_cost=1800.0,
            current_price=1800.0
        )
        position.update_price(1800.0)
        account.add_position(position)
        
        # 更新资产
        account.update_assets()
        
        self.assertEqual(account.market_value, 180000)
        self.assertEqual(account.total_assets, 1180000)


class TestSimulator(unittest.TestCase):
    """测试模拟券商"""

    def setUp(self):
        self.broker = SimulatedBroker(initial_capital=1000000)
        
        # 设置价格回调
        self.prices = {
            '600519': 1800.0,
            '600900': 25.0
        }
        self.broker.set_price_callback(lambda code: self.prices.get(code, 0))

    def test_buy_order(self):
        """测试买入订单"""
        order = self.broker.submit_order(
            stock_code='600519',
            stock_name='贵州茅台',
            side=OrderSide.BUY,
            quantity=100
        )
        
        self.assertIsNotNone(order)
        self.assertEqual(order.status, OrderStatus.FILLED)
        self.assertEqual(order.filled_quantity, 100)
        
        # 检查持仓
        position = self.broker.get_position('600519')
        self.assertIsNotNone(position)
        self.assertEqual(position.quantity, 100)
        
        # 检查账户
        account = self.broker.get_account()
        self.assertLess(account.cash, 1000000)

    def test_sell_order(self):
        """测试卖出订单"""
        # 先买入
        self.broker.submit_order(
            stock_code='600519',
            stock_name='贵州茅台',
            side=OrderSide.BUY,
            quantity=100
        )
        
        # 再卖出
        order = self.broker.submit_order(
            stock_code='600519',
            stock_name='贵州茅台',
            side=OrderSide.SELL,
            quantity=100
        )
        
        self.assertIsNotNone(order)
        self.assertEqual(order.status, OrderStatus.FILLED)
        
        # 检查持仓
        position = self.broker.get_position('600519')
        self.assertIsNone(position)

    def test_insufficient_funds(self):
        """测试资金不足"""
        order = self.broker.submit_order(
            stock_code='600519',
            stock_name='贵州茅台',
            side=OrderSide.BUY,
            quantity=10000  # 需要1800万
        )
        
        self.assertEqual(order.status, OrderStatus.REJECTED)
        self.assertIn('资金不足', order.remark)

    def test_insufficient_position(self):
        """测试持仓不足"""
        order = self.broker.submit_order(
            stock_code='600519',
            stock_name='贵州茅台',
            side=OrderSide.SELL,
            quantity=100
        )
        
        self.assertEqual(order.status, OrderStatus.REJECTED)
        self.assertIn('持仓不足', order.remark)


class TestStrategy(unittest.TestCase):
    """测试策略"""

    def setUp(self):
        self.broker = SimulatedBroker(initial_capital=1000000)
        self.broker.set_price_callback(lambda code: 1800.0 if code == '600519' else 25.0)
        
        self.strategy = SignalStrategy(
            min_score=60,
            max_position_pct=0.3,
            position_size=1
        )

    def test_generate_buy_signal(self):
        """测试生成买入信号"""
        # 创建聚合信号
        agg_signal = AggregatedSignal(
            stock_code='600519',
            stock_name='贵州茅台',
            weighted_score=75.0,
            consensus=SignalType.BUY,
            confidence=0.8,
            platform_signals=[],
            risk_level='low'
        )
        
        signals = self.strategy.generate_signals(
            [agg_signal],
            current_positions={},
            total_assets=1000000
        )
        
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]['side'], 'buy')
        self.assertEqual(signals[0]['stock_code'], '600519')

    def test_no_buy_signal_low_score(self):
        """测试低评分不生成买入信号"""
        agg_signal = AggregatedSignal(
            stock_code='600519',
            stock_name='贵州茅台',
            weighted_score=50.0,  # 低于阈值
            consensus=SignalType.BUY,
            confidence=0.8,
            platform_signals=[],
            risk_level='low'
        )
        
        signals = self.strategy.generate_signals(
            [agg_signal],
            current_positions={},
            total_assets=1000000
        )
        
        self.assertEqual(len(signals), 0)


class TestRiskManager(unittest.TestCase):
    """测试风险管理"""

    def setUp(self):
        self.config = RiskConfig(
            max_position_pct=0.2,
            stop_loss_pct=0.05,
            take_profit_pct=0.15
        )
        self.risk_manager = RiskManager(self.config)
        self.risk_manager.set_initial_assets(1000000)

    def test_stop_loss(self):
        """测试止损"""
        position = Position(
            stock_code='600519',
            stock_name='贵州茅台',
            quantity=100,
            avg_cost=1800.0,
            current_price=1700.0  # 亏损5.56%
        )
        
        signals = self.risk_manager.check_stop_loss([position])
        self.assertEqual(len(signals), 1)
        self.assertIn('止损', signals[0]['reason'])

    def test_take_profit(self):
        """测试止盈"""
        position = Position(
            stock_code='600519',
            stock_name='贵州茅台',
            quantity=100,
            avg_cost=1800.0,
            current_price=2100.0  # 盈利16.67%
        )
        
        signals = self.risk_manager.check_take_profit([position])
        self.assertEqual(len(signals), 1)
        self.assertIn('止盈', signals[0]['reason'])

    def test_no_stop_loss(self):
        """测试未触发止损"""
        position = Position(
            stock_code='600519',
            stock_name='贵州茅台',
            quantity=100,
            avg_cost=1800.0,
            current_price=1750.0  # 亏损2.78%
        )
        
        signals = self.risk_manager.check_stop_loss([position])
        self.assertEqual(len(signals), 0)


class TestOrderManager(unittest.TestCase):
    """测试订单管理"""

    def setUp(self):
        self.broker = SimulatedBroker(initial_capital=1000000)
        self.broker.set_price_callback(lambda code: 1800.0 if code == '600519' else 25.0)
        self.order_manager = OrderManager(self.broker)

    def test_create_buy_order(self):
        """测试创建买入订单"""
        order = self.order_manager.create_buy_order(
            stock_code='600519',
            stock_name='贵州茅台',
            quantity=100
        )
        
        self.assertIsNotNone(order)
        self.assertEqual(order.status, OrderStatus.FILLED)

    def test_get_orders(self):
        """测试获取订单"""
        # 创建订单
        self.order_manager.create_buy_order(
            stock_code='600519',
            stock_name='贵州茅台',
            quantity=100
        )
        
        # 获取订单
        orders = self.order_manager.get_orders()
        self.assertEqual(len(orders), 1)
        
        # 按状态筛选
        filled_orders = self.order_manager.get_filled_orders()
        self.assertEqual(len(filled_orders), 1)

    def test_order_summary(self):
        """测试订单摘要"""
        # 创建订单
        self.order_manager.create_buy_order(
            stock_code='600519',
            stock_name='贵州茅台',
            quantity=100
        )
        
        summary = self.order_manager.get_order_summary()
        self.assertEqual(summary['total_orders'], 1)
        self.assertEqual(summary['buy_count'], 1)


if __name__ == '__main__':
    unittest.main()
