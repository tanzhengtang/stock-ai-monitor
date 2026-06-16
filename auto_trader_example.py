"""
自动交易示例
演示如何使用自动交易系统
"""

import time
from datetime import datetime

from auto_trader import (
    SimulatorBroker, AutoOrderManager, RiskController,
    OrderSide, OrderStatus
)


def on_order_filled(order):
    """订单成交回调"""
    print(f"✅ 订单成交: {order.side.value} {order.stock_code} {order.quantity}股 @ {order.filled_price:.2f}")


def on_order_failed(order):
    """订单失败回调"""
    print(f"❌ 订单失败: {order.side.value} {order.stock_code} - {order.remark}")


def main():
    """主函数"""
    print("=" * 60)
    print("自动交易示例")
    print("=" * 60)
    
    # 1. 创建模拟券商
    print("\n1. 初始化模拟券商")
    broker = SimulatorBroker(
        initial_capital=1000000,
        commission_rate=0.0003,
        min_commission=5,
        tax_rate=0.001,
        slippage=0.001
    )
    
    # 设置价格回调
    prices = {
        '600519': 1800.0,
        '600900': 25.0,
        '000858': 150.0
    }
    broker.set_price_callback(lambda code: prices.get(code, 0))
    
    # 连接
    broker.connect()
    print("   模拟券商已连接")
    
    # 2. 创建订单管理器
    print("\n2. 创建订单管理器")
    order_manager = AutoOrderManager(broker)
    order_manager.on_order_filled = on_order_filled
    order_manager.on_order_failed = on_order_failed
    print("   订单管理器已创建")
    
    # 3. 创建风险控制器
    print("\n3. 创建风险控制器")
    risk_controller = RiskController()
    risk_controller.set_initial_assets(1000000)
    print("   风险控制器已创建")
    
    # 4. 获取账户信息
    print("\n4. 获取账户信息")
    account = order_manager.get_account()
    print(f"   总资产: {account.total_assets:,.2f}")
    print(f"   可用资金: {account.cash:,.2f}")
    
    # 5. 执行交易
    print("\n5. 执行交易")
    print("-" * 60)
    
    # 买入贵州茅台
    print("\n买入 600519 贵州茅台:")
    order1 = order_manager.create_buy_order(
        stock_code='600519',
        stock_name='贵州茅台',
        price=1800.0,
        quantity=100
    )
    print(f"   订单状态: {order1.status.value}")
    
    # 买入长江电力
    print("\n买入 600900 长江电力:")
    order2 = order_manager.create_buy_order(
        stock_code='600900',
        stock_name='长江电力',
        price=25.0,
        quantity=1000
    )
    print(f"   订单状态: {order2.status.value}")
    
    # 查看持仓
    print("\n查看持仓:")
    positions = order_manager.get_positions()
    for pos in positions:
        print(f"   {pos.stock_code} {pos.stock_name}: {pos.quantity}股 @ {pos.avg_cost:.2f}")
    
    # 更新价格
    print("\n更新价格:")
    prices['600519'] = 1850.0  # 上涨
    prices['600900'] = 24.0    # 下跌
    
    # 检查止损止盈
    print("\n检查止损止盈:")
    positions = order_manager.get_positions()
    for pos in positions:
        pos.update_price(prices.get(pos.stock_code, pos.current_price))
    
    stop_loss_signals = risk_controller.check_stop_loss(positions)
    take_profit_signals = risk_controller.check_take_profit(positions)
    
    for signal in stop_loss_signals:
        print(f"   ⚠️ 止损信号: {signal['stock_code']} {signal['reason']}")
    
    for signal in take_profit_signals:
        print(f"   ✅ 止盈信号: {signal['stock_code']} {signal['reason']}")
    
    # 卖出盈利股票
    print("\n卖出 600519 贵州茅台 (止盈):")
    order3 = order_manager.create_sell_order(
        stock_code='600519',
        price=1850.0,
        quantity=100
    )
    print(f"   订单状态: {order3.status.value}")
    
    # 6. 查看统计
    print("\n6. 交易统计")
    print("-" * 60)
    print(order_manager.format_statistics())
    
    # 7. 风险状态
    print("7. 风险状态")
    print("-" * 60)
    account = order_manager.get_account()
    risk_status = risk_controller.get_risk_status(account)
    print(f"   仓位比例: {risk_status['position_pct']:.1%}")
    print(f"   现金比例: {risk_status['cash_ratio']:.1%}")
    print(f"   日订单数: {risk_status['daily_order_count']}")
    
    # 8. 最终账户状态
    print("\n8. 最终账户状态")
    print("-" * 60)
    account = order_manager.get_account()
    print(f"   总资产: {account.total_assets:,.2f}")
    print(f"   可用资金: {account.cash:,.2f}")
    print(f"   持仓市值: {account.market_value:,.2f}")
    
    # 断开连接
    broker.disconnect()
    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
