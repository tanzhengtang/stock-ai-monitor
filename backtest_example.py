"""
策略回测示例
使用真实数据进行回测
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from backtest_engine import BacktestEngine, BacktestConfig


class SimpleMAStrategy:
    """简单均线策略
    
    策略逻辑：
    - 买入：5日均线上穿10日均线
    - 卖出：5日均线下穿10日均线 或 触发止损止盈
    """

    def __init__(self, short_window: int = 5, long_window: int = 10):
        self.short_window = short_window
        self.long_window = long_window
        self.name = f"MA{short_window}_{long_window}策略"

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        Args:
            data: 包含close列的DataFrame
            
        Returns:
            添加了signal列的DataFrame
        """
        df = data.copy()
        
        # 计算均线
        df['ma_short'] = df['close'].rolling(window=self.short_window).mean()
        df['ma_long'] = df['close'].rolling(window=self.long_window).mean()
        
        # 生成信号
        df['signal'] = 0
        df.loc[df['ma_short'] > df['ma_long'], 'signal'] = 1   # 买入信号
        df.loc[df['ma_short'] <= df['ma_long'], 'signal'] = -1  # 卖出信号
        
        # 只在信号变化时交易
        df['position'] = df['signal'].diff()
        
        return df


class RSIstrategy:
    """RSI策略
    
    策略逻辑：
    - 买入：RSI < 30（超卖）
    - 卖出：RSI > 70（超买）或 触发止损止盈
    """

    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.name = f"RSI{period}策略"

    def calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """计算RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        Args:
            data: 包含close列的DataFrame
            
        Returns:
            添加了signal列的DataFrame
        """
        df = data.copy()
        
        # 计算RSI
        df['rsi'] = self.calculate_rsi(df['close'])
        
        # 生成信号
        df['signal'] = 0
        df.loc[df['rsi'] < self.oversold, 'signal'] = 1    # 买入信号
        df.loc[df['rsi'] > self.overbought, 'signal'] = -1  # 卖出信号
        
        # 只在信号变化时交易
        df['position'] = df['signal'].diff()
        
        return df


def generate_sample_data(days: int = 252, start_price: float = 100) -> pd.DataFrame:
    """
    生成模拟数据
    
    Args:
        days: 交易天数
        start_price: 起始价格
        
    Returns:
        模拟数据DataFrame
    """
    dates = pd.date_range(start='2024-01-02', periods=days, freq='B')
    
    # 生成随机价格
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.02, days)  # 日收益率
    prices = start_price * (1 + returns).cumprod()
    
    # 生成OHLCV数据
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
    initial_capital: float = 1000000,
    stock_code: str = '000001',
    stock_name: str = '测试股票'
) -> dict:
    """
    运行回测
    
    Args:
        strategy: 策略对象
        data: 历史数据
        initial_capital: 初始资金
        stock_code: 股票代码
        stock_name: 股票名称
        
    Returns:
        回测结果
    """
    # 创建回测引擎
    config = BacktestConfig(
        initial_capital=initial_capital,
        stop_loss_pct=0.05,
        take_profit_pct=0.1,
        max_holding_days=20
    )
    engine = BacktestEngine(config)
    
    # 生成信号
    signals = strategy.generate_signals(data)
    
    # 运行回测
    for i, row in signals.iterrows():
        date = row['date'].strftime('%Y-%m-%d')
        price = row['close']
        
        # 更新日期和价格
        engine.update_date(date)
        engine.update_prices({stock_code: price})
        
        # 检查止损止盈
        stop_loss_signals = engine.check_stop_loss({stock_code: price})
        take_profit_signals = engine.check_take_profit({stock_code: price})
        max_holding_signals = engine.check_max_holding()
        
        # 执行止损止盈
        for signal in stop_loss_signals + take_profit_signals + max_holding_signals:
            engine.sell(stock_code, price, signal_reason=signal['reason'])
        
        # 执行策略信号
        if 'position' in row:
            if row['position'] > 0:  # 买入信号
                # 计算买入数量（使用20%仓位）
                total_assets = engine.get_total_assets()
                amount = total_assets * 0.2
                quantity = int(amount / price / 100) * 100
                if quantity >= 100:
                    engine.buy(stock_code, stock_name, price, quantity, '均线金叉')
            
            elif row['position'] < 0:  # 卖出信号
                if stock_code in engine.positions:
                    engine.sell(stock_code, price, signal_reason='均线死叉')
        
        # 记录快照
        engine.take_snapshot()
    
    # 计算结果
    result = engine.calculate_result(strategy.name)
    
    return {
        'result': result,
        'engine': engine,
        'signals': signals
    }


def main():
    """主函数"""
    print("=" * 70)
    print("策略回测示例")
    print("=" * 70)
    
    # 生成模拟数据
    print("\n生成模拟数据...")
    data = generate_sample_data(days=252, start_price=100)
    print(f"数据区间: {data['date'].iloc[0].strftime('%Y-%m-%d')} 至 {data['date'].iloc[-1].strftime('%Y-%m-%d')}")
    print(f"数据量: {len(data)} 条")
    
    # 回测均线策略
    print("\n" + "=" * 70)
    print("回测均线策略")
    print("=" * 70)
    
    ma_strategy = SimpleMAStrategy(short_window=5, long_window=10)
    ma_result = run_backtest(ma_strategy, data, stock_code='000001', stock_name='测试股票')
    
    print(ma_result['engine'].format_report(ma_result['result']))
    
    # 回测RSI策略
    print("\n" + "=" * 70)
    print("回测RSI策略")
    print("=" * 70)
    
    rsi_strategy = RSIstrategy(period=14, oversold=30, overbought=70)
    rsi_result = run_backtest(rsi_strategy, data, stock_code='000001', stock_name='测试股票')
    
    print(rsi_result['engine'].format_report(rsi_result['result']))
    
    # 策略对比
    print("\n" + "=" * 70)
    print("策略对比")
    print("=" * 70)
    
    ma_res = ma_result['result']
    rsi_res = rsi_result['result']
    
    print(f"""
{'指标':<20} {'均线策略':<15} {'RSI策略':<15}
{'-'*50}
{'总收益率':<20} {ma_res.total_return:.2f}%{'':<10} {rsi_res.total_return:.2f}%
{'年化收益率':<20} {ma_res.annual_return:.2f}%{'':<10} {rsi_res.annual_return:.2f}%
{'最大回撤':<20} {ma_res.max_drawdown:.2f}%{'':<10} {rsi_res.max_drawdown:.2f}%
{'夏普比率':<20} {ma_res.sharpe_ratio:.2f}{'':<12} {rsi_res.sharpe_ratio:.2f}
{'胜率':<20} {ma_res.win_rate:.1f}%{'':<11} {rsi_res.win_rate:.1f}%
{'交易次数':<20} {ma_res.total_trades:<15} {rsi_res.total_trades}
""")


if __name__ == '__main__':
    main()
