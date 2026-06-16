"""
信号聚合器测试用例
"""

import unittest
from datetime import datetime

from signal_aggregator import (
    SignalAggregator, PlatformSignal, Platform,
    SignalType, AggregatedSignal, AggregationResult
)
from signal_aggregator.analyzers import ConsensusAnalyzer, RiskAnalyzer


class TestPlatformSignal(unittest.TestCase):
    """测试平台信号"""

    def test_create_signal(self):
        """测试创建信号"""
        signal = PlatformSignal(
            platform=Platform.EASTMONEY,
            stock_code='000001',
            stock_name='平安银行',
            score=75.0,
            signal_type=SignalType.BUY,
            confidence=0.8,
            reasons=['技术面良好', '资金流入']
        )

        self.assertEqual(signal.platform, Platform.EASTMONEY)
        self.assertEqual(signal.stock_code, '000001')
        self.assertEqual(signal.stock_name, '平安银行')
        self.assertEqual(signal.score, 75.0)
        self.assertEqual(signal.signal_type, SignalType.BUY)
        self.assertEqual(signal.confidence, 0.8)
        self.assertEqual(len(signal.reasons), 2)

    def test_invalid_score(self):
        """测试无效评分"""
        with self.assertRaises(ValueError):
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=150,  # 超出范围
                signal_type=SignalType.BUY
            )

    def test_invalid_confidence(self):
        """测试无效置信度"""
        with self.assertRaises(ValueError):
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=75,
                signal_type=SignalType.BUY,
                confidence=1.5  # 超出范围
            )

    def test_to_dict(self):
        """测试转换为字典"""
        signal = PlatformSignal(
            platform=Platform.EASTMONEY,
            stock_code='000001',
            stock_name='平安银行',
            score=75.0,
            signal_type=SignalType.BUY,
            confidence=0.8
        )

        result = signal.to_dict()
        self.assertEqual(result['platform'], 'eastmoney')
        self.assertEqual(result['stock_code'], '000001')
        self.assertEqual(result['score'], 75.0)


class TestSignalType(unittest.TestCase):
    """测试信号类型"""

    def test_from_score(self):
        """测试从评分创建信号类型"""
        self.assertEqual(SignalType.from_score(90), SignalType.STRONG_BUY)
        self.assertEqual(SignalType.from_score(70), SignalType.BUY)
        self.assertEqual(SignalType.from_score(50), SignalType.NEUTRAL)
        self.assertEqual(SignalType.from_score(30), SignalType.SELL)
        self.assertEqual(SignalType.from_score(10), SignalType.STRONG_SELL)

    def test_value_numeric(self):
        """测试数值表示"""
        self.assertEqual(SignalType.STRONG_BUY.value_numeric, 2)
        self.assertEqual(SignalType.BUY.value_numeric, 1)
        self.assertEqual(SignalType.NEUTRAL.value_numeric, 0)
        self.assertEqual(SignalType.SELL.value_numeric, -1)
        self.assertEqual(SignalType.STRONG_SELL.value_numeric, -2)


class TestConsensusAnalyzer(unittest.TestCase):
    """测试共识分析器"""

    def setUp(self):
        self.analyzer = ConsensusAnalyzer()

    def test_empty_signals(self):
        """测试空信号"""
        result = self.analyzer.analyze([])
        self.assertEqual(result, SignalType.NEUTRAL)

    def test_single_signal(self):
        """测试单个信号"""
        signals = [
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=75,
                signal_type=SignalType.BUY
            )
        ]
        result = self.analyzer.analyze(signals)
        self.assertEqual(result, SignalType.BUY)

    def test_consensus_buy(self):
        """测试买入共识"""
        signals = [
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=75,
                signal_type=SignalType.BUY,
                confidence=0.8
            ),
            PlatformSignal(
                platform=Platform.TONGHUASHUN,
                stock_code='000001',
                stock_name='平安银行',
                score=80,
                signal_type=SignalType.BUY,
                confidence=0.85
            ),
            PlatformSignal(
                platform=Platform.XUEQIU,
                stock_code='000001',
                stock_name='平安银行',
                score=70,
                signal_type=SignalType.BUY,
                confidence=0.7
            )
        ]
        result = self.analyzer.analyze(signals)
        self.assertIn(result, [SignalType.BUY, SignalType.STRONG_BUY])

    def test_consensus_sell(self):
        """测试卖出共识"""
        signals = [
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=25,
                signal_type=SignalType.SELL,
                confidence=0.8
            ),
            PlatformSignal(
                platform=Platform.TONGHUASHUN,
                stock_code='000001',
                stock_name='平安银行',
                score=20,
                signal_type=SignalType.SELL,
                confidence=0.85
            )
        ]
        result = self.analyzer.analyze(signals)
        self.assertIn(result, [SignalType.SELL, SignalType.STRONG_SELL])

    def test_mixed_signals(self):
        """测试混合信号"""
        signals = [
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=70,
                signal_type=SignalType.BUY,
                confidence=0.8
            ),
            PlatformSignal(
                platform=Platform.TONGHUASHUN,
                stock_code='000001',
                stock_name='平安银行',
                score=30,
                signal_type=SignalType.SELL,
                confidence=0.8
            )
        ]
        result = self.analyzer.analyze(signals)
        self.assertEqual(result, SignalType.NEUTRAL)

    def test_detailed_analysis(self):
        """测试详细分析"""
        signals = [
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=75,
                signal_type=SignalType.BUY,
                confidence=0.8
            ),
            PlatformSignal(
                platform=Platform.TONGHUASHUN,
                stock_code='000001',
                stock_name='平安银行',
                score=80,
                signal_type=SignalType.BUY,
                confidence=0.85
            )
        ]
        result = self.analyzer.get_detailed_analysis(signals)
        self.assertIn('consensus', result)
        self.assertIn('strength', result)
        self.assertIn('methods', result)


class TestRiskAnalyzer(unittest.TestCase):
    """测试风险分析器"""

    def setUp(self):
        self.analyzer = RiskAnalyzer()

    def test_empty_signals(self):
        """测试空信号"""
        result = self.analyzer.assess([])
        self.assertEqual(result, 'high')

    def test_low_risk(self):
        """测试低风险"""
        signals = [
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=75,
                signal_type=SignalType.BUY,
                confidence=0.9
            ),
            PlatformSignal(
                platform=Platform.TONGHUASHUN,
                stock_code='000001',
                stock_name='平安银行',
                score=78,
                signal_type=SignalType.BUY,
                confidence=0.85
            )
        ]
        result = self.analyzer.assess(signals)
        self.assertEqual(result, 'low')

    def test_high_risk_divergence(self):
        """测试高风险（信号分歧）"""
        signals = [
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=95,
                signal_type=SignalType.STRONG_BUY,
                confidence=0.9
            ),
            PlatformSignal(
                platform=Platform.TONGHUASHUN,
                stock_code='000001',
                stock_name='平安银行',
                score=5,
                signal_type=SignalType.STRONG_SELL,
                confidence=0.9
            )
        ]
        result = self.analyzer.assess(signals)
        self.assertEqual(result, 'high')

    def test_detailed_assessment(self):
        """测试详细评估"""
        signals = [
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=75,
                signal_type=SignalType.BUY,
                confidence=0.8
            )
        ]
        result = self.analyzer.get_detailed_assessment(signals)
        self.assertIn('risk_level', result)
        self.assertIn('risk_score', result)
        self.assertIn('factors', result)
        self.assertIn('warnings', result)


class TestSignalAggregator(unittest.TestCase):
    """测试信号聚合器"""

    def setUp(self):
        self.aggregator = SignalAggregator()

    def test_add_signal(self):
        """测试添加信号"""
        signal = PlatformSignal(
            platform=Platform.EASTMONEY,
            stock_code='000001',
            stock_name='平安银行',
            score=75,
            signal_type=SignalType.BUY
        )
        self.aggregator.add_signal(signal)

        signals = self.aggregator.get_stock_signals('000001')
        self.assertEqual(len(signals), 1)

    def test_add_duplicate_platform_signal(self):
        """测试添加重复平台信号"""
        signal1 = PlatformSignal(
            platform=Platform.EASTMONEY,
            stock_code='000001',
            stock_name='平安银行',
            score=75,
            signal_type=SignalType.BUY
        )
        signal2 = PlatformSignal(
            platform=Platform.EASTMONEY,
            stock_code='000001',
            stock_name='平安银行',
            score=80,
            signal_type=SignalType.BUY
        )

        self.aggregator.add_signal(signal1)
        self.aggregator.add_signal(signal2)

        signals = self.aggregator.get_stock_signals('000001')
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].score, 80)

    def test_aggregate_stock(self):
        """测试聚合单个股票"""
        signals = [
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=75,
                signal_type=SignalType.BUY,
                confidence=0.8
            ),
            PlatformSignal(
                platform=Platform.TONGHUASHUN,
                stock_code='000001',
                stock_name='平安银行',
                score=80,
                signal_type=SignalType.BUY,
                confidence=0.85
            )
        ]

        self.aggregator.add_signals(signals)
        result = self.aggregator.aggregate_stock('000001')

        self.assertIsNotNone(result)
        self.assertEqual(result.stock_code, '000001')
        self.assertIn(result.consensus, [SignalType.BUY, SignalType.STRONG_BUY])

    def test_aggregate_stock_insufficient_signals(self):
        """测试信号不足时的聚合"""
        # 使用配置要求至少2个信号
        aggregator = SignalAggregator(config={'min_signals': 2})
        
        signal = PlatformSignal(
            platform=Platform.EASTMONEY,
            stock_code='000001',
            stock_name='平安银行',
            score=75,
            signal_type=SignalType.BUY
        )

        aggregator.add_signal(signal)
        result = aggregator.aggregate_stock('000001')

        self.assertIsNone(result)

    def test_aggregate_all(self):
        """测试聚合所有股票"""
        # 股票1
        self.aggregator.add_signals([
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=75,
                signal_type=SignalType.BUY,
                confidence=0.8
            ),
            PlatformSignal(
                platform=Platform.TONGHUASHUN,
                stock_code='000001',
                stock_name='平安银行',
                score=80,
                signal_type=SignalType.BUY,
                confidence=0.85
            )
        ])

        # 股票2
        self.aggregator.add_signals([
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000002',
                stock_name='万科A',
                score=30,
                signal_type=SignalType.SELL,
                confidence=0.7
            ),
            PlatformSignal(
                platform=Platform.TONGHUASHUN,
                stock_code='000002',
                stock_name='万科A',
                score=25,
                signal_type=SignalType.SELL,
                confidence=0.75
            )
        ])

        result = self.aggregator.aggregate_all()

        self.assertEqual(result.total_stocks, 2)
        self.assertEqual(result.bullish_count, 1)
        self.assertEqual(result.bearish_count, 1)
        self.assertEqual(len(result.top_picks), 1)

    def test_clear_signals(self):
        """测试清除信号"""
        signal = PlatformSignal(
            platform=Platform.EASTMONEY,
            stock_code='000001',
            stock_name='平安银行',
            score=75,
            signal_type=SignalType.BUY
        )

        self.aggregator.add_signal(signal)
        self.assertEqual(len(self.aggregator.get_all_stock_codes()), 1)

        self.aggregator.clear_signals()
        self.assertEqual(len(self.aggregator.get_all_stock_codes()), 0)

    def test_get_statistics(self):
        """测试获取统计信息"""
        self.aggregator.add_signals([
            PlatformSignal(
                platform=Platform.EASTMONEY,
                stock_code='000001',
                stock_name='平安银行',
                score=75,
                signal_type=SignalType.BUY
            ),
            PlatformSignal(
                platform=Platform.TONGHUASHUN,
                stock_code='000001',
                stock_name='平安银行',
                score=80,
                signal_type=SignalType.BUY
            )
        ])

        stats = self.aggregator.get_statistics()
        self.assertEqual(stats['total_stocks'], 1)
        self.assertEqual(stats['total_signals'], 2)


class TestAggregationResult(unittest.TestCase):
    """测试聚合结果"""

    def test_summary(self):
        """测试摘要"""
        result = AggregationResult(
            date='2024-01-01',
            total_stocks=10,
            bullish_count=5,
            bearish_count=3,
            neutral_count=2,
            top_picks=[],
            risk_alerts=[],
            market_sentiment=0.5
        )

        summary = result.summary
        self.assertIn('2024-01-01', summary)
        self.assertIn('10', summary)

    def test_to_report(self):
        """测试生成报告"""
        signal = AggregatedSignal(
            stock_code='000001',
            stock_name='平安银行',
            weighted_score=75.0,
            consensus=SignalType.BUY,
            confidence=0.8,
            platform_signals=[],
            consensus_reasons=['技术面良好'],
            risk_level='low'
        )

        result = AggregationResult(
            date='2024-01-01',
            total_stocks=1,
            bullish_count=1,
            bearish_count=0,
            neutral_count=0,
            top_picks=[signal],
            risk_alerts=[],
            market_sentiment=1.0
        )

        report = result.to_report()
        self.assertIn('AI信号聚合报告', report)
        self.assertIn('平安银行', report)


if __name__ == '__main__':
    unittest.main()
