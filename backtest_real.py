"""
真实数据回测系统
使用akshare获取历史数据进行回测
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import warnings
warnings.filterwarnings('ignore')

from backtest_engine import BacktestEngine, BacktestConfig


class DataManager:
    """数据管理器
    
    使用akshare获取A股历史数据
    """

    def __init__(self):
        self.logger = logging.getLogger('DataManager')
        try:
            import akshare as ak
            self.ak = ak
        except ImportError:
            self.ak = None
            self.logger.warning("akshare未安装")

    def get_stock_data(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> Optional[pd.DataFrame]:
        """
        获取股票历史数据
        
        Args:
            stock_code: 股票代码，如 '600519'
            start_date: 开始日期，如 '20230101'
            end_date: 结束日期，如 '20241231'
            adjust: 复权方式，'qfq'前复权，'hfq'后复权，''不复权
            
        Returns:
            历史数据DataFrame
        """
        if not self.ak:
            self.logger.error("akshare未安装")
            return None
        
        try:
            # 使用akshare获取数据
            df = self.ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
            
            if df.empty:
                self.logger.warning(f"获取数据为空: {stock_code}")
                return None
            
            # 重命名列
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '换手率': 'turnover'
            })
            
            # 转换日期格式
            df['date'] = pd.to_datetime(df['date'])
            
            # 按日期排序
            df = df.sort_values('date').reset_index(drop=True)
            
            self.logger.info(f"获取数据成功: {stock_code}, {len(df)}条")
            return df
            
        except Exception as e:
            self.logger.error(f"获取数据失败: {stock_code}, {e}")
            return None

    def get_multiple_stocks(
        self,
        stock_codes: List[str],
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> Dict[str, pd.DataFrame]:
        """
        获取多只股票数据
        
        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权方式
            
        Returns:
            {股票代码: DataFrame}
        """
        data = {}
        for code in stock_codes:
            df = self.get_stock_data(code, start_date, end_date, adjust)
            if df is not None:
                data[code] = df
        return data


class Strategy:
    """策略基类"""

    def __init__(self, name: str):
        self.name = name

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号"""
        raise NotImplementedError


class MAStrategy(Strategy):
    """均线策略"""

    def __init__(self, short_window: int = 5, long_window: int = 10):
        super().__init__(f"MA{short_window}_{long_window}")
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df['ma_short'] = df['close'].rolling(window=self.short_window).mean()
        df['ma_long'] = df['close'].rolling(window=self.long_window).mean()
        
        df['signal'] = 0
        df.loc[df['ma_short'] > df['ma_long'], 'signal'] = 1
        df.loc[df['ma_short'] <= df['ma_long'], 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        return df


class RSIStrategy(Strategy):
    """RSI策略"""

    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        super().__init__(f"RSI{period}_{oversold}_{overbought}")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def calculate_rsi(self, prices: pd.Series) -> pd.Series:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df['rsi'] = self.calculate_rsi(df['close'])
        
        df['signal'] = 0
        df.loc[df['rsi'] < self.oversold, 'signal'] = 1
        df.loc[df['rsi'] > self.overbought, 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        return df


class MACDStrategy(Strategy):
    """MACD策略"""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__(f"MACD_{fast}_{slow}_{signal}")
        self.fast = fast
        self.slow = slow
        self.signal_period = signal

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        # 计算MACD
        exp1 = df['close'].ewm(span=self.fast, adjust=False).mean()
        exp2 = df['close'].ewm(span=self.slow, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal_line'] = df['macd'].ewm(span=self.signal_period, adjust=False).mean()
        df['histogram'] = df['macd'] - df['signal_line']
        
        # 生成信号
        df['signal'] = 0
        df.loc[df['macd'] > df['signal_line'], 'signal'] = 1
        df.loc[df['macd'] <= df['signal_line'], 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        return df


class BollingerStrategy(Strategy):
    """布林带策略"""

    def __init__(self, window: int = 20, num_std: float = 2.0):
        super().__init__(f"Bollinger_{window}_{num_std}")
        self.window = window
        self.num_std = num_std

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        # 计算布林带
        df['ma'] = df['close'].rolling(window=self.window).mean()
        df['std'] = df['close'].rolling(window=self.window).std()
        df['upper'] = df['ma'] + (df['std'] * self.num_std)
        df['lower'] = df['ma'] - (df['std'] * self.num_std)
        
        # 生成信号
        df['signal'] = 0
        df.loc[df['close'] < df['lower'], 'signal'] = 1   # 超卖买入
        df.loc[df['close'] > df['upper'], 'signal'] = -1   # 超买卖出
        df['position'] = df['signal'].diff()
        
        return df


def run_backtest(
    strategy: Strategy,
    data: pd.DataFrame,
    stock_code: str,
    stock_name: str,
    initial_capital: float = 1000000,
    position_pct: float = 0.2
) -> Tuple[BacktestEngine, any]:
    """
    运行回测
    
    Args:
        strategy: 策略对象
        data: 历史数据
        stock_code: 股票代码
        stock_name: 股票名称
        initial_capital: 初始资金
        position_pct: 仓位比例
        
    Returns:
        (回测引擎, 回测结果)
    """
    config = BacktestConfig(
        initial_capital=initial_capital,
        stop_loss_pct=0.05,
        take_profit_pct=0.1,
        max_holding_days=20
    )
    engine = BacktestEngine(config)
    
    # 生成信号
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
            if row['position'] > 0:  # 买入
                total_assets = engine.get_total_assets()
                amount = total_assets * position_pct
                quantity = int(amount / price / 100) * 100
                if quantity >= 100:
                    engine.buy(stock_code, stock_name, price, quantity, strategy.name)
            elif row['position'] < 0:  # 卖出
                if stock_code in engine.positions:
                    engine.sell(stock_code, price, signal_reason=strategy.name)
        
        engine.take_snapshot()
    
    result = engine.calculate_result(strategy.name)
    return engine, result


def optimize_parameters(
    strategy_class,
    data: pd.DataFrame,
    stock_code: str,
    stock_name: str,
    param_grid: Dict[str, List],
    initial_capital: float = 1000000
) -> List[Dict]:
    """
    参数优化
    
    Args:
        strategy_class: 策略类
        data: 历史数据
        stock_code: 股票代码
        stock_name: 股票名称
        param_grid: 参数网格
        initial_capital: 初始资金
        
    Returns:
        优化结果列表
    """
    results = []
    
    # 生成参数组合
    import itertools
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    
    for combination in itertools.product(*param_values):
        params = dict(zip(param_names, combination))
        
        try:
            # 创建策略
            strategy = strategy_class(**params)
            
            # 运行回测
            engine, result = run_backtest(
                strategy, data, stock_code, stock_name, initial_capital
            )
            
            if result:
                results.append({
                    'params': params,
                    'strategy_name': strategy.name,
                    'total_return': result.total_return,
                    'annual_return': result.annual_return,
                    'max_drawdown': result.max_drawdown,
                    'sharpe_ratio': result.sharpe_ratio,
                    'win_rate': result.win_rate,
                    'total_trades': result.total_trades,
                    'profit_factor': result.profit_factor
                })
        except Exception as e:
            logging.warning(f"参数组合失败: {params}, {e}")
    
    # 按夏普比率排序
    results.sort(key=lambda x: x['sharpe_ratio'], reverse=True)
    
    return results


def main():
    """主函数"""
    print("=" * 70)
    print("真实数据回测系统")
    print("=" * 70)
    
    # 获取数据
    print("\n获取历史数据...")
    data_manager = DataManager()
    
    # 获取贵州茅台数据
    stock_code = "600519"
    stock_name = "贵州茅台"
    start_date = "20230101"
    end_date = "20241231"
    
    data = data_manager.get_stock_data(stock_code, start_date, end_date)
    
    if data is None or data.empty:
        print("获取数据失败，使用模拟数据")
        # 使用模拟数据
        np.random.seed(42)
        dates = pd.date_range(start='2023-01-02', periods=252, freq='B')
        prices = 1800 * (1 + np.random.normal(0.0005, 0.02, 252)).cumprod()
        data = pd.DataFrame({
            'date': dates,
            'open': prices * 0.99,
            'high': prices * 1.02,
            'low': prices * 0.98,
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, 252)
        })
    
    print(f"股票: {stock_code} {stock_name}")
    print(f"数据区间: {data['date'].iloc[0].strftime('%Y-%m-%d')} 至 {data['date'].iloc[-1].strftime('%Y-%m-%d')}")
    print(f"数据量: {len(data)} 条")
    
    # 定义策略
    strategies = [
        MAStrategy(5, 10),
        MAStrategy(5, 20),
        RSIStrategy(14, 30, 70),
        RSIStrategy(14, 20, 80),
        MACDStrategy(12, 26, 9),
        BollingerStrategy(20, 2.0),
    ]
    
    # 运行回测
    print("\n" + "=" * 70)
    print("多策略回测")
    print("=" * 70)
    
    all_results = []
    
    for strategy in strategies:
        engine, result = run_backtest(
            strategy, data, stock_code, stock_name
        )
        
        if result:
            all_results.append({
                'strategy': strategy.name,
                'result': result,
                'engine': engine
            })
            
            print(f"\n{strategy.name}:")
            print(f"  总收益率: {result.total_return:.2f}%")
            print(f"  最大回撤: {result.max_drawdown:.2f}%")
            print(f"  夏普比率: {result.sharpe_ratio:.2f}")
            print(f"  胜率: {result.win_rate:.1f}%")
            print(f"  交易次数: {result.total_trades}")
    
    # 策略对比
    print("\n" + "=" * 70)
    print("策略对比排名")
    print("=" * 70)
    
    # 按夏普比率排序
    all_results.sort(key=lambda x: x['result'].sharpe_ratio, reverse=True)
    
    print(f"\n{'排名':<5} {'策略':<20} {'收益率':<10} {'最大回撤':<10} {'夏普比率':<10} {'胜率':<10}")
    print("-" * 65)
    
    for i, item in enumerate(all_results, 1):
        r = item['result']
        print(f"{i:<5} {item['strategy']:<20} {r.total_return:.2f}%{'':<5} {r.max_drawdown:.2f}%{'':<5} {r.sharpe_ratio:.2f}{'':<8} {r.win_rate:.1f}%")
    
    # 打印最佳策略详细报告
    if all_results:
        best = all_results[0]
        print("\n" + "=" * 70)
        print(f"最佳策略: {best['strategy']}")
        print("=" * 70)
        print(best['engine'].format_report(best['result']))
    
    # 参数优化示例
    print("\n" + "=" * 70)
    print("参数优化示例 (MA策略)")
    print("=" * 70)
    
    param_grid = {
        'short_window': [3, 5, 10],
        'long_window': [10, 20, 30]
    }
    
    optimization_results = optimize_parameters(
        MAStrategy, data, stock_code, stock_name, param_grid
    )
    
    print(f"\n{'参数':<20} {'收益率':<10} {'最大回撤':<10} {'夏普比率':<10} {'胜率':<10}")
    print("-" * 60)
    
    for item in optimization_results[:5]:  # 显示前5个
        params = item['params']
        param_str = f"MA{params['short_window']}_{params['long_window']}"
        print(f"{param_str:<20} {item['total_return']:.2f}%{'':<5} {item['max_drawdown']:.2f}%{'':<5} {item['sharpe_ratio']:.2f}{'':<8} {item['win_rate']:.1f}%")


if __name__ == '__main__':
    main()
