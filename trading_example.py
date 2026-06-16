"""
量化交易示例
演示如何使用模拟交易系统
"""

from trading import (
    SimulatedBroker, OrderManager, StrategyEngine,
    SignalStrategy, RiskManager, RiskConfig,
    OrderSide
)
from signal_aggregator import AggregatedSignal, SignalType


def main():
    """主函数"""
    print("=" * 60)
    print("量化交易系统示例")
    print("=" * 60)
    print()

    # 1. 创建模拟券商
    print("【1. 初始化模拟券商】")
    broker = SimulatedBroker(
        initial_capital=1000000,  # 初始资金100万
        commission_rate=0.0003,   # 佣金万分之三
        min_commission=5,         # 最低佣金5元
        tax_rate=0.001,           # 印花税千分之一
        slippage=0.001            # 滑点千分之一
    )
    
    # 设置价格回调
    prices = {
        '600519': 1800.0,  # 贵州茅台
        '600900': 25.0,    # 长江电力
        '000858': 150.0,   # 五粮液
    }
    broker.set_price_callback(lambda code: prices.get(code, 0))
    print(f"  初始资金: {broker.initial_capital:,.0f} 元")
    print()

    # 2. 创建订单管理器
    print("【2. 创建订单管理器】")
    order_manager = OrderManager(broker)
    print("  订单管理器已创建")
    print()

    # 3. 创建风险管理器
    print("【3. 创建风险管理器】")
    risk_config = RiskConfig(
        max_position_pct=0.2,      # 单只股票最大仓位20%
        max_total_position_pct=0.8, # 最大总仓位80%
        stop_loss_pct=0.05,        # 止损5%
        take_profit_pct=0.15,      # 止盈15%
        max_orders_per_day=10      # 每日最大订单数
    )
    risk_manager = RiskManager(risk_config)
    risk_manager.set_initial_assets(broker.initial_capital)
    print("  风险管理器已创建")
    print()

    # 4. 创建策略引擎
    print("【4. 创建策略引擎】")
    strategy_engine = StrategyEngine(broker)
    
    # 添加信号策略
    signal_strategy = SignalStrategy(
        name="SignalStrategy",
        min_score=60,              # 最低买入评分60
        max_position_pct=0.2,      # 最大仓位20%
        position_size=1            # 基础交易1手（100股）
    )
    strategy_engine.add_strategy(signal_strategy)
    print("  策略引擎已创建")
    print()

    # 5. 模拟交易
    print("【5. 模拟交易】")
    print("-" * 60)
    
    # 模拟AI信号
    signals = [
        AggregatedSignal(
            stock_code='600519',
            stock_name='贵州茅台',
            weighted_score=75.0,
            consensus=SignalType.BUY,
            confidence=0.8,
            platform_signals=[],
            risk_level='low'
        ),
        AggregatedSignal(
            stock_code='600900',
            stock_name='长江电力',
            weighted_score=70.0,
            consensus=SignalType.BUY,
            confidence=0.75,
            platform_signals=[],
            risk_level='low'
        ),
    ]
    
    # 执行策略
    orders = strategy_engine.execute_signals(signals)
    
    print(f"\n  生成订单数: {len(orders)}")
    for order in orders:
        print(f"    {order.side.value} {order.stock_code} {order.stock_name} "
              f"{order.quantity}股 @ {order.price:.2f} - {order.status.value}")
    
    # 6. 查看账户状态
    print("\n【6. 账户状态】")
    print("-" * 60)
    
    account = broker.get_account()
    print(f"  总资产: {account.total_assets:,.2f} 元")
    print(f"  可用资金: {account.cash:,.2f} 元")
    print(f"  持仓市值: {account.market_value:,.2f} 元")
    print(f"  总盈亏: {account.total_pnl:,.2f} 元 ({account.total_pnl/1000000*100:.2f}%)")
    print(f"  佣金: {account.commission:,.2f} 元")
    print(f"  印花税: {account.tax:,.2f} 元")
    
    # 7. 查看持仓
    print("\n【7. 持仓详情】")
    print("-" * 60)
    
    positions = broker.get_positions()
    if positions:
        for pos in positions:
            print(f"  {pos.stock_code} {pos.stock_name}")
            print(f"    数量: {pos.quantity} 股")
            print(f"    成本: {pos.avg_cost:.2f} 元")
            print(f"    现价: {pos.current_price:.2f} 元")
            print(f"    市值: {pos.market_value:,.2f} 元")
            print(f"    盈亏: {pos.unrealized_pnl:,.2f} 元 ({pos.unrealized_pnl_pct:.2f}%)")
    else:
        print("  无持仓")
    
    # 8. 查看订单
    print("\n【8. 订单记录】")
    print("-" * 60)
    
    orders = order_manager.get_orders()
    for order in orders:
        print(f"  {order.order_id} | {order.side.value} {order.stock_code} "
              f"{order.quantity}股 @ {order.price:.2f} | {order.status.value}")
    
    # 9. 风险状态
    print("\n【9. 风险状态】")
    print("-" * 60)
    
    risk_status = risk_manager.get_risk_status(account)
    print(f"  仓位比例: {risk_status['position_pct']:.1%}")
    print(f"  现金比例: {risk_status['cash_ratio']:.1%}")
    print(f"  回撤比例: {risk_status['drawdown_pct']:.1%}")
    print(f"  日订单数: {risk_status['daily_order_count']}/{risk_status['max_daily_orders']}")
    
    # 10. 订单摘要
    print("\n【10. 订单摘要】")
    print("-" * 60)
    
    summary = order_manager.get_order_summary()
    print(f"  总订单数: {summary['total_orders']}")
    print(f"  买入订单: {summary['buy_count']}")
    print(f"  卖出订单: {summary['sell_count']}")
    print(f"  成交金额: {summary['total_buy_amount']:,.2f} 元")

    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
