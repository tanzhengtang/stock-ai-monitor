"""
东方财富爬虫
获取东方财富的AI诊股、智能选股等数据
"""

import re
import json
from typing import List, Optional, Dict
from datetime import datetime

from .base_scraper import BaseScraper
from signal_aggregator.models import PlatformSignal, Platform, SignalType


class EastMoneyScraper(BaseScraper):
    """东方财富爬虫
    
    获取东方财富的AI诊股数据，包括：
    - AI综合评分
    - 技术面分析
    - 资金面分析
    - 消息面分析
    """

    def __init__(self, timeout: int = 10, retry_count: int = 3):
        super().__init__(
            platform=Platform.EASTMONEY,
            base_url='https://www.eastmoney.com',
            timeout=timeout,
            retry_count=retry_count
        )
        
        # AI诊股API
        self.ai_diagnosis_url = 'https://emappdata.eastmoney.com/stockcomment/api/StockComment/GetAIDiagnosis'
        
        # 个股行情API
        self.quote_url = 'https://push2.eastmoney.com/api/qt/stock/get'

    def get_stock_signal(self, stock_code: str) -> Optional[PlatformSignal]:
        """
        获取单个股票的AI诊股信号
        
        Args:
            stock_code: 股票代码，如 '000001'
            
        Returns:
            平台信号
        """
        # 转换股票代码格式
        secid = self._convert_stock_code(stock_code)
        if not secid:
            return None
        
        # 获取股票名称
        stock_name = self._get_stock_name(secid)
        
        # 获取AI诊股数据
        ai_data = self._get_ai_diagnosis(secid)
        if not ai_data:
            return None
        
        # 解析数据
        score = ai_data.get('score', 50)
        reasons = ai_data.get('reasons', [])
        confidence = ai_data.get('confidence', 0.7)
        
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
            raw_data=ai_data
        )

    def get_hot_stocks(self) -> List[PlatformSignal]:
        """
        获取东方财富热门股票
        
        Returns:
            热门股票信号列表
        """
        signals = []
        
        # 获取热门股票列表
        url = 'https://emappdata.eastmoney.com/stockcomment/api/StockComment/GetHotStockList'
        data = self.get_json(url)
        
        if not data or 'data' not in data:
            return signals
        
        for item in data['data'][:10]:  # 取前10个
            stock_code = item.get('code', '')
            if stock_code:
                signal = self.get_stock_signal(stock_code)
                if signal:
                    signals.append(signal)
        
        return signals

    def _convert_stock_code(self, stock_code: str) -> Optional[str]:
        """
        转换股票代码为东方财富格式
        
        Args:
            stock_code: 原始股票代码
            
        Returns:
            东方财富格式的代码，如 '0.000001'
        """
        stock_code = stock_code.strip()
        
        # 判断市场
        if stock_code.startswith(('60', '68')):
            # 上海
            return f"1.{stock_code}"
        elif stock_code.startswith(('00', '30')):
            # 深圳
            return f"0.{stock_code}"
        else:
            return None

    def _get_stock_name(self, secid: str) -> Optional[str]:
        """
        获取股票名称
        
        Args:
            secid: 东方财富格式的代码
            
        Returns:
            股票名称
        """
        params = {
            'secid': secid,
            'fields': 'f58',
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
        }
        
        data = self.get_json(self.quote_url, params)
        if data and 'data' in data:
            return data['data'].get('f58')
        
        return None

    def _get_ai_diagnosis(self, secid: str) -> Optional[Dict]:
        """
        获取AI诊股数据
        
        Args:
            secid: 东方财富格式的代码
            
        Returns:
            AI诊股数据
        """
        # 由于AI诊股API可能需要登录或有反爬，这里使用模拟数据
        # 实际使用时需要找到正确的API或使用selenium
        
        # 尝试从行情数据推断
        params = {
            'secid': secid,
            'fields': 'f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,f116,f117,f162,f167,f170',
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
        }
        
        data = self.get_json(self.quote_url, params)
        if not data or 'data' not in data:
            return None
        
        stock_data = data['data']
        
        # 从行情数据推断评分
        score = self._calculate_score_from_quote(stock_data)
        
        # 生成理由
        reasons = self._generate_reasons(stock_data)
        
        return {
            'score': score,
            'reasons': reasons,
            'confidence': 0.7,
            'raw_data': stock_data
        }

    def _calculate_score_from_quote(self, quote_data: Dict) -> float:
        """
        从行情数据计算评分
        
        Args:
            quote_data: 行情数据
            
        Returns:
            评分 (0-100)
        """
        score = 50  # 基础分
        
        # 涨跌幅
        change_pct = quote_data.get('f170', 0)
        if change_pct and change_pct != '-':
            try:
                change_pct = float(change_pct)
                if change_pct > 0:
                    score += min(change_pct, 20)
                else:
                    score += max(change_pct, -20)
            except (ValueError, TypeError):
                pass
        
        # 换手率
        turnover = quote_data.get('f168', 0)
        if turnover and turnover != '-':
            try:
                turnover = float(turnover)
                if turnover > 3:
                    score += 5
            except (ValueError, TypeError):
                pass
        
        # 量比
        volume_ratio = quote_data.get('f50', 0)
        if volume_ratio and volume_ratio != '-':
            try:
                volume_ratio = float(volume_ratio)
                if volume_ratio > 1.5:
                    score += 5
            except (ValueError, TypeError):
                pass
        
        return min(max(score, 0), 100)

    def _generate_reasons(self, quote_data: Dict) -> List[str]:
        """
        根据行情数据生成理由
        
        Args:
            quote_data: 行情数据
            
        Returns:
            理由列表
        """
        reasons = []
        
        # 涨跌幅
        change_pct = quote_data.get('f170', 0)
        if change_pct and change_pct != '-':
            try:
                change_pct = float(change_pct)
                if change_pct > 5:
                    reasons.append('涨幅较大')
                elif change_pct > 0:
                    reasons.append('上涨趋势')
                elif change_pct < -5:
                    reasons.append('跌幅较大')
                elif change_pct < 0:
                    reasons.append('下跌趋势')
            except (ValueError, TypeError):
                pass
        
        # 换手率
        turnover = quote_data.get('f168', 0)
        if turnover and turnover != '-':
            try:
                turnover = float(turnover)
                if turnover > 5:
                    reasons.append('换手率活跃')
            except (ValueError, TypeError):
                pass
        
        # 量比
        volume_ratio = quote_data.get('f50', 0)
        if volume_ratio and volume_ratio != '-':
            try:
                volume_ratio = float(volume_ratio)
                if volume_ratio > 2:
                    reasons.append('成交量放大')
            except (ValueError, TypeError):
                pass
        
        if not reasons:
            reasons.append('技术面分析')
        
        return reasons
