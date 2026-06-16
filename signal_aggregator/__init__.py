"""
信号聚合模块
用于聚合多个平台的AI股票信号
"""

from .models import (
    SignalType,
    Platform,
    AnalysisType,
    PlatformSignal,
    AggregatedSignal,
    AggregationResult
)
from .aggregator import SignalAggregator

__all__ = [
    'SignalType',
    'Platform',
    'AnalysisType',
    'PlatformSignal',
    'AggregatedSignal',
    'AggregationResult',
    'SignalAggregator'
]
