"""
爬虫基类
定义爬虫的通用接口和方法
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from signal_aggregator.models import PlatformSignal, Platform, SignalType, AnalysisType


class BaseScraper(ABC):
    """爬虫基类
    
    所有平台爬虫都应继承此类，实现抽象方法。
    
    Attributes:
        platform: 平台来源
        base_url: 基础URL
        headers: 请求头
        timeout: 请求超时时间
        retry_count: 重试次数
        logger: 日志记录器
    """

    def __init__(
        self,
        platform: Platform,
        base_url: str,
        timeout: int = 10,
        retry_count: int = 3
    ):
        """
        初始化爬虫
        
        Args:
            platform: 平台来源
            base_url: 基础URL
            timeout: 请求超时时间
            retry_count: 重试次数
        """
        self.platform = platform
        self.base_url = base_url
        self.timeout = timeout
        self.retry_count = retry_count
        
        # 设置请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        
        # 创建session
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # 日志
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_page(self, url: str, params: Optional[Dict] = None) -> Optional[str]:
        """
        获取页面内容
        
        Args:
            url: 页面URL
            params: 请求参数
            
        Returns:
            页面HTML内容，失败返回None
        """
        for attempt in range(self.retry_count):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                response.encoding = response.apparent_encoding
                return response.text
            except requests.RequestException as e:
                self.logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(1)
        
        return None

    def get_json(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        获取JSON数据
        
        Args:
            url: API地址
            params: 请求参数
            
        Returns:
            JSON数据，失败返回None
        """
        for attempt in range(self.retry_count):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as e:
                self.logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(1)
        
        return None

    def post_json(self, url: str, data: Optional[Dict] = None, json_data: Optional[Dict] = None) -> Optional[Dict]:
        """
        POST请求获取JSON数据
        
        Args:
            url: API地址
            data: 表单数据
            json_data: JSON数据
            
        Returns:
            JSON数据，失败返回None
        """
        for attempt in range(self.retry_count):
            try:
                response = self.session.post(
                    url,
                    data=data,
                    json=json_data,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as e:
                self.logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(1)
        
        return None

    def parse_html(self, html: str) -> BeautifulSoup:
        """
        解析HTML
        
        Args:
            html: HTML内容
            
        Returns:
            BeautifulSoup对象
        """
        return BeautifulSoup(html, 'html.parser')

    def score_to_signal_type(self, score: float) -> SignalType:
        """
        将评分转换为信号类型
        
        Args:
            score: 评分 (0-100)
            
        Returns:
            信号类型
        """
        return SignalType.from_score(score)

    @abstractmethod
    def get_stock_signal(self, stock_code: str) -> Optional[PlatformSignal]:
        """
        获取单个股票的AI信号
        
        Args:
            stock_code: 股票代码
            
        Returns:
            平台信号，失败返回None
        """
        pass

    @abstractmethod
    def get_hot_stocks(self) -> List[PlatformSignal]:
        """
        获取热门股票信号
        
        Returns:
            热门股票信号列表
        """
        pass

    def get_multiple_signals(self, stock_codes: List[str]) -> List[PlatformSignal]:
        """
        批量获取股票信号
        
        Args:
            stock_codes: 股票代码列表
            
        Returns:
            信号列表
        """
        signals = []
        for code in stock_codes:
            signal = self.get_stock_signal(code)
            if signal:
                signals.append(signal)
            time.sleep(0.5)  # 避免请求过快
        return signals

    def close(self):
        """关闭session"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
