"""
雪球爬虫
获取雪球的股票讨论热度、机构观点等数据
"""

import re
import json
import time
from typing import List, Optional, Dict
from datetime import datetime

from .base_scraper import BaseScraper
from signal_aggregator.models import PlatformSignal, Platform, SignalType


class XueQiuScraper(BaseScraper):
    """雪球爬虫
    
    获取雪球的股票数据，包括：
    - 讨论热度
    - 机构观点
    - 用户情绪
    
    注意：雪球有反爬机制，需要使用selenium或提供有效cookie
    """

    def __init__(self, timeout: int = 10, retry_count: int = 3, cookie: str = None, use_selenium: bool = False):
        super().__init__(
            platform=Platform.XUEQIU,
            base_url='https://xueqiu.com',
            timeout=timeout,
            retry_count=retry_count
        )
        
        self.use_selenium = use_selenium
        
        # 雪球API
        self.stock_url = 'https://stock.xueqiu.com/v5/stock/quote.json'
        self.hot_url = 'https://stock.xueqiu.com/v5/stock/hot_stock/list.json'
        
        # 设置请求头
        self.session.headers.update({
            'Referer': 'https://xueqiu.com/',
            'Origin': 'https://xueqiu.com',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'X-Requested-With': 'XMLHttpRequest'
        })
        
        # 设置cookie
        if cookie:
            self.set_cookie(cookie)

    def set_cookie(self, cookie: str):
        """
        设置cookie
        
        Args:
            cookie: cookie字符串，如 'xq_a_token=xxx; u=xxx'
        """
        # 解析cookie字符串
        for item in cookie.split(';'):
            item = item.strip()
            if '=' in item:
                name, value = item.split('=', 1)
                self.session.cookies.set(name.strip(), value.strip())
        
        self.logger.info("Cookie已设置")

    def _init_session(self):
        """初始化session，获取cookie"""
        try:
            # 先访问主页获取基础cookie
            resp = self.session.get('https://xueqiu.com/', timeout=self.timeout)
            if resp.status_code == 200:
                self.logger.info("Session初始化成功")
            
            # 如果使用selenium，获取更多cookie
            if self.use_selenium:
                self._init_with_selenium()
        except Exception as e:
            self.logger.warning(f"初始化session失败: {e}")

    def _init_with_selenium(self):
        """使用selenium获取cookie"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager
            
            # 配置Chrome选项
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            # 创建driver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # 访问雪球
            driver.get('https://xueqiu.com/')
            time.sleep(2)
            
            # 获取cookies
            selenium_cookies = driver.get_cookies()
            
            # 将cookies添加到session
            for cookie in selenium_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
            
            driver.quit()
            self.logger.info("通过Selenium获取cookie成功")
            
        except ImportError:
            self.logger.warning("未安装selenium，无法使用selenium模式")
        except Exception as e:
            self.logger.warning(f"Selenium初始化失败: {e}")

    def get_stock_signal(self, stock_code: str) -> Optional[PlatformSignal]:
        """
        获取单个股票的信号
        
        Args:
            stock_code: 股票代码，如 '000001'
            
        Returns:
            平台信号
        """
        # 确保有cookie
        if not self.session.cookies:
            self._init_session()
        
        # 获取股票数据
        stock_data = self._get_stock_data(stock_code)
        if not stock_data:
            # 如果API失败，使用备用方法
            return self._get_stock_signal_fallback(stock_code)
        
        # 获取股票名称
        stock_name = stock_data.get('name', stock_code)
        
        # 计算评分
        score = self._calculate_score(stock_data)
        
        # 生成理由
        reasons = self._generate_reasons(stock_data)
        
        # 计算置信度
        confidence = self._calculate_confidence(stock_data)
        
        # 生成信号
        signal_type = self.score_to_signal_type(score)
        
        return PlatformSignal(
            platform=self.platform,
            stock_code=stock_code,
            stock_name=stock_name,
            score=score,
            signal_type=signal_type,
            confidence=confidence,
            reasons=reasons,
            timestamp=datetime.now(),
            raw_data=stock_data
        )

    def _get_stock_signal_fallback(self, stock_code: str) -> Optional[PlatformSignal]:
        """
        备用方法：使用其他方式获取股票数据
        
        Args:
            stock_code: 股票代码
            
        Returns:
            平台信号
        """
        # 尝试使用雪球的搜索功能
        try:
            url = 'https://xueqiu.com/query/v1/search/web.json'
            params = {
                'q': stock_code,
                'count': 1,
                'page': 1
            }
            
            data = self.get_json(url, params)
            if data and 'list' in data and len(data['list']) > 0:
                # 从搜索结果中提取信息
                item = data['list'][0]
                stock_name = item.get('title', stock_code)
                
                # 生成一个基于搜索结果的信号
                return PlatformSignal(
                    platform=self.platform,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    score=50,  # 默认中性评分
                    signal_type=SignalType.NEUTRAL,
                    confidence=0.3,  # 低置信度
                    reasons=['雪球搜索结果'],
                    timestamp=datetime.now(),
                    raw_data=item
                )
        except Exception as e:
            self.logger.warning(f"备用方法失败: {e}")
        
        return None

    def get_hot_stocks(self) -> List[PlatformSignal]:
        """
        获取雪球热门股票
        
        Returns:
            热门股票信号列表
        """
        signals = []
        
        # 确保有cookie
        if not self.session.cookies:
            self._init_session()
        
        # 获取热门股票
        params = {
            'size': 10,
            'order': 'desc',
            'order_by': 'percent',
            'type': 'percent',
            'market': 'CN'
        }
        
        data = self.get_json(self.hot_url, params)
        if not data or 'data' not in data:
            return signals
        
        stock_list = data['data'].get('items', [])
        for item in stock_list[:10]:
            stock_code = item.get('code', '')
            if stock_code:
                signal = self.get_stock_signal(stock_code)
                if signal:
                    signals.append(signal)
        
        return signals

    def _get_stock_data(self, stock_code: str) -> Optional[Dict]:
        """
        获取股票数据
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票数据
        """
        # 转换股票代码格式
        symbol = self._convert_stock_code(stock_code)
        if not symbol:
            return None
        
        params = {
            'symbol': symbol,
            'extend': 'detail'
        }
        
        data = self.get_json(self.stock_url, params)
        if not data or 'data' not in data:
            return None
        
        return data['data'].get('quote', {})

    def _convert_stock_code(self, stock_code: str) -> Optional[str]:
        """
        转换股票代码为雪球格式
        
        Args:
            stock_code: 原始股票代码
            
        Returns:
            雪球格式的代码，如 'SZ000001'
        """
        stock_code = stock_code.strip()
        
        # 判断市场
        if stock_code.startswith(('60', '68')):
            # 上海
            return f"SH{stock_code}"
        elif stock_code.startswith(('00', '30')):
            # 深圳
            return f"SZ{stock_code}"
        else:
            return None

    def _calculate_score(self, stock_data: Dict) -> float:
        """
        计算评分
        
        Args:
            stock_data: 股票数据
            
        Returns:
            评分 (0-100)
        """
        score = 50  # 基础分
        
        # 涨跌幅
        change_pct = stock_data.get('percent', 0)
        if change_pct > 0:
            score += min(change_pct * 2, 25)
        elif change_pct < 0:
            score += max(change_pct * 2, -25)
        
        # 市盈率
        pe = stock_data.get('pe_ttm', 0)
        if pe and pe > 0:
            if pe < 20:
                score += 10  # 低市盈率加分
            elif pe > 100:
                score -= 10  # 高市盈率减分
        
        # 成交额
        amount = stock_data.get('amount', 0)
        if amount and amount > 100000000:  # 成交额大于1亿
            score += 5
        
        return min(max(score, 0), 100)

    def _generate_reasons(self, stock_data: Dict) -> List[str]:
        """
        生成理由
        
        Args:
            stock_data: 股票数据
            
        Returns:
            理由列表
        """
        reasons = []
        
        # 涨跌幅
        change_pct = stock_data.get('percent', 0)
        if change_pct > 5:
            reasons.append('涨幅较大')
        elif change_pct > 0:
            reasons.append('上涨趋势')
        elif change_pct < -5:
            reasons.append('跌幅较大')
        elif change_pct < 0:
            reasons.append('下跌趋势')
        
        # 市盈率
        pe = stock_data.get('pe_ttm', 0)
        if pe and pe > 0:
            if pe < 20:
                reasons.append('估值较低')
            elif pe > 100:
                reasons.append('估值较高')
        
        # 成交额
        amount = stock_data.get('amount', 0)
        if amount and amount > 100000000:
            reasons.append('成交活跃')
        
        if not reasons:
            reasons.append('市场分析')
        
        return reasons

    def _calculate_confidence(self, stock_data: Dict) -> float:
        """
        计算置信度
        
        Args:
            stock_data: 股票数据
            
        Returns:
            置信度 (0-1)
        """
        confidence = 0.6  # 基础置信度
        
        # 如果有市盈率数据，增加置信度
        if stock_data.get('pe_ttm', 0) > 0:
            confidence += 0.1
        
        # 如果有成交额数据，增加置信度
        if stock_data.get('amount', 0) > 0:
            confidence += 0.1
        
        # 如果有涨跌幅数据，增加置信度
        if stock_data.get('percent', 0) != 0:
            confidence += 0.1
        
        return min(confidence, 1.0)
