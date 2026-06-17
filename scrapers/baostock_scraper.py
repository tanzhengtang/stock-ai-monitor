"""
BaoStock爬虫
使用baostock库获取A股数据，包括行情数据和基本面数据
"""

import pandas as pd
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from .base_scraper import BaseScraper
from signal_aggregator.models import PlatformSignal, Platform, SignalType, AnalysisType


class BaoStockScraper(BaseScraper):
    """BaoStock爬虫
    
    使用baostock获取A股数据：
    - 历史行情数据
    - 基本面数据（市盈率、市净率、ROE等）
    - 财务数据
    - 季频数据
    """

    def __init__(self, timeout: int = 30, retry_count: int = 3):
        super().__init__(
            platform=Platform.OTHER,
            base_url='http://baostock.com',
            timeout=timeout,
            retry_count=retry_count
        )
        
        self.bs = None
        self._login_status = False

    def _init_baostock(self):
        """初始化baostock连接"""
        if self.bs is None:
            try:
                import baostock as bs
                self.bs = bs
                # 登录
                login_result = bs.login()
                if login_result.error_code == '0':
                    self._login_status = True
                    self.logger.info("BaoStock登录成功")
                else:
                    self.logger.error(f"BaoStock登录失败: {login_result.error_msg}")
            except ImportError:
                self.logger.warning("baostock未安装")
            except Exception as e:
                self.logger.error(f"BaoStock初始化失败: {e}")

    def close(self):
        """关闭连接"""
        if self.bs and self._login_status:
            self.bs.logout()
            self._login_status = False
        super().close()

    def get_stock_signal(self, stock_code: str) -> Optional[PlatformSignal]:
        """
        获取单个股票的信号（数据采集，不做评分）
        
        Args:
            stock_code: 股票代码，如 '000001' 或 '600519'
            
        Returns:
            平台信号 (score=50, neutral, raw_data包含完整数据)
        """
        self._init_baostock()
        
        if not self.bs or not self._login_status:
            return None
        
        try:
            bs_code = self._convert_stock_code(stock_code)
            if not bs_code:
                return None
            
            quote_data = self._get_quote_data(bs_code)
            fundamental_data = self._get_fundamental_data(bs_code)
            all_data = {**quote_data, **fundamental_data}
            all_data['stock_code'] = stock_code
            
            return PlatformSignal(
                platform=Platform.BAOSTOCK,
                stock_code=stock_code,
                stock_name=all_data.get('name', stock_code),
                score=50,
                signal_type=SignalType.NEUTRAL,
                analysis_type=AnalysisType.COMBINED,
                confidence=0.5,
                reasons=['数据已获取'],
                timestamp=datetime.now(),
                raw_data=all_data,
                fundamental_data=fundamental_data
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
        # baostock不直接提供热门股票，返回空列表
        return []

    def _convert_stock_code(self, stock_code: str) -> Optional[str]:
        """
        转换股票代码为baostock格式
        
        Args:
            stock_code: 原始股票代码
            
        Returns:
            baostock格式的代码，如 'sh.600519'
        """
        stock_code = stock_code.strip()
        
        # 判断市场
        if stock_code.startswith(('60', '68')):
            # 上海
            return f"sh.{stock_code}"
        elif stock_code.startswith(('00', '30')):
            # 深圳
            return f"sz.{stock_code}"
        else:
            return None

    def _get_quote_data(self, bs_code: str) -> Dict:
        """
        获取行情数据
        
        Args:
            bs_code: baostock格式的股票代码
            
        Returns:
            行情数据
        """
        result = {
            'price': 0,
            'change_pct': 0,
            'volume': 0,
            'amount': 0,
            'high': 0,
            'low': 0,
            'open': 0,
            'turnover': 0
        }
        
        try:
            # 获取最近30天的历史数据
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            rs = self.bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount,turn",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2"
            )
            
            if rs.error_code == '0':
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                
                if data_list:
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    
                    # 获取最新数据
                    latest = df.iloc[-1]
                    result['price'] = float(latest.get('close', 0))
                    result['volume'] = float(latest.get('volume', 0))
                    result['amount'] = float(latest.get('amount', 0))
                    result['high'] = float(latest.get('high', 0))
                    result['low'] = float(latest.get('low', 0))
                    result['open'] = float(latest.get('open', 0))
                    result['turnover'] = float(latest.get('turn', 0))
                    
                    # 计算涨跌幅
                    if len(df) > 1:
                        prev_close = float(df.iloc[-2]['close'])
                        if prev_close > 0:
                            result['change_pct'] = (result['price'] - prev_close) / prev_close * 100
                    
                    # 获取股票名称
                    stock_info = self.bs.query_stock_basic(code=bs_code)
                    if stock_info.error_code == '0':
                        info_data = []
                        while stock_info.next():
                            info_data.append(stock_info.get_row_data())
                        if info_data:
                            result['name'] = info_data[0][1]  # 股票名称
        except Exception as e:
            self.logger.warning(f"获取行情数据失败: {e}")
        
        return result

    def _get_fundamental_data(self, bs_code: str) -> Dict:
        """
        获取基本面数据
        
        Args:
            bs_code: baostock格式的股票代码
            
        Returns:
            基本面数据
        """
        result = {
            'pe': 0,
            'pb': 0,
            'roe': 0,
            'total_mv': 0,
            'circ_mv': 0,
            'revenue': 0,
            'profit': 0,
            'profit_growth': 0
        }
        
        try:
            # 获取最新的季度报告数据
            current_year = datetime.now().year
            current_quarter = (datetime.now().month - 1) // 3 + 1
            
            # 获取盈利能力数据
            rs = self.bs.query_profit_data(code=bs_code, year=current_year, quarter=current_quarter)
            if rs.error_code == '0':
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                
                if data_list:
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    latest = df.iloc[0]
                    result['roe'] = float(latest.get('roeAvg', 0)) * 100  # 转换为百分比
                    result['profit'] = float(latest.get('npMargin', 0))
            
            # 获取成长能力数据
            rs = self.bs.query_growth_data(code=bs_code, year=current_year, quarter=current_quarter)
            if rs.error_code == '0':
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                
                if data_list:
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    latest = df.iloc[0]
                    result['profit_growth'] = float(latest.get('YOYEquity', 0))
            
            # 获取估值数据（市盈率、市净率）
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            rs = self.bs.query_history_k_data_plus(
                bs_code,
                "date,peTTM,pbMRQ",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2"
            )
            
            if rs.error_code == '0':
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                
                if data_list:
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    latest = df.iloc[-1]
                    result['pe'] = float(latest.get('peTTM', 0))
                    result['pb'] = float(latest.get('pbMRQ', 0))
        except Exception as e:
            self.logger.warning(f"获取基本面数据失败: {e}")
        
        return result

    # ================================================================
    # 评分系统已迁移至 scheduler/predictor.py
    #   StockPredictor._calculate_fundamental_score()
    # 爬虫仅负责数据采集，不再执行评分
    # ================================================================
