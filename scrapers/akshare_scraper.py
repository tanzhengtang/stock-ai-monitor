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
        获取单个股票的信号
        
        Args:
            stock_code: 股票代码，如 '000001' 或 '600519'
            
        Returns:
            平台信号
        """
        if not self.ak:
            return None
        
        try:
            # 获取行情数据
            quote_data = self._get_quote_data(stock_code)
            
            # 获取财务数据
            financial_data = self._get_financial_data(stock_code)
            
            # 合并数据
            all_data = {**quote_data, **financial_data}
            
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
                platform=Platform.AKSHARE,
                stock_code=stock_code,
                stock_name=stock_name,
                score=score,
                signal_type=signal_type,
                analysis_type=AnalysisType.COMBINED,
                confidence=confidence,
                reasons=reasons,
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

    def _calculate_score(self, data: Dict) -> float:
        """
        计算评分
        
        Args:
            data: 股票数据
            
        Returns:
            评分 (0-100)
        """
        score = 50  # 基础分
        
        # ===== 技术面指标 (30%) =====
        
        # 涨跌幅 (10%)
        change_pct = data.get('change_pct', 0)
        if change_pct > 5:
            score += 10
        elif change_pct > 2:
            score += 7
        elif change_pct > 0:
            score += 3
        elif change_pct < -5:
            score -= 10
        elif change_pct < -2:
            score -= 7
        elif change_pct < 0:
            score -= 3
        
        # 换手率 (10%)
        turnover = data.get('turnover', 0)
        if turnover > 10:
            score += 8
        elif turnover > 5:
            score += 5
        elif turnover < 1:
            score -= 3
        
        # 量比 (10%)
        volume = data.get('volume', 0)
        if volume > 1000000:
            score += 5
        
        # ===== 估值指标 (30%) =====
        
        # 市盈率 (15%)
        pe = data.get('pe', 0)
        if pe > 0:
            if pe < 15:
                score += 15  # 低估值
            elif pe < 25:
                score += 10  # 合理估值
            elif pe < 40:
                score += 5   # 略高
            elif pe > 100:
                score -= 15  # 高估值
            elif pe > 60:
                score -= 10
        
        # 市净率 (15%)
        pb = data.get('pb', 0)
        if pb > 0:
            if pb < 1:
                score += 15  # 破净
            elif pb < 2:
                score += 10  # 合理
            elif pb < 3:
                score += 5
            elif pb > 10:
                score -= 10  # 高估
            elif pb > 6:
                score -= 5
        
        # ===== 盈利能力指标 (25%) =====
        
        # 净资产收益率 (10%)
        roe = data.get('roe', 0)
        if roe > 20:
            score += 10  # 优秀
        elif roe > 15:
            score += 8
        elif roe > 10:
            score += 5  # 良好
        elif roe > 0:
            score += 2
        elif roe < 0:
            score -= 10  # 亏损
        
        # 毛利率 (8%)
        gross_margin = data.get('gross_margin', 0)
        if gross_margin > 50:
            score += 8   # 高毛利
        elif gross_margin > 30:
            score += 5
        elif gross_margin > 15:
            score += 3
        elif gross_margin < 10:
            score -= 5   # 低毛利
        
        # 净利率 (7%)
        net_margin = data.get('net_margin', 0)
        if net_margin > 30:
            score += 7
        elif net_margin > 20:
            score += 5
        elif net_margin > 10:
            score += 3
        elif net_margin < 0:
            score -= 7   # 亏损
        
        # ===== 成长性指标 (15%) =====
        
        # 净利润增长率 (10%)
        profit_growth = data.get('net_profit_growth', 0)
        if profit_growth > 30:
            score += 10  # 高增长
        elif profit_growth > 20:
            score += 8
        elif profit_growth > 10:
            score += 5
        elif profit_growth > 0:
            score += 2
        elif profit_growth < -20:
            score -= 10  # 大幅下降
        
        # 营收增长率 (5%)
        revenue_growth = data.get('revenue_growth', 0)
        if revenue_growth > 20:
            score += 5
        elif revenue_growth > 10:
            score += 3
        elif revenue_growth > 0:
            score += 1
        elif revenue_growth < -10:
            score -= 5
        
        # ===== 财务健康指标 (可选加分) =====
        
        # 资产负债率
        debt_ratio = data.get('debt_ratio', 0)
        if 0 < debt_ratio < 50:
            score += 3  # 财务健康
        elif debt_ratio > 80:
            score -= 5  # 高负债
        
        # 经营现金流
        operating_cashflow = data.get('operating_cashflow', 0)
        net_profit = data.get('net_profit', 0)
        if operating_cashflow > 0 and net_profit > 0:
            # 经营现金流为正且与净利润匹配
            if operating_cashflow > net_profit * 0.8:
                score += 3
        
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
        
        # 估值理由
        pe = data.get('pe', 0)
        if pe > 0:
            if pe < 15:
                reasons.append('低市盈率')
            elif pe < 25:
                reasons.append('估值合理')
            elif pe > 60:
                reasons.append('高市盈率')
        
        pb = data.get('pb', 0)
        if pb > 0:
            if pb < 1:
                reasons.append('破净股')
            elif pb < 2:
                reasons.append('市净率合理')
            elif pb > 6:
                reasons.append('市净率偏高')
        
        # 盈利能力理由
        roe = data.get('roe', 0)
        if roe > 20:
            reasons.append('ROE优秀')
        elif roe > 10:
            reasons.append('ROE良好')
        elif roe < 0:
            reasons.append('ROE为负')
        
        gross_margin = data.get('gross_margin', 0)
        if gross_margin > 50:
            reasons.append('高毛利率')
        
        net_margin = data.get('net_margin', 0)
        if net_margin > 30:
            reasons.append('高净利率')
        elif net_margin < 0:
            reasons.append('净利率为负')
        
        # 成长性理由
        profit_growth = data.get('net_profit_growth', 0)
        if profit_growth > 30:
            reasons.append('利润高增长')
        elif profit_growth > 10:
            reasons.append('利润增长')
        elif profit_growth < -20:
            reasons.append('利润大幅下降')
        
        revenue_growth = data.get('revenue_growth', 0)
        if revenue_growth > 20:
            reasons.append('营收高增长')
        elif revenue_growth > 10:
            reasons.append('营收增长')
        
        # 财务健康理由
        debt_ratio = data.get('debt_ratio', 0)
        if 0 < debt_ratio < 40:
            reasons.append('财务健康')
        elif debt_ratio > 70:
            reasons.append('负债较高')
        
        # 市值理由
        total_mv = data.get('total_mv', 0)
        if total_mv > 100000000000:  # 1000亿
            reasons.append('大盘股')
        elif total_mv > 10000000000:  # 100亿
            reasons.append('中盘股')
        
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
        confidence = 0.4
        
        # 有行情数据增加置信度
        if data.get('price', 0) > 0:
            confidence += 0.1
        
        # 有估值数据增加置信度
        if data.get('pe', 0) > 0:
            confidence += 0.05
        
        if data.get('pb', 0) > 0:
            confidence += 0.05
        
        # 有财务数据增加置信度
        if data.get('revenue', 0) > 0:
            confidence += 0.1
        
        if data.get('net_profit', 0) > 0:
            confidence += 0.1
        
        if data.get('roe', 0) > 0:
            confidence += 0.05
        
        if data.get('gross_margin', 0) > 0:
            confidence += 0.05
        
        if data.get('operating_cashflow', 0) > 0:
            confidence += 0.05
        
        # 有增长率数据增加置信度
        if data.get('net_profit_growth', 0) != 0:
            confidence += 0.05
        
        return min(confidence, 1.0)
