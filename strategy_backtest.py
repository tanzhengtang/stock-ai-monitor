"""
策略库回测示例
测试所有策略的表现
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple

from backtest_engine import BacktestEngine, BacktestConfig
from strategies import STRATEGY_REGISTRY, list_strategies


def generate_sample_data(days: int = 500, start_price: float = 100) -> pd.DataFrame:
    """生成模拟数据"""
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-02', periods=days, freq='B')
    
    # 生成带趋势的价格数据
    trend = np.linspace(0, 0.2, days)  # 上升趋势
    noise = np.random.normal(0, 0.02, days)
    returns = trend / days + noise
    
    prices = start_price * (1 + returns).cumprod()
    
    data = pd.DataFrame({
        'date': dates,
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': prices * (1 + np.random.uniform(0, 0.02, days)),
        'low': prices * (1 - np.random.uniform(0, 0.02, days)),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, days)
    })
    
    return data


def run_backtest(
    strategy,
    data: pd.DataFrame,
    stock_code: str = '000001',
    stock_name: str = '测试股票',
    initial_capital: float = 1000000
) -> Tuple[BacktestEngine, any]:
    """运行回测"""
    config = BacktestConfig(
        initial_capital=initial_capital,
        stop_loss_pct=0.05,
        take_profit_pct=0.1,
        max_holding_days=20
    )
    engine = BacktestEngine(config)
    
    signals = strategy.generate_signals(data)
    
    for i, row in signals.iterrows():
        date = row['date'].strftime('%Y-%m-%d')
        price = row['close']
        
        engine.update_date(date)
        engine.update_prices({stock_code: price})
        
        # 检查止损止盈
        for signal in engine.check_stop_loss({stock_code: price}):
            engine.sell(stock_code, price, signal_reason=signal['reason'])
        for signal in engine.check_take_profit({stock_code: price}):
            engine.sell(stock_code, price, signal_reason=signal['reason'])
        for signal in engine.check_max_holding():
            engine.sell(stock_code, price, signal_reason=signal['reason'])
        
        # 执行策略信号
        if 'position' in row and not pd.isna(row['position']):
            if row['position'] > 0:
                total_assets = engine.get_total_assets()
                amount = total_assets * 0.2
                quantity = int(amount / price / 100) * 100
                if quantity >= 100:
                    engine.buy(stock_code, stock_name, price, quantity, strategy.name)
            elif row['position'] < 0:
                if stock_code in engine.positions:
                    engine.sell(stock_code, price, signal_reason=strategy.name)
        
        engine.take_snapshot()
    
    result = engine.calculate_result(strategy.name)
    return engine, result


def main():
    """主函数"""
    print("=" * 80)
    print("策略库回测 - 全策略测试")
    print("=" * 80)
    
    # 生成数据
    print("\n生成模拟数据...")
    data = generate_sample_data(days=500, start_price=100)
    print(f"数据区间: {data['date'].iloc[0].strftime('%Y-%m-%d')} 至 {data['date'].iloc[-1].strftime('%Y-%m-%d')}")
    print(f"数据量: {len(data)} 条")
    
    # 列出所有策略
    print("\n" + "=" * 80)
    print("可用策略列表")
    print("=" * 80)
    
    strategies_info = list_strategies()
    for i, s in enumerate(strategies_info, 1):
        print(f"{i:2d}. {s['name']:<20} - {s['doc']}")
    
    # 测试所有策略
    print("\n" + "=" * 80)
    print("回测所有策略")
    print("=" * 80)
    
    results = []
    
    # 趋势跟踪策略
    trend_strategies = [
        ('ma', {'short_window': 5, 'long_window': 20}),
        ('ma', {'short_window': 10, 'long_window': 30}),
        ('ema', {'short_window': 12, 'long_window': 26}),
        ('triple_ma', {'short': 5, 'mid': 20, 'long': 60}),
        ('macd', {'fast': 12, 'slow': 26, 'signal': 9}),
        ('adx', {'period': 14, 'threshold': 25}),
    ]
    
    # 动量策略
    momentum_strategies = [
        ('rsi', {'period': 14, 'oversold': 30, 'overbought': 70}),
        ('rsi', {'period': 14, 'oversold': 20, 'overbought': 80}),
        ('kdj', {'k_period': 9, 'd_period': 3}),
        ('momentum', {'period': 20, 'threshold': 0.05}),
        ('williams_r', {'period': 14}),
    ]
    
    # 均值回归策略
    mean_reversion_strategies = [
        ('bollinger', {'window': 20, 'num_std': 2.0}),
        ('bollinger', {'window': 20, 'num_std': 1.5}),
        ('cci', {'period': 20}),
    ]
    
    # 成交量策略
    volume_strategies = [
        ('volume_ma', {'price_window': 20, 'volume_window': 20, 'volume_ratio': 1.5}),
        ('obv', {'window': 20}),
    ]
    
    # 波动率策略
    volatility_strategies = [
        ('atr', {'period': 14, 'multiplier': 2.0}),
    ]
    
    # 复合策略
    composite_strategies = [
        ('multi_indicator', {}),
    ]
    
    all_strategy_configs = (
        trend_strategies + 
        momentum_strategies + 
        mean_reversion_strategies + 
        volume_strategies + 
        volatility_strategies + 
        composite_strategies
    )
    
    for strategy_name, params in all_strategy_configs:
        try:
            strategy = STRATEGY_REGISTRY[strategy_name](**params)
            engine, result = run_backtest(strategy, data)
            
            if result:
                results.append({
                    'name': strategy.name,
                    'category': get_strategy_category(strategy_name),
                    'total_return': result.total_return,
                    'annual_return': result.annual_return,
                    'max_drawdown': result.max_drawdown,
                    'sharpe_ratio': result.sharpe_ratio,
                    'win_rate': result.win_rate,
                    'total_trades': result.total_trades,
                    'profit_factor': result.profit_factor
                })
        except Exception as e:
            print(f"策略 {strategy_name} 回测失败: {e}")
    
    # 按夏普比率排序
    results.sort(key=lambda x: x['sharpe_ratio'], reverse=True)
    
    # 打印结果
    print(f"\n{'排名':<4} {'策略':<25} {'类别':<10} {'收益率':<10} {'最大回撤':<10} {'夏普比率':<10} {'胜率':<8} {'交易次数':<8}")
    print("-" * 85)
    
    for i, r in enumerate(results, 1):
        print(f"{i:<4} {r['name']:<25} {r['category']:<10} {r['total_return']:.2f}%{'':<5} {r['max_drawdown']:.2f}%{'':<5} {r['sharpe_ratio']:.2f}{'':<8} {r['win_rate']:.1f}%{'':<3} {r['total_trades']}")
    
    # 按类别统计
    print("\n" + "=" * 80)
    print("按类别统计")
    print("=" * 80)
    
    categories = {}
    for r in results:
        cat = r['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)
    
    for cat, cat_results in categories.items():
        avg_return = np.mean([r['total_return'] for r in cat_results])
        avg_sharpe = np.mean([r['sharpe_ratio'] for r in cat_results])
        best = max(cat_results, key=lambda x: x['sharpe_ratio'])
        
        print(f"\n{cat}:")
        print(f"  平均收益率: {avg_return:.2f}%")
        print(f"  平均夏普比率: {avg_sharpe:.2f}")
        print(f"  最佳策略: {best['name']} (夏普比率: {best['sharpe_ratio']:.2f})")
    
    # 打印最佳策略详细报告
    if results:
        best = results[0]
        print("\n" + "=" * 80)
        print(f"最佳策略详细报告: {best['name']}")
        print("=" * 80)
        
        strategy_name, params = parse_strategy_name(best['name'])
        strategy = STRATEGY_REGISTRY[strategy_name](**params)
        engine, result = run_backtest(strategy, data)
        
        if result:
            print(engine.format_report(result))


def get_strategy_category(strategy_name: str) -> str:
    """获取策略类别"""
    categories = {
        'ma': '趋势跟踪',
        'ema': '趋势跟踪',
        'triple_ma': '趋势跟踪',
        'macd': '趋势跟踪',
        'adx': '趋势跟踪',
        'rsi': '动量策略',
        'kdj': '动量策略',
        'momentum': '动量策略',
        'williams_r': '动量策略',
        'bollinger': '均值回归',
        'cci': '均值回归',
        'volume_ma': '成交量策略',
        'obv': '成交量策略',
        'atr': '波动率策略',
        'multi_indicator': '复合策略'
    }
    return categories.get(strategy_name, '其他')


def parse_strategy_name(name: str) -> tuple:
    """解析策略名称和参数"""
    parts = name.split('_')
    
    # 尝试匹配已知策略
    for strategy_name in STRATEGY_REGISTRY:
        if name.startswith(strategy_name):
            # 提取参数
            param_str = name[len(strategy_name):].strip('_')
            params = {}
            
            if strategy_name == 'ma' and len(parts) >= 3:
                params = {'short_window': int(parts[1]), 'long_window': int(parts[2])}
            elif strategy_name == 'ema' and len(parts) >= 3:
                params = {'short_window': int(parts[1]), 'long_window': int(parts[2])}
            elif strategy_name == 'rsi' and len(parts) >= 4:
                params = {'period': int(parts[1]), 'oversold': int(parts[2]), 'overbought': int(parts[3])}
            elif strategy_name == 'bollinger' and len(parts) >= 3:
                params = {'window': int(parts[1]), 'num_std': float(parts[2])}
            elif strategy_name == 'macd' and len(parts) >= 4:
                params = {'fast': int(parts[1]), 'slow': int(parts[2]), 'signal': int(parts[3])}
            
            return strategy_name, params
    
    # 默认返回
    return 'ma', {'short_window': 5, 'long_window': 20}


if __name__ == '__main__':
    main()
