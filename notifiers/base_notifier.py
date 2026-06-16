"""
通知推送基类
定义通知推送的通用接口
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from signal_aggregator.models import AggregationResult


class BaseNotifier(ABC):
    """通知推送基类
    
    所有通知推送都应继承此类，实现抽象方法。
    """

    def __init__(self, name: str = "BaseNotifier"):
        """
        初始化通知推送
        
        Args:
            name: 通知器名称
        """
        self.name = name
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送消息
        
        Args:
            message: 消息内容
            title: 消息标题
            
        Returns:
            是否发送成功
        """
        pass

    def send_report(self, result: AggregationResult) -> bool:
        """
        发送分析报告
        
        Args:
            result: 聚合结果
            
        Returns:
            是否发送成功
        """
        report = result.to_report()
        title = f"AI信号分析报告 - {result.date}"
        return self.send(report, title)

    def send_alert(self, stock_code: str, stock_name: str, signal_type: str, score: float) -> bool:
        """
        发送信号提醒
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            signal_type: 信号类型
            score: 评分
            
        Returns:
            是否发送成功
        """
        message = f"""
信号提醒

股票代码: {stock_code}
股票名称: {stock_name}
信号类型: {signal_type}
评分: {score:.1f}

请注意投资风险！
"""
        title = f"信号提醒 - {stock_name}"
        return self.send(message, title)
