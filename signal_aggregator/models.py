"""
数据模型定义
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class SignalType(Enum):
    """信号类型"""
    STRONG_BUY = "strong_buy"      # 强烈买入
    BUY = "buy"                    # 买入
    NEUTRAL = "neutral"            # 中性
    SELL = "sell"                   # 卖出
    STRONG_SELL = "strong_sell"    # 强烈卖出

    @property
    def value_numeric(self) -> int:
        """获取数值表示"""
        mapping = {
            SignalType.STRONG_BUY: 2,
            SignalType.BUY: 1,
            SignalType.NEUTRAL: 0,
            SignalType.SELL: -1,
            SignalType.STRONG_SELL: -2
        }
        return mapping[self]

    @classmethod
    def from_score(cls, score: float) -> 'SignalType':
        """从评分创建信号类型"""
        if score >= 80:
            return cls.STRONG_BUY
        elif score >= 60:
            return cls.BUY
        elif score >= 40:
            return cls.NEUTRAL
        elif score >= 20:
            return cls.SELL
        else:
            return cls.STRONG_SELL


class Platform(Enum):
    """平台来源"""
    EASTMONEY = "eastmoney"        # 东方财富
    TONGHUASHUN = "tonghuashun"    # 同花顺
    XUEQIU = "xueqiu"              # 雪球
    TENCENT = "tencent"            # 腾讯
    AKSHARE = "akshare"            # AKShare
    BAOSTOCK = "baostock"          # BaoStock
    OTHER = "other"                # 其他


class AnalysisType(Enum):
    """分析类型"""
    TECHNICAL = "technical"        # 技术面分析
    FUNDAMENTAL = "fundamental"    # 基本面分析
    COMBINED = "combined"          # 综合分析


@dataclass
class PlatformSignal:
    """单个平台信号
    
    Attributes:
        platform: 平台来源
        stock_code: 股票代码
        stock_name: 股票名称
        score: 评分 (0-100)
        signal_type: 信号类型
        analysis_type: 分析类型（技术面/基本面/综合）
        confidence: 置信度 (0-1)
        reasons: 推荐理由
        timestamp: 更新时间
        raw_data: 原始数据
        fundamental_data: 基本面数据
    """
    platform: Platform
    stock_code: str
    stock_name: str
    score: float
    signal_type: SignalType
    analysis_type: AnalysisType = AnalysisType.COMBINED
    confidence: float = 0.5
    reasons: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    raw_data: Optional[Dict[str, Any]] = None
    fundamental_data: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """验证数据"""
        if not 0 <= self.score <= 100:
            raise ValueError(f"score must be between 0 and 100, got {self.score}")
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"confidence must be between 0 and 1, got {self.confidence}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'platform': self.platform.value,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'score': self.score,
            'signal_type': self.signal_type.value,
            'analysis_type': self.analysis_type.value,
            'confidence': self.confidence,
            'reasons': self.reasons,
            'timestamp': self.timestamp.isoformat(),
            'raw_data': self.raw_data,
            'fundamental_data': self.fundamental_data
        }


@dataclass
class AggregatedSignal:
    """聚合信号
    
    Attributes:
        stock_code: 股票代码
        stock_name: 股票名称
        weighted_score: 加权评分
        consensus: 共识信号
        confidence: 综合置信度
        platform_signals: 各平台信号
        consensus_reasons: 共识理由
        risk_level: 风险等级
        timestamp: 生成时间
    """
    stock_code: str
    stock_name: str
    weighted_score: float
    consensus: SignalType
    confidence: float
    platform_signals: List[PlatformSignal]
    consensus_reasons: List[str] = field(default_factory=list)
    risk_level: str = 'medium'
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def signal_count(self) -> int:
        """信号数量"""
        return len(self.platform_signals)

    @property
    def platform_names(self) -> List[str]:
        """平台名称列表"""
        return [s.platform.value for s in self.platform_signals]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'weighted_score': self.weighted_score,
            'consensus': self.consensus.value,
            'confidence': self.confidence,
            'signal_count': self.signal_count,
            'platform_signals': [s.to_dict() for s in self.platform_signals],
            'consensus_reasons': self.consensus_reasons,
            'risk_level': self.risk_level,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class AggregationResult:
    """聚合结果
    
    Attributes:
        date: 日期
        total_stocks: 总股票数
        bullish_count: 看多数量
        bearish_count: 看空数量
        neutral_count: 中性数量
        top_picks: 今日推荐
        risk_alerts: 风险提示
        market_sentiment: 市场情绪 (0-1)
        timestamp: 生成时间
    """
    date: str
    total_stocks: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    top_picks: List[AggregatedSignal]
    risk_alerts: List[AggregatedSignal]
    market_sentiment: float
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def summary(self) -> str:
        """获取摘要"""
        return (
            f"日期: {self.date}\n"
            f"总股票数: {self.total_stocks}\n"
            f"看多: {self.bullish_count} | 看空: {self.bearish_count} | 中性: {self.neutral_count}\n"
            f"市场情绪: {self.market_sentiment:.1%}\n"
            f"推荐股票: {len(self.top_picks)} | 风险提示: {len(self.risk_alerts)}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'date': self.date,
            'total_stocks': self.total_stocks,
            'bullish_count': self.bullish_count,
            'bearish_count': self.bearish_count,
            'neutral_count': self.neutral_count,
            'top_picks': [s.to_dict() for s in self.top_picks],
            'risk_alerts': [s.to_dict() for s in self.risk_alerts],
            'market_sentiment': self.market_sentiment,
            'timestamp': self.timestamp.isoformat()
        }

    def to_report(self) -> str:
        """生成报告"""
        lines = [
            "=" * 60,
            "AI信号聚合报告",
            "=" * 60,
            f"日期: {self.date}",
            f"生成时间: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "-" * 60,
            "",
            "【市场概览】",
            f"  总股票数: {self.total_stocks}",
            f"  看多信号: {self.bullish_count}",
            f"  看空信号: {self.bearish_count}",
            f"  中性信号: {self.neutral_count}",
            f"  市场情绪: {self.market_sentiment:.1%}",
            "",
        ]

        if self.top_picks:
            lines.append("【今日推荐】")
            for i, stock in enumerate(self.top_picks[:10], 1):
                lines.append(
                    f"  {i}. {stock.stock_code} {stock.stock_name} "
                    f"[{stock.weighted_score:.1f}分] {stock.consensus.value}"
                )
                if stock.consensus_reasons:
                    lines.append(f"     理由: {', '.join(stock.consensus_reasons[:3])}")
            lines.append("")

        if self.risk_alerts:
            lines.append("【风险提示】")
            for stock in self.risk_alerts[:5]:
                lines.append(
                    f"  ⚠ {stock.stock_code} {stock.stock_name} "
                    f"[{stock.risk_level}]"
                )
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)
