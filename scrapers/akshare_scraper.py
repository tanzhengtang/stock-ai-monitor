"""
AKShare爬虫
使用akshare库获取A股数据，包括行情数据和财务数据
"""

import pandas as pd
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from .base_scraper import BaseScraper
from signal_aggregator.models import PlatformSignal, Platform, SignalType, AnalysisType


class AKShareScraper(BaseScraper):
    """AKShare爬虫
    
    使用akshare获取A股数据：
    - 实时行情数据
    - 历史行情数据
    - 基本面数据（市盈率、市净率、ROE等）
    - 财务数据（利润表、资产负债表、现金流量表）
    """

    def __init__(self, timeout: int = 30, retry_count: int = 3):
        super().__init__(
            platform=Platform.AKSHARE,
            base_url='https://akshare.akfamily.xyz',
            timeout=timeout,
            retry_count=retry_count
        )
        
        try:
            import akshare as ak
            self.ak = ak
        except ImportError:
            self.ak = None
            self.logger.warning("akshare未安装")

    def get_stock_signal(self, stock_code: str) -> Optional[PlatformSignal]:
        """
        获取单个股票的信号（数据采集，不做评分）
        
        Args:
            stock_code: 股票代码，如 '000001' 或 '600519'
            
        Returns:
            平台信号 (score=50, neutral, raw_data包含完整数据)
        """
        if not self.ak:
            return None
        
        try:
            quote_data = self._get_quote_data(stock_code)
            financial_data = self._get_financial_data(stock_code)
            all_data = {**quote_data, **financial_data}
            
            return PlatformSignal(
                platform=Platform.AKSHARE,
                stock_code=stock_code,
                stock_name=all_data.get('name', stock_code),
                score=50,
                signal_type=SignalType.NEUTRAL,
                analysis_type=AnalysisType.COMBINED,
                confidence=0.5,
                reasons=['数据已获取'],
                timestamp=datetime.now(),
                raw_data=all_data,
                fundamental_data=financial_data
            )
        except Exception as e:
            self.logger.error(f"获取{stock_code}数据失败: {e}")
            return None

    def get_hot_stocks(self) -> List[PlatformSignal]:
        """
        获取热门股票
        
        Returns:
            热门股票信号列表
        """
        signals = []
        
        if not self.ak:
            return signals
        
        try:
            # 获取实时行情
            df = self.ak.stock_zh_a_spot_em()
            
            # 按涨跌幅排序，取前10
            df = df.sort_values(by='涨跌幅', ascending=False).head(10)
            
            for _, row in df.iterrows():
                stock_code = str(row['代码']).zfill(6)
                signal = self.get_stock_signal(stock_code)
                if signal:
                    signals.append(signal)
        except Exception as e:
            self.logger.error(f"获取热门股票失败: {e}")
        
        return signals

    def _get_quote_data(self, stock_code: str) -> Dict:
        """
        获取行情数据
        
        Args:
            stock_code: 股票代码
            
        Returns:
            行情数据
        """
        result = {
            'name': stock_code,
            'price': 0,
            'change_pct': 0,
            'volume': 0,
            'amount': 0,
            'high': 0,
            'low': 0,
            'open': 0,
            'turnover': 0,
            'pe': 0,
            'pb': 0,
            'total_mv': 0,
            'circ_mv': 0
        }
        
        try:
            # 获取实时行情
            df = self.ak.stock_zh_a_spot_em()
            
            # 查找股票
            stock_row = df[df['代码'] == stock_code.zfill(6)]
            
            if not stock_row.empty:
                row = stock_row.iloc[0]
                result['name'] = row.get('名称', stock_code)
                result['price'] = self._safe_float(row.get('最新价', 0))
                result['change_pct'] = self._safe_float(row.get('涨跌幅', 0))
                result['volume'] = self._safe_float(row.get('成交量', 0))
                result['amount'] = self._safe_float(row.get('成交额', 0))
                result['high'] = self._safe_float(row.get('最高', 0))
                result['low'] = self._safe_float(row.get('最低', 0))
                result['open'] = self._safe_float(row.get('今开', 0))
                result['turnover'] = self._safe_float(row.get('换手率', 0))
                result['pe'] = self._safe_float(row.get('市盈率-动态', 0))
                result['pb'] = self._safe_float(row.get('市净率', 0))
                result['total_mv'] = self._safe_float(row.get('总市值', 0))
                result['circ_mv'] = self._safe_float(row.get('流通市值', 0))
        except Exception as e:
            self.logger.warning(f"获取行情数据失败: {e}")
        
        return result

    def _get_financial_data(self, stock_code: str) -> Dict:
        """
        获取财务数据
        
        Args:
            stock_code: 股票代码
            
        Returns:
            财务数据
        """
        result = {
            'revenue': 0,              # 营业收入
            'revenue_growth': 0,       # 营收增长率
            'net_profit': 0,           # 净利润
            'net_profit_growth': 0,    # 净利润增长率
            'eps': 0,                  # 每股收益
            'roe': 0,                  # 净资产收益率
            'gross_margin': 0,         # 毛利率
            'net_margin': 0,           # 净利率
            'debt_ratio': 0,           # 资产负债率
            'operating_cashflow': 0,   # 经营现金流
            'bvps': 0,                 # 每股净资产
        }
        
        # 获取主要财务指标
        try:
            df = self.ak.stock_financial_abstract_ths(symbol=stock_code)
            if not df.empty:
                # 获取最新一期数据（最后一行）
                latest = df.iloc[-1]
                
                result['revenue'] = self._parse_financial_value(latest.get('营业总收入', 0))
                result['net_profit'] = self._parse_financial_value(latest.get('净利润', 0))
                result['eps'] = self._safe_float(latest.get('基本每股收益', 0))
                result['roe'] = self._parse_percentage(latest.get('净资产收益率', 0))
                result['gross_margin'] = self._parse_percentage(latest.get('销售毛利率', 0))
                result['net_margin'] = self._parse_percentage(latest.get('销售净利率', 0))
                result['debt_ratio'] = self._parse_percentage(latest.get('资产负债率', 0))
                result['bvps'] = self._safe_float(latest.get('每股净资产', 0))
                
                # 计算增长率（与去年同期比较）
                if len(df) > 4:
                    # 找去年同期数据
                    current_period = str(latest.get('报告期', ''))
                    if '12-31' in current_period:
                        prev_year = int(current_period[:4]) - 1
                        prev_period = f"{prev_year}-12-31"
                        prev_rows = df[df['报告期'] == prev_period]
                        if not prev_rows.empty:
                            prev = prev_rows.iloc[0]
                            prev_revenue = self._parse_financial_value(prev.get('营业总收入', 0))
                            prev_profit = self._parse_financial_value(prev.get('净利润', 0))
                            
                            if prev_revenue > 0:
                                result['revenue_growth'] = (result['revenue'] - prev_revenue) / prev_revenue * 100
                            if prev_profit > 0:
                                result['net_profit_growth'] = (result['net_profit'] - prev_profit) / prev_profit * 100
        except Exception as e:
            self.logger.warning(f"获取财务指标失败: {e}")
        
        # 获取现金流量表数据
        try:
            df_cash = self.ak.stock_financial_cash_ths(symbol=stock_code, indicator='报告期')
            if not df_cash.empty:
                latest = df_cash.iloc[0]
                result['operating_cashflow'] = self._parse_financial_value(
                    latest.get('*经营活动产生的现金流量净额', 0)
                )
        except Exception as e:
            self.logger.warning(f"获取现金流量数据失败: {e}")
        
        return result

    def _safe_float(self, value, default: float = 0) -> float:
        """安全转换为浮点数"""
        try:
            if value is None or value == '' or value == 'False':
                return default
            return float(value)
        except (ValueError, TypeError):
            return default

    def _parse_financial_value(self, value) -> float:
        """
        解析财务数值，处理'亿'、'万'等单位
        
        Args:
            value: 原始值
            
        Returns:
            数值（元）
        """
        if value is None or value == '' or value == 'False':
            return 0
        
        try:
            value_str = str(value).strip()
            
            # 处理'亿'单位
            if '亿' in value_str:
                num = float(value_str.replace('亿', ''))
                return num * 100000000
            
            # 处理'万'单位
            if '万' in value_str:
                num = float(value_str.replace('万', ''))
                return num * 10000
            
            # 处理'%'单位
            if '%' in value_str:
                return float(value_str.replace('%', ''))
            
            return float(value_str)
        except (ValueError, TypeError):
            return 0

    def _parse_percentage(self, value) -> float:
        """
        解析百分比值
        
        Args:
            value: 原始值
            
        Returns:
            百分比数值
        """
        if value is None or value == '' or value == 'False':
            return 0
        
        try:
            value_str = str(value).strip()
            
            # 处理'%'单位
            if '%' in value_str:
                return float(value_str.replace('%', ''))
            
            return float(value_str)
        except (ValueError, TypeError):
            return 0


    # ================================================================
    # 评分系统已迁移至 scheduler/predictor.py
    #   StockPredictor._calculate_fundamental_score()
    # 爬虫仅负责数据采集，不再执行评分
    # ================================================================
