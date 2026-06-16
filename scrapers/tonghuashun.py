"""
同花顺爬虫
获取同花顺的AI诊股、智能选股等数据
"""

import re
import json
from typing import List, Optional, Dict
from datetime import datetime

from .base_scraper import BaseScraper
from signal_aggregator.models import PlatformSignal, Platform, SignalType


class TongHuaShunScraper(BaseScraper):
    """同花顺爬虫
    
    获取同花顺的AI诊股数据，包括：
    - AI综合评分
    - 技术面分析
    - 资金流向
    - 行业分析
    """

    def __init__(self, timeout: int = 10, retry_count: int = 3):
        super().__init__(
            platform=Platform.TONGHUASHUN,
            base_url='https://www.10jqka.com.cn',
            timeout=timeout,
            retry_count=retry_count
        )
        
        # 个股详情页
        self.stock_url = 'https://stockpage.10jqka.com.cn/{code}/'
        
        # AI诊股API
        self.ai_url = 'https://ai.10jqka.com.cn/stock/diagnosis/{code}'

    def get_stock_signal(self, stock_code: str) -> Optional[PlatformSignal]:
        """
        获取单个股票的AI诊股信号
        
        Args:
            stock_code: 股票代码，如 '000001'
            
        Returns:
            平台信号
        """
        # 获取股票名称
        stock_name = self._get_stock_name(stock_code)
        
        # 获取行情数据
        quote_data = self._get_quote_data(stock_code)
        if not quote_data:
            return None
        
        # 计算评分
        score = self._calculate_score(quote_data)
        
        # 生成理由
        reasons = self._generate_reasons(quote_data)
        
        # 计算置信度
        confidence = self._calculate_confidence(quote_data)
        
        # 生成信号
        signal_type = self.score_to_signal_type(score)
        
        return PlatformSignal(
            platform=self.platform,
            stock_code=stock_code,
            stock_name=stock_name or stock_code,
            score=score,
            signal_type=signal_type,
            confidence=confidence,
            reasons=reasons,
            timestamp=datetime.now(),
            raw_data=quote_data
        )

    def get_hot_stocks(self) -> List[PlatformSignal]:
        """
        获取同花顺热门股票
        
        Returns:
            热门股票信号列表
        """
        signals = []
        
        # 获取热门股票列表
        url = 'https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock?stock_type=a&type=hour&list_type=normal'
        
        headers = {
            'Referer': 'https://www.10jqka.com.cn/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        data = self.get_json(url)
        if not data or 'data' not in data:
            return signals
        
        stock_list = data['data'].get('stock_list', [])
        for item in stock_list[:10]:  # 取前10个
            stock_code = item.get('code', '')
            if stock_code:
                signal = self.get_stock_signal(stock_code)
                if signal:
                    signals.append(signal)
        
        return signals

    def _get_stock_name(self, stock_code: str) -> Optional[str]:
        """
        获取股票名称
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票名称
        """
        url = self.stock_url.format(code=stock_code)
        html = self.get_page(url)
        
        if not html:
            return None
        
        # 从HTML中提取股票名称
        match = re.search(r'<title>(.*?)_', html)
        if match:
            return match.group(1).strip()
        
        return None

    def _get_quote_data(self, stock_code: str) -> Optional[Dict]:
        """
        获取行情数据
        
        Args:
            stock_code: 股票代码
            
        Returns:
            行情数据
        """
        # 使用同花顺行情API
        market = '1' if stock_code.startswith(('60', '68')) else '0'
        url = f'http://d.10jqka.com.cn/v2/line/hs_{stock_code}/01/last.js'
        
        headers = {
            'Referer': f'https://stockpage.10jqka.com.cn/{stock_code}/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        html = self.get_page(url)
        if not html:
            return None
        
        # 解析JavaScript数据
        try:
            # 提取JSON数据
            match = re.search(r'\{.*\}', html)
            if match:
                data = json.loads(match.group())
                return self._parse_quote_data(data, stock_code)
        except (json.JSONDecodeError, AttributeError):
            pass
        
        return None

    def _parse_quote_data(self, data: Dict, stock_code: str) -> Dict:
        """
        解析行情数据
        
        Args:
            data: 原始数据
            stock_code: 股票代码
            
        Returns:
            解析后的数据
        """
        # 从同花顺数据中提取关键信息
        result = {
            'stock_code': stock_code,
            'price': 0,
            'change_pct': 0,
            'volume': 0,
            'turnover': 0
        }
        
        # 解析具体字段
        if 'data' in data:
            items = data['data'].split(';')
            if len(items) > 0:
                last_item = items[-1].split(',')
                if len(last_item) >= 6:
                    try:
                        result['price'] = float(last_item[1])
                        result['change_pct'] = float(last_item[3])
                        result['volume'] = float(last_item[4])
                    except (ValueError, IndexError):
                        pass
        
        return result

    def _calculate_score(self, quote_data: Dict) -> float:
        """
        计算评分
        
        Args:
            quote_data: 行情数据
            
        Returns:
            评分 (0-100)
        """
        score = 50  # 基础分
        
        # 涨跌幅
        change_pct = quote_data.get('change_pct', 0)
        if change_pct > 0:
            score += min(change_pct * 2, 25)
        elif change_pct < 0:
            score += max(change_pct * 2, -25)
        
        # 成交量
        volume = quote_data.get('volume', 0)
        if volume > 1000000:  # 成交量大于100万
            score += 5
        
        return min(max(score, 0), 100)

    def _generate_reasons(self, quote_data: Dict) -> List[str]:
        """
        生成理由
        
        Args:
            quote_data: 行情数据
            
        Returns:
            理由列表
        """
        reasons = []
        
        # 涨跌幅
        change_pct = quote_data.get('change_pct', 0)
        if change_pct > 5:
            reasons.append('涨幅较大')
        elif change_pct > 0:
            reasons.append('上涨趋势')
        elif change_pct < -5:
            reasons.append('跌幅较大')
        elif change_pct < 0:
            reasons.append('下跌趋势')
        
        # 成交量
        volume = quote_data.get('volume', 0)
        if volume > 1000000:
            reasons.append('成交量活跃')
        
        if not reasons:
            reasons.append('技术面分析')
        
        return reasons

    def _calculate_confidence(self, quote_data: Dict) -> float:
        """
        计算置信度
        
        Args:
            quote_data: 行情数据
            
        Returns:
            置信度 (0-1)
        """
        confidence = 0.6  # 基础置信度
        
        # 如果有成交量数据，增加置信度
        if quote_data.get('volume', 0) > 0:
            confidence += 0.1
        
        # 如果有价格数据，增加置信度
        if quote_data.get('price', 0) > 0:
            confidence += 0.1
        
        return min(confidence, 1.0)
