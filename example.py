"""
信号聚合器使用示例
"""

from datetime import datetime
from signal_aggregator import (
    SignalAggregator, PlatformSignal, Platform, SignalType
)


def create_sample_signals():
    """创建示例信号"""
    signals = [
        # 平安银行 - 多平台看多
        PlatformSignal(
            platform=Platform.EASTMONEY,
            stock_code='000001',
            stock_name='平安银行',
            score=75,
            signal_type=SignalType.BUY,
            confidence=0.8,
            reasons=['技术面良好', '资金流入', '业绩稳定']
        ),
        PlatformSignal(
            platform=Platform.TONGHUASHUN,
            stock_code='000001',
            stock_name='平安银行',
            score=80,
            signal_type=SignalType.BUY,
            confidence=0.85,
            reasons=['AI评分高', '行业前景好', '技术面良好']
        ),
        PlatformSignal(
            platform=Platform.XUEQIU,
            stock_code='000001',
            stock_name='平安银行',
            score=72,
            signal_type=SignalType.BUY,
            confidence=0.75,
            reasons=['机构看好', '估值合理']
        ),

        # 万科A - 多平台看空
        PlatformSignal(
            platform=Platform.EASTMONEY,
            stock_code='000002',
            stock_name='万科A',
            score=30,
            signal_type=SignalType.SELL,
            confidence=0.7,
            reasons=['房地产调控', '业绩下滑']
        ),
        PlatformSignal(
            platform=Platform.TONGHUASHUN,
            stock_code='000002',
            stock_name='万科A',
            score=25,
            signal_type=SignalType.SELL,
            confidence=0.75,
            reasons=['行业低迷', '资金流出']
        ),

        # 贵州茅台 - 信号分歧
        PlatformSignal(
            platform=Platform.EASTMONEY,
            stock_code='600519',
            stock_name='贵州茅台',
            score=85,
            signal_type=SignalType.STRONG_BUY,
            confidence=0.9,
            reasons=['业绩优秀', '品牌价值高']
        ),
        PlatformSignal(
            platform=Platform.TONGHUASHUN,
            stock_code='600519',
            stock_name='贵州茅台',
            score=45,
            signal_type=SignalType.NEUTRAL,
            confidence=0.6,
            reasons=['估值偏高', '短期回调风险']
        ),

        # 比亚迪 - 强烈看多
        PlatformSignal(
            platform=Platform.EASTMONEY,
            stock_code='002594',
            stock_name='比亚迪',
            score=90,
            signal_type=SignalType.STRONG_BUY,
            confidence=0.9,
            reasons=['新能源龙头', '技术领先', '政策支持']
        ),
        PlatformSignal(
            platform=Platform.TONGHUASHUN,
            stock_code='002594',
            stock_name='比亚迪',
            score=88,
            signal_type=SignalType.STRONG_BUY,
            confidence=0.88,
            reasons=['销量增长', '产业链优势']
        ),
        PlatformSignal(
            platform=Platform.XUEQIU,
            stock_code='002594',
            stock_name='比亚迪',
            score=85,
            signal_type=SignalType.BUY,
            confidence=0.82,
            reasons=['市场看好', '技术突破']
        ),
    ]

    return signals


def main():
    """主函数"""
    print("=" * 60)
    print("信号聚合器示例")
    print("=" * 60)
    print()

    # 创建聚合器
    aggregator = SignalAggregator()

    # 添加信号
    signals = create_sample_signals()
    aggregator.add_signals(signals)

    # 获取统计信息
    stats = aggregator.get_statistics()
    print("【统计信息】")
    print(f"  总股票数: {stats['total_stocks']}")
    print(f"  总信号数: {stats['total_signals']}")
    print(f"  平均信号数: {stats['avg_signals_per_stock']:.1f}")
    print(f"  平台分布: {stats['platform_distribution']}")
    print()

    # 聚合所有信号
    result = aggregator.aggregate_all()

    # 输出报告
    print(result.to_report())

    # 详细分析单个股票
    print("\n" + "=" * 60)
    print("详细分析")
    print("=" * 60)

    for stock_code in aggregator.get_all_stock_codes():
        aggregated = aggregator.aggregate_stock(stock_code)
        if aggregated:
            print(f"\n【{aggregated.stock_code} {aggregated.stock_name}】")
            print(f"  加权评分: {aggregated.weighted_score:.1f}")
            print(f"  共识信号: {aggregated.consensus.value}")
            print(f"  置信度: {aggregated.confidence:.1%}")
            print(f"  风险等级: {aggregated.risk_level}")
            print(f"  信号来源: {aggregated.platform_names}")
            print(f"  共识理由: {aggregated.consensus_reasons}")

            # 各平台详细信号
            print("  各平台信号:")
            for signal in aggregated.platform_signals:
                print(f"    - {signal.platform.value}: "
                      f"{signal.score}分 ({signal.signal_type.value})")


if __name__ == '__main__':
    main()
