"""
策略库
包含多种量化交易策略
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional


class BaseStrategy:
    """策略基类"""

    def __init__(self, name: str):
        self.name = name

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号"""
        raise NotImplementedError


# ==================== 趋势跟踪策略 ====================

class MAStrategy(BaseStrategy):
    """均线交叉策略
    
    买入：短期均线上穿长期均线
    卖出：短期均线下穿长期均线
    """

    def __init__(self, short_window: int = 5, long_window: int = 20):
        super().__init__(f"MA_{short_window}_{long_window}")
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


class EMAStrategy(BaseStrategy):
    """指数均线策略
    
    使用EMA代替SMA，对近期价格更敏感
    """

    def __init__(self, short_window: int = 12, long_window: int = 26):
        super().__init__(f"EMA_{short_window}_{long_window}")
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df['ema_short'] = df['close'].ewm(span=self.short_window, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=self.long_window, adjust=False).mean()
        
        df['signal'] = 0
        df.loc[df['ema_short'] > df['ema_long'], 'signal'] = 1
        df.loc[df['ema_short'] <= df['ema_long'], 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        return df


class TripleMAStrategy(BaseStrategy):
    """三均线策略
    
    买入：短期 > 中期 > 长期（多头排列）
    卖出：短期 < 中期 或 中期 < 长期
    """

    def __init__(self, short: int = 5, mid: int = 20, long: int = 60):
        super().__init__(f"TripleMA_{short}_{mid}_{long}")
        self.short = short
        self.mid = mid
        self.long = long

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df['ma_short'] = df['close'].rolling(window=self.short).mean()
        df['ma_mid'] = df['close'].rolling(window=self.mid).mean()
        df['ma_long'] = df['close'].rolling(window=self.long).mean()
        
        # 多头排列买入
        df['signal'] = 0
        bullish = (df['ma_short'] > df['ma_mid']) & (df['ma_mid'] > df['ma_long'])
        df.loc[bullish, 'signal'] = 1
        
        # 任一均线死叉卖出
        bearish = (df['ma_short'] < df['ma_mid']) | (df['ma_mid'] < df['ma_long'])
        df.loc[bearish, 'signal'] = -1
        
        df['position'] = df['signal'].diff()
        return df


class MACDStrategy(BaseStrategy):
    """MACD策略
    
    买入：MACD金叉（MACD线上穿信号线）
    卖出：MACD死叉（MACD线下穿信号线）
    """

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__(f"MACD_{fast}_{slow}_{signal}")
        self.fast = fast
        self.slow = slow
        self.signal_period = signal

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        exp1 = df['close'].ewm(span=self.fast, adjust=False).mean()
        exp2 = df['close'].ewm(span=self.slow, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal_line'] = df['macd'].ewm(span=self.signal_period, adjust=False).mean()
        df['histogram'] = df['macd'] - df['signal_line']
        
        df['signal'] = 0
        df.loc[df['macd'] > df['signal_line'], 'signal'] = 1
        df.loc[df['macd'] <= df['signal_line'], 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        return df


class ADXStrategy(BaseStrategy):
    """ADX趋势强度策略
    
    买入：ADX > 25 且 +DI > -DI（强上升趋势）
    卖出：ADX > 25 且 +DI < -DI（强下降趋势）
    观望：ADX < 25（趋势不明）
    """

    def __init__(self, period: int = 14, threshold: float = 25):
        super().__init__(f"ADX_{period}_{threshold}")
        self.period = period
        self.threshold = threshold

    def calculate_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算ADX指标"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        # 计算TR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # 计算+DM和-DM
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # 计算+DI和-DI
        atr = tr.rolling(window=self.period).mean()
        plus_di = 100 * pd.Series(plus_dm).rolling(window=self.period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(window=self.period).mean() / atr
        
        # 计算ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=self.period).mean()
        
        df['plus_di'] = plus_di.values
        df['minus_di'] = minus_di.values
        df['adx'] = adx.values
        
        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df = self.calculate_adx(df)
        
        df['signal'] = 0
        
        # 强上升趋势
        bullish = (df['adx'] > self.threshold) & (df['plus_di'] > df['minus_di'])
        df.loc[bullish, 'signal'] = 1
        
        # 强下降趋势
        bearish = (df['adx'] > self.threshold) & (df['plus_di'] < df['minus_di'])
        df.loc[bearish, 'signal'] = -1
        
        df['position'] = df['signal'].diff()
        return df


# ==================== 动量策略 ====================

class RSIStrategy(BaseStrategy):
    """RSI策略
    
    买入：RSI < oversold（超卖）
    卖出：RSI > overbought（超买）
    """

    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        super().__init__(f"RSI_{period}_{oversold}_{overbought}")
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


class KDJStrategy(BaseStrategy):
    """KDJ策略
    
    买入：K线上穿D线且J < 20
    卖出：K线下穿D线且J > 80
    """

    def __init__(self, k_period: int = 9, d_period: int = 3):
        super().__init__(f"KDJ_{k_period}_{d_period}")
        self.k_period = k_period
        self.d_period = d_period

    def calculate_kdj(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算KDJ指标"""
        low_min = df['low'].rolling(window=self.k_period).min()
        high_max = df['high'].rolling(window=self.k_period).max()
        
        rsv = 100 * (df['close'] - low_min) / (high_max - low_min)
        
        df['k'] = rsv.ewm(com=self.d_period - 1, adjust=False).mean()
        df['d'] = df['k'].ewm(com=self.d_period - 1, adjust=False).mean()
        df['j'] = 3 * df['k'] - 2 * df['d']
        
        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df = self.calculate_kdj(df)
        
        df['signal'] = 0
        
        # K上穿D且超卖
        buy_signal = (df['k'] > df['d']) & (df['k'].shift(1) <= df['d'].shift(1)) & (df['j'] < 20)
        df.loc[buy_signal, 'signal'] = 1
        
        # K下穿D且超买
        sell_signal = (df['k'] < df['d']) & (df['k'].shift(1) >= df['d'].shift(1)) & (df['j'] > 80)
        df.loc[sell_signal, 'signal'] = -1
        
        df['position'] = df['signal'].diff()
        return df


class MomentumStrategy(BaseStrategy):
    """动量策略
    
    买入：N日收益率 > 阈值
    卖出：N日收益率 < -阈值
    """

    def __init__(self, period: int = 20, threshold: float = 0.05):
        super().__init__(f"Momentum_{period}_{int(threshold*100)}")
        self.period = period
        self.threshold = threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        # 计算N日收益率
        df['momentum'] = df['close'].pct_change(periods=self.period)
        
        df['signal'] = 0
        df.loc[df['momentum'] > self.threshold, 'signal'] = 1
        df.loc[df['momentum'] < -self.threshold, 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        return df


class WilliamsRStrategy(BaseStrategy):
    """威廉指标策略
    
    买入：%R < -80（超卖）
    卖出：%R > -20（超买）
    """

    def __init__(self, period: int = 14):
        super().__init__(f"WilliamsR_{period}")
        self.period = period

    def calculate_williams_r(self, df: pd.DataFrame) -> pd.Series:
        highest_high = df['high'].rolling(window=self.period).max()
        lowest_low = df['low'].rolling(window=self.period).min()
        wr = -100 * (highest_high - df['close']) / (highest_high - lowest_low)
        return wr

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df['williams_r'] = self.calculate_williams_r(df)
        
        df['signal'] = 0
        df.loc[df['williams_r'] < -80, 'signal'] = 1
        df.loc[df['williams_r'] > -20, 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        return df


# ==================== 均值回归策略 ====================

class BollingerStrategy(BaseStrategy):
    """布林带策略
    
    买入：价格触及下轨
    卖出：价格触及上轨
    """

    def __init__(self, window: int = 20, num_std: float = 2.0):
        super().__init__(f"Bollinger_{window}_{num_std}")
        self.window = window
        self.num_std = num_std

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        df['ma'] = df['close'].rolling(window=self.window).mean()
        df['std'] = df['close'].rolling(window=self.window).std()
        df['upper'] = df['ma'] + (df['std'] * self.num_std)
        df['lower'] = df['ma'] - (df['std'] * self.num_std)
        
        df['signal'] = 0
        df.loc[df['close'] < df['lower'], 'signal'] = 1
        df.loc[df['close'] > df['upper'], 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        return df


class CCIStrategy(BaseStrategy):
    """CCI策略
    
    买入：CCI < -100（超卖）
    卖出：CCI > 100（超买）
    """

    def __init__(self, period: int = 20):
        super().__init__(f"CCI_{period}")
        self.period = period

    def calculate_cci(self, df: pd.DataFrame) -> pd.Series:
        tp = (df['high'] + df['low'] + df['close']) / 3
        ma = tp.rolling(window=self.period).mean()
        md = tp.rolling(window=self.period).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
        cci = (tp - ma) / (0.015 * md)
        return cci

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df['cci'] = self.calculate_cci(df)
        
        df['signal'] = 0
        df.loc[df['cci'] < -100, 'signal'] = 1
        df.loc[df['cci'] > 100, 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        return df


# ==================== 成交量策略 ====================

class VolumeMAStrategy(BaseStrategy):
    """成交量均线策略
    
    买入：价格上穿均线 且 成交量放大
    卖出：价格下穿均线 且 成交量放大
    """

    def __init__(self, price_window: int = 20, volume_window: int = 20, volume_ratio: float = 1.5):
        super().__init__(f"VolMA_{price_window}_{volume_window}")
        self.price_window = price_window
        self.volume_window = volume_window
        self.volume_ratio = volume_ratio

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        df['price_ma'] = df['close'].rolling(window=self.price_window).mean()
        df['volume_ma'] = df['volume'].rolling(window=self.volume_window).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        df['signal'] = 0
        
        # 价格上穿均线且放量
        buy_signal = (df['close'] > df['price_ma']) & (df['close'].shift(1) <= df['price_ma'].shift(1)) & (df['volume_ratio'] > self.volume_ratio)
        df.loc[buy_signal, 'signal'] = 1
        
        # 价格下穿均线且放量
        sell_signal = (df['close'] < df['price_ma']) & (df['close'].shift(1) >= df['price_ma'].shift(1)) & (df['volume_ratio'] > self.volume_ratio)
        df.loc[sell_signal, 'signal'] = -1
        
        df['position'] = df['signal'].diff()
        return df


class OBVStrategy(BaseStrategy):
    """OBV能量潮策略
    
    买入：OBV上穿OBV均线
    卖出：OBV下穿OBV均线
    """

    def __init__(self, window: int = 20):
        super().__init__(f"OBV_{window}")
        self.window = window

    def calculate_obv(self, df: pd.DataFrame) -> pd.Series:
        obv = pd.Series(0, index=df.index, dtype=float)
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + df['volume'].iloc[i]
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - df['volume'].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        return obv

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df['obv'] = self.calculate_obv(df)
        df['obv_ma'] = df['obv'].rolling(window=self.window).mean()
        
        df['signal'] = 0
        df.loc[df['obv'] > df['obv_ma'], 'signal'] = 1
        df.loc[df['obv'] <= df['obv_ma'], 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        return df


# ==================== 波动率策略 ====================

class ATRStrategy(BaseStrategy):
    """ATR波动率策略
    
    买入：价格突破N日高点 + ATR倍数
    卖出：价格跌破N日低点 - ATR倍数
    """

    def __init__(self, period: int = 14, multiplier: float = 2.0):
        super().__init__(f"ATR_{period}_{multiplier}")
        self.period = period
        self.multiplier = multiplier

    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.period).mean()
        
        return atr

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df['atr'] = self.calculate_atr(df)
        df['upper'] = df['high'].rolling(window=self.period).max() + df['atr'] * self.multiplier
        df['lower'] = df['low'].rolling(window=self.period).min() - df['atr'] * self.multiplier
        
        df['signal'] = 0
        df.loc[df['close'] > df['upper'].shift(1), 'signal'] = 1
        df.loc[df['close'] < df['lower'].shift(1), 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        return df


# ==================== 复合策略 ========================

class MultiIndicatorStrategy(BaseStrategy):
    """多指标复合策略
    
    综合多个指标进行决策
    """

    def __init__(self):
        super().__init__("MultiIndicator")

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        # 计算多个指标
        # MA
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal_line'] = df['macd'].ewm(span=9, adjust=False).mean()
        
        # 综合评分
        df['score'] = 0
        df.loc[df['ma20'] > df['ma60'], 'score'] += 1
        df.loc[df['ma20'] <= df['ma60'], 'score'] -= 1
        df.loc[df['rsi'] < 30, 'score'] += 1
        df.loc[df['rsi'] > 70, 'score'] -= 1
        df.loc[df['macd'] > df['signal_line'], 'score'] += 1
        df.loc[df['macd'] <= df['signal_line'], 'score'] -= 1
        
        # 生成信号
        df['signal'] = 0
        df.loc[df['score'] >= 2, 'signal'] = 1
        df.loc[df['score'] <= -2, 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        return df


# 策略注册表
STRATEGY_REGISTRY = {
    # 趋势跟踪
    'ma': MAStrategy,
    'ema': EMAStrategy,
    'triple_ma': TripleMAStrategy,
    'macd': MACDStrategy,
    'adx': ADXStrategy,
    
    # 动量策略
    'rsi': RSIStrategy,
    'kdj': KDJStrategy,
    'momentum': MomentumStrategy,
    'williams_r': WilliamsRStrategy,
    
    # 均值回归
    'bollinger': BollingerStrategy,
    'cci': CCIStrategy,
    
    # 成交量策略
    'volume_ma': VolumeMAStrategy,
    'obv': OBVStrategy,
    
    # 波动率策略
    'atr': ATRStrategy,
    
    # 复合策略
    'multi_indicator': MultiIndicatorStrategy,
}


def get_strategy(name: str, **kwargs) -> BaseStrategy:
    """
    获取策略实例
    
    Args:
        name: 策略名称
        **kwargs: 策略参数
        
    Returns:
        策略实例
    """
    strategy_class = STRATEGY_REGISTRY.get(name)
    if strategy_class is None:
        raise ValueError(f"未知策略: {name}")
    return strategy_class(**kwargs)


def list_strategies() -> List[Dict]:
    """
    列出所有可用策略
    
    Returns:
        策略信息列表
    """
    strategies = []
    for name, cls in STRATEGY_REGISTRY.items():
        strategies.append({
            'name': name,
            'class': cls.__name__,
            'doc': cls.__doc__.strip().split('\n')[0] if cls.__doc__ else ''
        })
    return strategies
