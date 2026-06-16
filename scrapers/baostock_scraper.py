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
        获取单个股票的信号
        
        Args:
            stock_code: 股票代码，如 '000001' 或 '600519'
            
        Returns:
            平台信号
        """
        self._init_baostock()
        
        if not self.bs or not self._login_status:
            return None
        
        try:
            # 转换股票代码格式
            bs_code = self._convert_stock_code(stock_code)
            if not bs_code:
                return None
            
            # 获取行情数据
            quote_data = self._get_quote_data(bs_code)
            
            # 获取基本面数据
            fundamental_data = self._get_fundamental_data(bs_code)
            
            # 合并数据
            all_data = {**quote_data, **fundamental_data}
            all_data['stock_code'] = stock_code
            
            # 计算评分
            score = self._calculate_score(all_data)
            
            # 生成理由
            reasons = self._generate_reasons(all_data)
            
            # 计算置信度
            confidence = self._calculate_confidence(all_data)
            
            # 获取股票名称
            stock_name = all_data.get('name', stock_code)
            
            # 生成信号
            signal_type = self.score_to_signal_type(score)
            
            return PlatformSignal(
                platform=Platform.BAOSTOCK,
                stock_code=stock_code,
                stock_name=stock_name,
                score=score,
                signal_type=signal_type,
                analysis_type=AnalysisType.COMBINED,
                confidence=confidence,
                reasons=reasons,
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

    def _calculate_score(self, data: Dict) -> float:
        """
        计算评分
        
        Args:
            data: 股票数据
            
        Returns:
            评分 (0-100)
        """
        score = 50  # 基础分
        
        # ===== 技术面指标 (40%) =====
        
        # 涨跌幅 (15%)
        change_pct = data.get('change_pct', 0)
        if change_pct > 5:
            score += 15
        elif change_pct > 2:
            score += 10
        elif change_pct > 0:
            score += 5
        elif change_pct < -5:
            score -= 15
        elif change_pct < -2:
            score -= 10
        elif change_pct < 0:
            score -= 5
        
        # 换手率 (10%)
        turnover = data.get('turnover', 0)
        if turnover > 10:
            score += 10
        elif turnover > 5:
            score += 5
        elif turnover < 1:
            score -= 5
        
        # 量比 (15%)
        volume = data.get('volume', 0)
        if volume > 1000000:
            score += 10
        
        # ===== 基本面指标 (60%) =====
        
        # 市盈率 (20%)
        pe = data.get('pe', 0)
        if pe > 0:
            if pe < 15:
                score += 20
            elif pe < 25:
                score += 10
            elif pe > 100:
                score -= 15
            elif pe > 60:
                score -= 10
        
        # 市净率 (15%)
        pb = data.get('pb', 0)
        if pb > 0:
            if pb < 1:
                score += 15
            elif pb < 2:
                score += 10
            elif pb > 10:
                score -= 10
        
        # 净资产收益率 (15%)
        roe = data.get('roe', 0)
        if roe > 20:
            score += 15
        elif roe > 10:
            score += 10
        elif roe > 0:
            score += 5
        
        # 利润增长 (10%)
        profit_growth = data.get('profit_growth', 0)
        if profit_growth > 30:
            score += 10
        elif profit_growth > 10:
            score += 5
        
        return min(max(score, 0), 100)

    def _generate_reasons(self, data: Dict) -> List[str]:
        """
        生成理由
        
        Args:
            data: 股票数据
            
        Returns:
            理由列表
        """
        reasons = []
        
        # 技术面理由
        change_pct = data.get('change_pct', 0)
        if change_pct > 5:
            reasons.append('涨幅较大')
        elif change_pct > 0:
            reasons.append('上涨趋势')
        elif change_pct < -5:
            reasons.append('跌幅较大')
        elif change_pct < 0:
            reasons.append('下跌趋势')
        
        # 基本面理由
        pe = data.get('pe', 0)
        if pe > 0:
            if pe < 15:
                reasons.append('低市盈率')
            elif pe < 25:
                reasons.append('估值合理')
            elif pe > 100:
                reasons.append('高市盈率')
        
        pb = data.get('pb', 0)
        if pb > 0:
            if pb < 1:
                reasons.append('破净股')
            elif pb < 2:
                reasons.append('市净率合理')
        
        roe = data.get('roe', 0)
        if roe > 20:
            reasons.append('ROE优秀')
        elif roe > 10:
            reasons.append('ROE良好')
        
        profit_growth = data.get('profit_growth', 0)
        if profit_growth > 30:
            reasons.append('高成长')
        elif profit_growth > 10:
            reasons.append('稳定增长')
        
        if not reasons:
            reasons.append('综合分析')
        
        return reasons

    def _calculate_confidence(self, data: Dict) -> float:
        """
        计算置信度
        
        Args:
            data: 股票数据
            
        Returns:
            置信度 (0-1)
        """
        confidence = 0.5
        
        # 有行情数据增加置信度
        if data.get('price', 0) > 0:
            confidence += 0.1
        
        # 有基本面数据增加置信度
        if data.get('pe', 0) > 0:
            confidence += 0.1
        
        if data.get('pb', 0) > 0:
            confidence += 0.1
        
        # 有财务数据增加置信度
        if data.get('roe', 0) > 0:
            confidence += 0.1
        
        if data.get('profit_growth', 0) > 0:
            confidence += 0.1
        
        return min(confidence, 1.0)
