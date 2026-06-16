"""
信号聚合器核心模块
用于聚合多个平台的AI股票信号
"""

from typing import Dict, List, Optional
from datetime import datetime
from collections import Counter

from .models import (
    Platform, PlatformSignal, AggregatedSignal,
    SignalType, AggregationResult
)
from .analyzers.consensus import ConsensusAnalyzer
from .analyzers.risk import RiskAnalyzer


class SignalAggregator:
    """信号聚合器
    
    聚合多个平台的AI股票信号，生成共识信号和风险评估。
    
    Attributes:
        platform_weights: 各平台权重配置
        consensus_analyzer: 共识分析器
        risk_analyzer: 风险分析器
        signals_cache: 信号缓存
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化聚合器
        
        Args:
            config: 配置字典，可包含以下字段：
                - platform_weights: 各平台权重
                - min_signals: 最少信号数量
                - min_confidence: 最小置信度
        """
        self.config = config or {}

        # 平台权重配置
        self.platform_weights = self.config.get('platform_weights', {
            Platform.EASTMONEY: 0.3,
            Platform.TONGHUASHUN: 0.3,
            Platform.AKSHARE: 0.2,
            Platform.BAOSTOCK: 0.2,
            Platform.OTHER: 0.1
        })

        # 最少信号数量
        self.min_signals = self.config.get('min_signals', 1)

        # 初始化分析器
        self.consensus_analyzer = ConsensusAnalyzer()
        self.risk_analyzer = RiskAnalyzer()

        # 信号缓存: {stock_code: [PlatformSignal, ...]}
        self.signals_cache: Dict[str, List[PlatformSignal]] = {}

    def add_signal(self, signal: PlatformSignal):
        """
        添加单个平台信号
        
        Args:
            signal: 平台信号
        """
        stock_code = signal.stock_code

        if stock_code not in self.signals_cache:
            self.signals_cache[stock_code] = []

        # 更新或添加信号
        existing_indices = [
            i for i, s in enumerate(self.signals_cache[stock_code])
            if s.platform == signal.platform
        ]

        if existing_indices:
            # 更新已存在的信号
            self.signals_cache[stock_code][existing_indices[0]] = signal
        else:
            # 添加新信号
            self.signals_cache[stock_code].append(signal)

    def add_signals(self, signals: List[PlatformSignal]):
        """
        批量添加信号
        
        Args:
            signals: 信号列表
        """
        for signal in signals:
            self.add_signal(signal)

    def clear_signals(self, stock_code: Optional[str] = None):
        """
        清除信号
        
        Args:
            stock_code: 股票代码，如果为None则清除所有
        """
        if stock_code:
            self.signals_cache.pop(stock_code, None)
        else:
            self.signals_cache.clear()

    def get_stock_signals(self, stock_code: str) -> List[PlatformSignal]:
        """
        获取指定股票的信号
        
        Args:
            stock_code: 股票代码
            
        Returns:
            信号列表
        """
        return self.signals_cache.get(stock_code, [])

    def get_all_stock_codes(self) -> List[str]:
        """
        获取所有股票代码
        
        Returns:
            股票代码列表
        """
        return list(self.signals_cache.keys())

    def aggregate_stock(self, stock_code: str) -> Optional[AggregatedSignal]:
        """
        聚合单个股票的信号
        
        Args:
            stock_code: 股票代码
            
        Returns:
            聚合信号，如果信号不足则返回None
        """
        signals = self.signals_cache.get(stock_code)

        if not signals or len(signals) < self.min_signals:
            return None

        # 计算加权评分
        weighted_score = self._calculate_weighted_score(signals)

        # 分析共识
        consensus = self.consensus_analyzer.analyze(signals)

        # 计算置信度
        confidence = self._calculate_confidence(signals)

        # 分析风险
        risk_level = self.risk_analyzer.assess(signals)

        # 生成共识理由
        consensus_reasons = self._generate_consensus_reasons(signals)

        return AggregatedSignal(
            stock_code=stock_code,
            stock_name=signals[0].stock_name,
            weighted_score=weighted_score,
            consensus=consensus,
            confidence=confidence,
            platform_signals=signals,
            consensus_reasons=consensus_reasons,
            risk_level=risk_level,
            timestamp=datetime.now()
        )

    def aggregate_all(self) -> AggregationResult:
        """
        聚合所有股票信号
        
        Returns:
            聚合结果
        """
        all_aggregated = []

        for stock_code in self.signals_cache:
            aggregated = self.aggregate_stock(stock_code)
            if aggregated:
                all_aggregated.append(aggregated)

        # 分类统计
        bullish = [
            s for s in all_aggregated
            if s.consensus in [SignalType.STRONG_BUY, SignalType.BUY]
        ]
        bearish = [
            s for s in all_aggregated
            if s.consensus in [SignalType.STRONG_SELL, SignalType.SELL]
        ]
        neutral = [
            s for s in all_aggregated
            if s.consensus == SignalType.NEUTRAL
        ]

        # 按评分排序，获取推荐（排除高风险）
        top_picks = sorted(
            [s for s in bullish if s.risk_level != 'high'],
            key=lambda x: (x.weighted_score * x.confidence),
            reverse=True
        )[:10]

        # 风险提示
        risk_alerts = [
            s for s in all_aggregated
            if s.risk_level == 'high'
        ]

        # 市场情绪
        market_sentiment = self._calculate_market_sentiment(all_aggregated)

        return AggregationResult(
            date=datetime.now().strftime('%Y-%m-%d'),
            total_stocks=len(all_aggregated),
            bullish_count=len(bullish),
            bearish_count=len(bearish),
            neutral_count=len(neutral),
            top_picks=top_picks,
            risk_alerts=risk_alerts,
            market_sentiment=market_sentiment,
            timestamp=datetime.now()
        )

    def _calculate_weighted_score(self, signals: List[PlatformSignal]) -> float:
        """
        计算加权评分
        
        考虑平台权重和信号置信度
        """
        total_weight = 0
        weighted_sum = 0

        for signal in signals:
            # 平台权重
            platform_weight = self.platform_weights.get(signal.platform, 0.1)
            # 综合权重 = 平台权重 * 置信度
            weight = platform_weight * signal.confidence

            weighted_sum += signal.score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0

    def _calculate_confidence(self, signals: List[PlatformSignal]) -> float:
        """
        计算综合置信度
        
        考虑平均置信度和信号一致性
        """
        if not signals:
            return 0

        # 平均置信度
        avg_confidence = sum(s.confidence for s in signals) / len(signals)

        # 信号一致性
        signal_types = [s.signal_type for s in signals]
        most_common = max(set(signal_types), key=signal_types.count)
        consistency = signal_types.count(most_common) / len(signal_types)

        # 综合置信度 = 平均置信度 * 一致性
        return avg_confidence * consistency

    def _generate_consensus_reasons(self, signals: List[PlatformSignal]) -> List[str]:
        """
        生成共识理由
        
        收集各平台的理由，统计高频理由
        """
        # 收集所有理由
        all_reasons = []
        for signal in signals:
            all_reasons.extend(signal.reasons)

        if not all_reasons:
            return ['多平台共识']

        # 统计高频理由
        reason_counts = Counter(all_reasons)

        # 取前5个高频理由（至少出现2次）
        reasons = []
        for reason, count in reason_counts.most_common(5):
            if count >= 2:
                reasons.append(f"{reason} ({count}个平台提及)")
            elif len(reasons) < 3:
                reasons.append(reason)

        return reasons if reasons else ['多平台共识']

    def _calculate_market_sentiment(self, signals: List[AggregatedSignal]) -> float:
        """
        计算市场情绪
        
        Returns:
            市场情绪 (0-1)，越高越乐观
        """
        if not signals:
            return 0.5

        bullish_count = sum(
            1 for s in signals
            if s.consensus in [SignalType.STRONG_BUY, SignalType.BUY]
        )

        return bullish_count / len(signals)

    def get_statistics(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        total_stocks = len(self.signals_cache)
        total_signals = sum(len(s) for s in self.signals_cache.values())

        # 平台分布
        platform_counts = Counter()
        for signals in self.signals_cache.values():
            for signal in signals:
                platform_counts[signal.platform.value] += 1

        return {
            'total_stocks': total_stocks,
            'total_signals': total_signals,
            'avg_signals_per_stock': total_signals / total_stocks if total_stocks > 0 else 0,
            'platform_distribution': dict(platform_counts)
        }

    def export_signals(self, format: str = 'dict') -> List[Dict]:
        """
        导出所有信号
        
        Args:
            format: 输出格式，目前支持 'dict'
            
        Returns:
            信号列表
        """
        result = []
        for stock_code, signals in self.signals_cache.items():
            aggregated = self.aggregate_stock(stock_code)
            if aggregated:
                result.append(aggregated.to_dict())
        return result
