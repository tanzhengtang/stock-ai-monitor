"""
风险分析器
用于评估信号的风险等级
"""

from typing import List, Dict
from ..models import PlatformSignal, SignalType


class RiskAnalyzer:
    """风险分析器
    
    评估信号的风险等级，考虑以下因素：
    1. 信号分歧度：多个平台信号的一致性
    2. 置信度：信号的平均置信度
    3. 评分极端性：评分是否过于极端
    4. 信号数量：信号来源的数量
    5. 波动性：评分的波动程度
    """

    # 风险等级常量
    RISK_LOW = 'low'
    RISK_MEDIUM = 'medium'
    RISK_HIGH = 'high'

    def assess(self, signals: List[PlatformSignal]) -> str:
        """
        评估风险等级
        
        Args:
            signals: 平台信号列表
            
        Returns:
            风险等级: 'low', 'medium', 'high'
        """
        if not signals:
            return self.RISK_HIGH

        # 计算各因素的风险分数
        risk_score = 0

        # 因素1：信号分歧度 (0-40分)
        divergence = self._calculate_divergence(signals)
        risk_score += divergence * 40

        # 因素2：置信度 (0-20分)
        avg_confidence = sum(s.confidence for s in signals) / len(signals)
        risk_score += (1 - avg_confidence) * 20

        # 因素3：评分极端性 (0-20分)
        extremity = self._calculate_extremity(signals)
        risk_score += extremity * 20

        # 因素4：信号数量 (0-10分)
        if len(signals) < 2:
            risk_score += 10
        elif len(signals) < 3:
            risk_score += 5

        # 因素5：波动性 (0-10分)
        volatility = self._calculate_volatility(signals)
        risk_score += volatility * 10

        # 判断风险等级
        if risk_score >= 50:
            return self.RISK_HIGH
        elif risk_score >= 25:
            return self.RISK_MEDIUM
        else:
            return self.RISK_LOW

    def _calculate_divergence(self, signals: List[PlatformSignal]) -> float:
        """
        计算信号分歧度
        
        Returns:
            分歧度 (0-1)，越高表示分歧越大
        """
        if len(signals) < 2:
            return 0

        # 计算评分的极差
        scores = [s.score for s in signals]
        max_diff = max(scores) - min(scores)

        # 归一化到0-1
        return min(max_diff / 100, 1.0)

    def _calculate_extremity(self, signals: List[PlatformSignal]) -> float:
        """
        计算评分极端性
        
        Returns:
            极端性 (0-1)，越高表示越极端
        """
        if not signals:
            return 0

        avg_score = sum(s.score for s in signals) / len(signals)

        # 计算与中间值(50)的距离
        distance = abs(avg_score - 50) / 50

        return distance

    def _calculate_volatility(self, signals: List[PlatformSignal]) -> float:
        """
        计算评分波动性
        
        Returns:
            波动性 (0-1)，越高表示波动越大
        """
        if len(signals) < 2:
            return 0

        scores = [s.score for s in signals]
        mean = sum(scores) / len(scores)

        # 计算标准差
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std_dev = variance ** 0.5

        # 归一化到0-1 (标准差最大为50)
        return min(std_dev / 50, 1.0)

    def get_detailed_assessment(self, signals: List[PlatformSignal]) -> Dict:
        """
        获取详细的风险评估结果
        
        Args:
            signals: 平台信号列表
            
        Returns:
            详细评估结果字典
        """
        if not signals:
            return {
                'risk_level': self.RISK_HIGH,
                'risk_score': 100,
                'factors': {},
                'warnings': ['无信号数据']
            }

        # 计算各因素
        divergence = self._calculate_divergence(signals)
        avg_confidence = sum(s.confidence for s in signals) / len(signals)
        extremity = self._calculate_extremity(signals)
        volatility = self._calculate_volatility(signals)

        # 计算总风险分数
        risk_score = (
            divergence * 30 +
            (1 - avg_confidence) * 20 +
            extremity * 20 +
            (15 if len(signals) < 2 else 10 if len(signals) < 3 else 0) +
            volatility * 15
        )

        # 生成警告信息
        warnings = []
        if divergence > 0.5:
            warnings.append(f'信号分歧较大: {divergence:.1%}')
        if avg_confidence < 0.5:
            warnings.append(f'平均置信度较低: {avg_confidence:.1%}')
        if extremity > 0.8:
            warnings.append('评分过于极端')
        if len(signals) < 3:
            warnings.append(f'信号来源较少: {len(signals)}个')
        if volatility > 0.5:
            warnings.append(f'评分波动较大: {volatility:.1%}')

        return {
            'risk_level': self.assess(signals),
            'risk_score': risk_score,
            'factors': {
                'divergence': divergence,
                'avg_confidence': avg_confidence,
                'extremity': extremity,
                'volatility': volatility,
                'signal_count': len(signals)
            },
            'warnings': warnings
        }

    def filter_high_risk(
        self,
        signals_list: List[List[PlatformSignal]]
    ) -> List[List[PlatformSignal]]:
        """
        过滤高风险信号
        
        Args:
            signals_list: 信号列表的列表
            
        Returns:
            过滤后的信号列表
        """
        return [
            signals for signals in signals_list
            if self.assess(signals) != self.RISK_HIGH
        ]
