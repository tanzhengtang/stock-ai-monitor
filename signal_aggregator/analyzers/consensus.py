"""
共识分析器
用于分析多个平台信号的共识
"""

from typing import List, Dict
from collections import Counter

from ..models import PlatformSignal, SignalType


class ConsensusAnalyzer:
    """共识分析器
    
    通过多种方法分析多个平台信号的共识：
    1. 投票机制：统计各信号类型的票数
    2. 加权评分：计算加权平均评分
    3. 置信度加权：按置信度加权计算
    4. 综合判断：结合多种方法得出最终结论
    """

    def analyze(self, signals: List[PlatformSignal]) -> SignalType:
        """
        分析信号共识
        
        Args:
            signals: 平台信号列表
            
        Returns:
            共识信号类型
        """
        if not signals:
            return SignalType.NEUTRAL

        if len(signals) == 1:
            return signals[0].signal_type

        # 方法1：投票机制
        vote_result = self._vote(signals)

        # 方法2：加权评分
        score_result = self._weighted_score(signals)

        # 方法3：置信度加权
        confidence_result = self._confidence_weighted(signals)

        # 综合判断
        return self._combine_methods(vote_result, score_result, confidence_result)

    def _vote(self, signals: List[PlatformSignal]) -> SignalType:
        """
        投票机制
        
        统计各信号类型的票数，超过半数的信号类型胜出
        """
        signal_types = [s.signal_type for s in signals]
        counter = Counter(signal_types)

        # 获取票数最多的信号类型
        most_common = counter.most_common(1)[0]
        signal_type, count = most_common

        # 超过半数才有效
        if count > len(signals) / 2:
            return signal_type

        # 否则返回中性
        return SignalType.NEUTRAL

    def _weighted_score(self, signals: List[PlatformSignal]) -> SignalType:
        """
        加权评分
        
        计算所有信号评分的加权平均值
        """
        # 计算加权平均分（考虑置信度）
        total_weight = 0
        weighted_sum = 0

        for signal in signals:
            weight = signal.confidence
            weighted_sum += signal.score * weight
            total_weight += weight

        if total_weight == 0:
            return SignalType.NEUTRAL

        avg_score = weighted_sum / total_weight
        return SignalType.from_score(avg_score)

    def _confidence_weighted(self, signals: List[PlatformSignal]) -> SignalType:
        """
        置信度加权
        
        按置信度加权计算各信号类型的得分
        """
        # 按信号类型分组，计算置信度加权得分
        type_scores: Dict[SignalType, float] = {}
        type_confidences: Dict[SignalType, float] = {}

        for signal in signals:
            if signal.signal_type not in type_scores:
                type_scores[signal.signal_type] = 0
                type_confidences[signal.signal_type] = 0

            type_scores[signal.signal_type] += signal.score * signal.confidence
            type_confidences[signal.signal_type] += signal.confidence

        # 计算每种类型的加权平均分
        type_avg_scores: Dict[SignalType, float] = {}
        for signal_type in type_scores:
            if type_confidences[signal_type] > 0:
                type_avg_scores[signal_type] = (
                    type_scores[signal_type] / type_confidences[signal_type]
                )

        # 返回置信度最高的信号类型
        if not type_avg_scores:
            return SignalType.NEUTRAL

        # 按置信度加权计算总分
        total_confidence = sum(type_confidences.values())
        if total_confidence == 0:
            return SignalType.NEUTRAL

        weighted_score = sum(
            type_avg_scores[st] * type_confidences[st]
            for st in type_avg_scores
        ) / total_confidence

        return SignalType.from_score(weighted_score)

    def _combine_methods(
        self,
        vote: SignalType,
        score: SignalType,
        confidence: SignalType
    ) -> SignalType:
        """
        综合多种方法
        
        结合投票、加权评分、置信度加权三种方法的结果
        """
        # 将信号类型转换为数值
        results = [vote, score, confidence]
        avg_value = sum(r.value_numeric for r in results) / len(results)

        # 转换回信号类型
        if avg_value >= 1.5:
            return SignalType.STRONG_BUY
        elif avg_value >= 0.5:
            return SignalType.BUY
        elif avg_value >= -0.5:
            return SignalType.NEUTRAL
        elif avg_value >= -1.5:
            return SignalType.SELL
        else:
            return SignalType.STRONG_SELL

    def get_consensus_strength(self, signals: List[PlatformSignal]) -> float:
        """
        获取共识强度
        
        Args:
            signals: 平台信号列表
            
        Returns:
            共识强度 (0-1)，越高表示共识越强
        """
        if len(signals) < 2:
            return 1.0

        # 计算信号类型的一致性
        signal_types = [s.signal_type for s in signals]
        counter = Counter(signal_types)
        most_common_count = counter.most_common(1)[0][1]

        return most_common_count / len(signals)

    def get_detailed_analysis(self, signals: List[PlatformSignal]) -> Dict:
        """
        获取详细分析结果
        
        Args:
            signals: 平台信号列表
            
        Returns:
            详细分析结果字典
        """
        if not signals:
            return {
                'consensus': SignalType.NEUTRAL.value,
                'strength': 0,
                'methods': {},
                'distribution': {}
            }

        # 各方法结果
        vote_result = self._vote(signals)
        score_result = self._weighted_score(signals)
        confidence_result = self._confidence_weighted(signals)
        final_result = self._combine_methods(
            vote_result, score_result, confidence_result
        )

        # 信号分布
        signal_types = [s.signal_type for s in signals]
        counter = Counter(signal_types)
        distribution = {st.value: count for st, count in counter.items()}

        # 平均评分和置信度
        avg_score = sum(s.score for s in signals) / len(signals)
        avg_confidence = sum(s.confidence for s in signals) / len(signals)

        return {
            'consensus': final_result.value,
            'strength': self.get_consensus_strength(signals),
            'avg_score': avg_score,
            'avg_confidence': avg_confidence,
            'methods': {
                'vote': vote_result.value,
                'weighted_score': score_result.value,
                'confidence_weighted': confidence_result.value
            },
            'distribution': distribution,
            'signal_count': len(signals)
        }
