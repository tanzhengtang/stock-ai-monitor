"""
股票预测模块
支持全A股扫描，集成策略模块和策略评估器
"""

import requests
import numpy as np
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from strategies import get_strategy, STRATEGY_REGISTRY
from strategy_evaluator import StrategyEvaluator


class StockPredictor:
    """股票预测器
    
    功能：
    1. 支持全A股扫描（5000+只）
    2. 使用多种量化策略分析
    3. 根据策略权重计算综合评分
    4. 预测可能上涨的股票
    """

    def __init__(self, data_dir: str = None):
        self.logger = logging.getLogger('StockPredictor')
        self.data_dir = Path(data_dir or 'data')
        self.data_dir.mkdir(exist_ok=True)
        
        # 策略评估器
        self.evaluator = StrategyEvaluator(data_dir)
        
        # 股票池
        self.stock_pool: Dict[str, str] = {}
        self.sector_stocks: Dict[str, Dict[str, str]] = {}
        
        # 板块定义
        self.sectors = {
            '金融': {'prefix': ['601', '600000', '601318', '601398', '601166', '600036', '600030']},
            '消费': {'prefix': ['600519', '000858', '000333', '000651', '600887', '000568', '600809']},
            '科技': {'prefix': ['300', '002', '688']},
            '新能源': {'prefix': ['002594', '601012', '600089', '601985']},
            '医药': {'prefix': ['600276', '300760', '603259', '600436']},
            '军工': {'prefix': ['600765', '000547', '601766', '000768']},
            '周期': {'prefix': ['601899', '600585', '600309', '601857']},
        }
        
        # 历史数据缓存
        self._history_cache = {}
        
        # 加载股票列表
        self._load_stock_pool()

    def _load_stock_pool(self):
        """加载股票池"""
        # 尝试从文件加载
        stock_file = self.data_dir / 'all_stocks.json'
        
        if stock_file.exists():
            try:
                with open(stock_file, 'r', encoding='utf-8') as f:
                    stocks = json.load(f)
                
                for stock in stocks:
                    code = stock['code']
                    name = stock['name']
                    self.stock_pool[code] = name
                
                self.logger.info(f"从文件加载 {len(self.stock_pool)} 只股票")
                
                # 按板块分类
                self._classify_stocks()
                
            except Exception as e:
                self.logger.warning(f"加载股票列表失败: {e}")
                self._load_default_pool()
        else:
            self.logger.info("股票列表文件不存在，使用默认列表")
            self._load_default_pool()

    def _load_default_pool(self):
        """加载默认股票池"""
        self.stock_pool = {
            'sh600519': '贵州茅台', 'sh601318': '中国平安', 'sh600036': '招商银行',
            'sh600900': '长江电力', 'sh601166': '兴业银行', 'sh600276': '恒瑞医药',
            'sh601398': '工商银行', 'sh600030': '中信证券', 'sz000858': '五粮液',
            'sz000333': '美的集团', 'sz000651': '格力电器', 'sz002594': '比亚迪',
            'sz300750': '宁德时代', 'sz300059': '东方财富', 'sz000001': '平安银行',
            'sh601888': '中国中免', 'sh600809': '山西汾酒', 'sh600887': '伊利股份',
            'sh601012': '隆基绿能', 'sz002475': '立讯精密', 'sz000568': '泸州老窖',
            'sz002714': '牧原股份', 'sh601899': '紫金矿业', 'sh600585': '海螺水泥',
            'sh601668': '中国建筑', 'sh600309': '万华化学', 'sh601857': '中国石油',
            'sz002352': '顺丰控股', 'sz300760': '迈瑞医疗', 'sz002415': '海康威视',
            'sh600765': '中航重机', 'sh601985': '中国核电', 'sh600089': '特变电工',
            'sh601633': '长城汽车', 'sz000547': '航天发展', 'sh600104': '上汽集团',
            'sh601766': '中国中车', 'sh600436': '片仔癀', 'sz002241': '歌尔股份',
            'sh600028': '中国石化', 'sh600000': '浦发银行', 'sh601288': '农业银行',
            'sz002230': '科大讯飞', 'sh600050': '中国联通', 'sh688981': '中芯国际',
            'sz300124': '汇川技术', 'sz002371': '北方华创', 'sh603259': '药明康德',
            'sh601669': '中国电建', 'sh600745': '闻泰科技', 'sh601601': '中国太保',
        }
        self._classify_stocks()

    def _classify_stocks(self):
        """按板块分类股票"""
        self.sector_stocks = {sector: {} for sector in self.sectors}
        self.sector_stocks['其他'] = {}
        
        for code, name in self.stock_pool.items():
            classified = False
            for sector, config in self.sectors.items():
                # 检查是否匹配板块
                for prefix in config.get('prefix', []):
                    if code.startswith(prefix) or code.endswith(prefix):
                        self.sector_stocks[sector][code] = name
                        classified = True
                        break
                if classified:
                    break
            
            if not classified:
                self.sector_stocks['其他'][code] = name

    def refresh_stock_pool(self):
        """
        刷新股票池（从新浪财经获取最新列表）
        """
        self.logger.info("开始刷新股票池...")
        
        url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
        all_stocks = []
        
        # 获取沪市A股
        for page in range(1, 30):
            params = {
                'page': page,
                'num': 100,
                'sort': 'symbol',
                'asc': 1,
                'node': 'sh_a',
                'symbol': '',
                '_s_r_a': 'sort'
            }
            
            try:
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    data = json.loads(resp.text)
                    if not data:
                        break
                    
                    for item in data:
                        all_stocks.append({
                            'code': item.get('code', ''),
                            'name': item.get('name', ''),
                            'market': 'SH',
                            'price': float(item.get('trade', 0)),
                            'change': float(item.get('changepercent', 0)),
                            'pe': float(item.get('per', 0)),
                            'pb': float(item.get('pb', 0))
                        })
                else:
                    break
            except Exception as e:
                self.logger.warning(f"获取沪市股票失败: {e}")
                break
            
            import time
            time.sleep(0.3)
        
        # 获取深市A股
        for page in range(1, 30):
            params = {
                'page': page,
                'num': 100,
                'sort': 'symbol',
                'asc': 1,
                'node': 'sz_a',
                'symbol': '',
                '_s_r_a': 'sort'
            }
            
            try:
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    data = json.loads(resp.text)
                    if not data:
                        break
                    
                    for item in data:
                        all_stocks.append({
                            'code': item.get('code', ''),
                            'name': item.get('name', ''),
                            'market': 'SZ',
                            'price': float(item.get('trade', 0)),
                            'change': float(item.get('changepercent', 0)),
                            'pe': float(item.get('per', 0)),
                            'pb': float(item.get('pb', 0))
                        })
                else:
                    break
            except Exception as e:
                self.logger.warning(f"获取深市股票失败: {e}")
                break
            
            import time
            time.sleep(0.3)
        
        # 保存到文件
        stock_file = self.data_dir / 'all_stocks.json'
        with open(stock_file, 'w', encoding='utf-8') as f:
            json.dump(all_stocks, f, ensure_ascii=False, indent=2)
        
        # 更新股票池
        self.stock_pool = {}
        for stock in all_stocks:
            self.stock_pool[stock['code']] = stock['name']
        
        self._classify_stocks()
        
        self.logger.info(f"股票池刷新完成: {len(self.stock_pool)} 只股票")
        
        return all_stocks

    def get_sector_list(self) -> List[str]:
        """获取板块列表"""
        return list(self.sector_stocks.keys())

    def get_sector_stocks(self, sector: str) -> Dict[str, str]:
        """获取板块股票"""
        return self.sector_stocks.get(sector, {})

    def _get_realtime_batch(self, codes: List[str]) -> Dict[str, Dict]:
        """
        批量获取实时行情
        
        Args:
            codes: 股票代码列表
            
        Returns:
            {code: {price, change_pct, ...}}
        """
        results = {}
        
        # 构建请求代码
        sina_codes = []
        for code in codes:
            if code.startswith('6') or code.startswith('9'):
                sina_codes.append(f'sh{code}')
            else:
                sina_codes.append(f'sz{code}')
        
        # 分批请求（每批最多50只）
        batch_size = 50
        for i in range(0, len(sina_codes), batch_size):
            batch = sina_codes[i:i+batch_size]
            codes_str = ','.join(batch)
            
            url = f'http://hq.sinajs.cn/list={codes_str}'
            headers = {'Referer': 'https://finance.sina.com.cn'}
            
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                lines = resp.text.strip().split('\n')
                
                for line in lines:
                    try:
                        parts = line.split('=')
                        sina_code = parts[0].split('_')[-1]
                        code = sina_code[2:]
                        
                        data = parts[1].strip('"').split(',')
                        
                        if len(data) >= 32:
                            name = data[0]
                            open_price = float(data[1]) if data[1] else 0
                            prev_close = float(data[2]) if data[2] else 0
                            current = float(data[3]) if data[3] else 0
                            high = float(data[4]) if data[4] else 0
                            low = float(data[5]) if data[5] else 0
                            volume = float(data[8]) if data[8] else 0
                            
                            change_pct = (current - prev_close) / prev_close * 100 if prev_close > 0 else 0
                            
                            results[code] = {
                                'name': name,
                                'open': open_price,
                                'prev_close': prev_close,
                                'price': current,
                                'high': high,
                                'low': low,
                                'volume': volume,
                                'change_pct': change_pct
                            }
                    except Exception as e:
                        continue
                        
            except Exception as e:
                self.logger.warning(f"批量获取行情失败: {e}")
        
        return results

    def _get_history_data(self, stock_code: str, days: int = 60) -> Optional[List[Dict]]:
        """获取历史数据"""
        if stock_code in self._history_cache:
            return self._history_cache[stock_code]
        
        try:
            sina_code = f'sh{stock_code}' if stock_code.startswith('6') else f'sz{stock_code}'
            url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sina_code}&scale=240&ma=no&datalen={days}'
            
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = json.loads(resp.text)
                
                history = []
                for item in data:
                    history.append({
                        'date': item['day'],
                        'open': float(item['open']),
                        'high': float(item['high']),
                        'low': float(item['low']),
                        'close': float(item['close']),
                        'volume': float(item['volume'])
                    })
                
                self._history_cache[stock_code] = history
                return history
            
            return None
            
        except Exception as e:
            return None

    def analyze_stock(self, code: str, name: str, realtime_data: Dict, history: List[Dict] = None) -> Optional[Dict]:
        """
        分析单只股票
        
        Args:
            code: 股票代码
            name: 股票名称
            realtime_data: 实时数据
            history: 历史数据（可选）
            
        Returns:
            分析结果
        """
        try:
            # 计算基础评分（基于实时数据）
            base_score = 50
            reasons = []
            
            change_pct = realtime_data.get('change_pct', 0)
            price = realtime_data.get('price', 0)
            open_price = realtime_data.get('open', 0)
            
            # 涨跌幅评分
            if 0 < change_pct < 2:
                base_score += 8
                reasons.append('温和上涨')
            elif 2 <= change_pct < 5:
                base_score += 5
            elif change_pct > 5:
                base_score -= 5
            
            # 开盘位置
            if price > open_price and change_pct > 0:
                base_score += 5
                reasons.append('高开高走')
            
            # 如果有历史数据，进行策略分析
            strategy_result = {'strategy_signals': {}, 'weighted_score': base_score, 'details': {}}
            tech_details = {}
            
            if history and len(history) >= 20:
                strategy_result = self._analyze_with_strategies(history)
                tech_details = self._calculate_indicators(history)
                
                # 更新理由
                signals = strategy_result['strategy_signals']
                if signals.get('ma_cross') == 'buy':
                    reasons.append('均线多头')
                if signals.get('rsi_reversal') in ['buy', 'strong_buy']:
                    reasons.append('RSI低位')
                if signals.get('macd_signal') == 'buy':
                    reasons.append('MACD金叉')
                if signals.get('bollinger_band') == 'buy':
                    reasons.append('布林下轨')
                if signals.get('volume_price') == 'buy':
                    reasons.append('放量上涨')
            
            # 最终评分
            final_score = strategy_result.get('weighted_score', base_score)
            
            # 预期收益
            expected_move = self._calculate_expected_move(
                realtime_data, tech_details, strategy_result.get('strategy_signals', {})
            )
            
            return {
                'code': code,
                'name': name,
                'price': price,
                'open': open_price,
                'high': realtime_data.get('high', 0),
                'low': realtime_data.get('low', 0),
                'prev_close': realtime_data.get('prev_close', 0),
                'change': change_pct,
                'volume': realtime_data.get('volume', 0),
                'score': final_score,
                'reasons': ', '.join(reasons[:3]) if reasons else '中性',
                'strategy_signals': strategy_result.get('strategy_signals', {}),
                'strategy_details': strategy_result.get('details', {}),
                'tech_details': tech_details,
                'expected_move': expected_move,
                'has_history': history is not None and len(history) >= 20
            }
            
        except Exception as e:
            return None

    def _analyze_with_strategies(self, history: List[Dict]) -> Dict:
        """使用策略分析"""
        if not history or len(history) < 30:
            return {'strategy_signals': {}, 'weighted_score': 50, 'details': {}}
        
        closes = [h['close'] for h in history]
        
        strategy_signals = {}
        details = {}
        
        # 1. 均线交叉策略
        try:
            ma5 = np.mean(closes[-5:])
            ma10 = np.mean(closes[-10:])
            ma20 = np.mean(closes[-20:])
            
            if ma5 > ma10 > ma20:
                strategy_signals['ma_cross'] = 'buy'
            elif ma5 < ma10 < ma20:
                strategy_signals['ma_cross'] = 'sell'
            else:
                strategy_signals['ma_cross'] = 'neutral'
            
            details['ma'] = {'ma5': ma5, 'ma10': ma10, 'ma20': ma20}
        except:
            pass
        
        # 2. RSI策略
        try:
            if len(closes) >= 15:
                deltas = np.diff(closes[-15:])
                gains = np.where(deltas > 0, deltas, 0)
                losses = np.where(deltas < 0, -deltas, 0)
                avg_gain = np.mean(gains)
                avg_loss = np.mean(losses)
                
                if avg_loss > 0:
                    rsi = 100 - (100 / (1 + avg_gain / avg_loss))
                else:
                    rsi = 100
                
                if rsi < 30:
                    strategy_signals['rsi_reversal'] = 'strong_buy'
                elif rsi < 40:
                    strategy_signals['rsi_reversal'] = 'buy'
                elif rsi > 70:
                    strategy_signals['rsi_reversal'] = 'sell'
                else:
                    strategy_signals['rsi_reversal'] = 'neutral'
                
                details['rsi'] = rsi
        except:
            pass
        
        # 3. MACD策略
        try:
            if len(closes) >= 26:
                ema12 = self._calculate_ema(closes, 12)
                ema26 = self._calculate_ema(closes, 26)
                macd = ema12 - ema26
                
                if macd > 0:
                    strategy_signals['macd_signal'] = 'buy'
                else:
                    strategy_signals['macd_signal'] = 'sell'
                
                details['macd'] = macd
        except:
            pass
        
        # 4. KDJ策略
        try:
            if len(history) >= 9:
                highs = [h['high'] for h in history[-9:]]
                lows = [h['low'] for h in history[-9:]]
                
                high_max = max(highs)
                low_min = min(lows)
                
                if high_max != low_min:
                    rsv = (closes[-1] - low_min) / (high_max - low_min) * 100
                else:
                    rsv = 50
                
                if rsv < 20:
                    strategy_signals['kdj_signal'] = 'buy'
                elif rsv > 80:
                    strategy_signals['kdj_signal'] = 'sell'
                else:
                    strategy_signals['kdj_signal'] = 'neutral'
                
                details['kdj'] = rsv
        except:
            pass
        
        # 5. 布林带策略
        try:
            if len(closes) >= 20:
                ma20 = np.mean(closes[-20:])
                std20 = np.std(closes[-20:])
                
                upper = ma20 + 2 * std20
                lower = ma20 - 2 * std20
                
                if closes[-1] < lower:
                    strategy_signals['bollinger_band'] = 'buy'
                elif closes[-1] > upper:
                    strategy_signals['bollinger_band'] = 'sell'
                else:
                    strategy_signals['bollinger_band'] = 'neutral'
                
                details['bollinger'] = {'upper': upper, 'lower': lower}
        except:
            pass
        
        # 6. 动量策略
        try:
            if len(closes) >= 20:
                momentum = (closes[-1] - closes[-20]) / closes[-20] * 100
                
                if momentum > 5:
                    strategy_signals['momentum'] = 'buy'
                elif momentum < -5:
                    strategy_signals['momentum'] = 'sell'
                else:
                    strategy_signals['momentum'] = 'neutral'
                
                details['momentum'] = momentum
        except:
            pass
        
        # 7. 量价关系策略
        try:
            volumes = [h['volume'] for h in history]
            if len(volumes) >= 5:
                vol_ma = np.mean(volumes[-5:])
                price_change = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) >= 2 else 0
                
                if volumes[-1] > vol_ma * 1.3 and price_change > 0:
                    strategy_signals['volume_price'] = 'buy'
                elif volumes[-1] > vol_ma * 1.3 and price_change < 0:
                    strategy_signals['volume_price'] = 'sell'
                else:
                    strategy_signals['volume_price'] = 'neutral'
                
                details['volume'] = {'current': volumes[-1], 'ma5': vol_ma}
        except:
            pass
        
        # 计算加权评分
        weighted_score = self.evaluator.get_weighted_score(strategy_signals)
        
        return {
            'strategy_signals': strategy_signals,
            'weighted_score': weighted_score,
            'details': details
        }

    def _calculate_ema(self, data: List[float], period: int) -> float:
        """计算EMA"""
        if len(data) < period:
            return data[-1] if data else 0
        
        multiplier = 2 / (period + 1)
        ema = data[0]
        
        for price in data[1:]:
            ema = (price - ema) * multiplier + ema
        
        return ema

    def _calculate_indicators(self, history: List[Dict]) -> Dict:
        """计算技术指标"""
        if not history or len(history) < 20:
            return {}
        
        closes = [h['close'] for h in history]
        volumes = [h['volume'] for h in history]
        highs = [h['high'] for h in history]
        lows = [h['low'] for h in history]
        
        # 均线
        ma5 = np.mean(closes[-5:])
        ma10 = np.mean(closes[-10:])
        ma20 = np.mean(closes[-20:])
        
        # RSI
        rsi = 50
        if len(closes) >= 15:
            deltas = np.diff(closes[-15:])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            if avg_loss > 0:
                rsi = 100 - (100 / (1 + avg_gain / avg_loss))
        
        # 布林带
        bb_ma = np.mean(closes[-20:])
        bb_std = np.std(closes[-20:])
        bb_upper = bb_ma + 2 * bb_std
        bb_lower = bb_ma - 2 * bb_std
        
        # 波动率
        if len(closes) >= 21:
            returns = np.diff(closes[-20:]) / closes[-20:-1] * 100
            volatility = np.std(returns)
        else:
            volatility = 2.0
        
        # 成交量比率
        vol_ma5 = np.mean(volumes[-5:])
        vol_ratio = volumes[-1] / vol_ma5 if vol_ma5 > 0 else 1.0
        
        # 支撑位和阻力位
        support = min(lows[-20:])
        resistance = max(highs[-20:])
        
        return {
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'ma20': round(ma20, 2),
            'rsi': round(rsi, 1),
            'bb_upper': round(bb_upper, 2),
            'bb_middle': round(bb_ma, 2),
            'bb_lower': round(bb_lower, 2),
            'volatility': round(volatility, 2),
            'vol_ratio': round(vol_ratio, 2),
            'support': round(support, 2),
            'resistance': round(resistance, 2)
        }

    def _calculate_expected_move(self, realtime_data: Dict, tech_details: Dict, strategy_signals: Dict) -> Dict:
        """计算预期收益"""
        current_price = realtime_data.get('price', 0)
        if current_price <= 0:
            return {
                'expected_pct': 0,
                'expected_points': 0,
                'target_price': 0,
                'stop_loss': 0,
                'confidence': 0
            }
        
        # 基础预期
        base_expected = 2.0
        
        # 根据策略信号调整
        signal_boost = 0
        buy_count = 0
        sell_count = 0
        
        for strategy, signal in strategy_signals.items():
            weight = self.evaluator.strategy_weights.get(strategy, 0.5)
            if signal in ['buy', 'strong_buy']:
                buy_count += 1
                signal_boost += 1.5 * weight
            elif signal in ['sell', 'strong_sell']:
                sell_count += 1
                signal_boost -= 1.5 * weight
        
        # 根据RSI调整
        rsi = tech_details.get('rsi', 50)
        if rsi < 30:
            signal_boost += 1.0
        elif rsi > 70:
            signal_boost -= 0.5
        
        # 根据波动率调整
        volatility = tech_details.get('volatility', 2.0)
        volatility_factor = volatility / 2.0
        
        # 计算预期
        expected_pct = (base_expected + signal_boost) * volatility_factor
        expected_pct = max(min(expected_pct, 10), -5)
        
        expected_points = current_price * expected_pct / 100
        target_price = current_price * (1 + expected_pct / 100)
        stop_loss = current_price * 0.95
        
        # 置信度
        confidence = 50 + (buy_count - sell_count) * 10
        confidence = max(min(confidence, 90), 30)
        
        return {
            'expected_pct': round(expected_pct, 2),
            'expected_points': round(expected_points, 2),
            'target_price': round(target_price, 2),
            'stop_loss': round(stop_loss, 2),
            'confidence': round(confidence, 1)
        }

    def scan_sector(self, sector: str, max_stocks: int = 100) -> List[Dict]:
        """
        扫描单个板块
        
        Args:
            sector: 板块名称
            max_stocks: 最大扫描数量
        """
        stocks = self.sector_stocks.get(sector, {})
        if not stocks:
            return []
        
        # 限制扫描数量
        stock_items = list(stocks.items())[:max_stocks]
        
        self.logger.info(f"扫描板块: {sector} ({len(stock_items)}只)")
        
        # 批量获取实时数据
        codes = [code for code, _ in stock_items]
        realtime_data = self._get_realtime_batch(codes)
        
        results = []
        for code, name in stock_items:
            if code not in realtime_data:
                continue
            
            # 获取历史数据
            history = self._get_history_data(code)
            
            # 分析股票
            result = self.analyze_stock(code, name, realtime_data[code], history)
            if result:
                result['sector'] = sector
                results.append(result)
        
        # 按评分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        
        return results

    def scan_all_sectors(self, record: bool = True, max_per_sector: int = 0) -> Dict[str, List[Dict]]:
        """
        扫描所有板块
        
        Args:
            record: 是否记录预测结果
            max_per_sector: 每板块最大数量，0表示不限制
        """
        self.logger.info("开始扫描所有板块...")
        
        self._history_cache = {}
        all_results = {}
        
        # 先批量获取所有股票的实时数据
        all_codes = []
        for sector, stocks in self.sector_stocks.items():
            stock_items = list(stocks.items())
            if max_per_sector > 0:
                stock_items = stock_items[:max_per_sector]
            all_codes.extend([code for code, _ in stock_items])
        
        self.logger.info(f"批量获取 {len(all_codes)} 只股票实时数据...")
        all_realtime = self._get_realtime_batch(all_codes)
        self.logger.info(f"获取到 {len(all_realtime)} 只股票数据")
        
        # 第一轮：快速筛选（只用实时数据）
        candidates = []
        for sector, stocks in self.sector_stocks.items():
            stock_items = list(stocks.items())
            if max_per_sector > 0:
                stock_items = stock_items[:max_per_sector]
            
            for code, name in stock_items:
                if code not in all_realtime:
                    continue
                
                realtime = all_realtime[code]
                change_pct = realtime.get('change_pct', 0)
                
                # 快速过滤
                if change_pct < -5:
                    continue
                
                # 快速评分
                quick_score = 50
                if 0 < change_pct < 3:
                    quick_score += 8
                if realtime['price'] > realtime['open'] and change_pct > 0:
                    quick_score += 5
                
                candidates.append({
                    'code': code,
                    'name': name,
                    'sector': sector,
                    'realtime': realtime,
                    'quick_score': quick_score
                })
        
        # 按快速评分排序，只对前500名获取历史数据
        candidates.sort(key=lambda x: x['quick_score'], reverse=True)
        top_candidates = candidates[:500]
        
        self.logger.info(f"快速筛选: {len(top_candidates)} 只股票进入深度分析")
        
        # 第二轮：深度分析（获取历史数据）
        all_stocks = []
        
        for i, candidate in enumerate(top_candidates):
            code = candidate['code']
            name = candidate['name']
            sector = candidate['sector']
            realtime = candidate['realtime']
            
            # 获取历史数据
            history = self._get_history_data(code)
            
            # 深度分析
            result = self.analyze_stock(code, name, realtime, history)
            if result:
                result['sector'] = sector
                all_stocks.append(result)
            
            if (i + 1) % 100 == 0:
                self.logger.info(f"已分析 {i + 1}/{len(top_candidates)} 只")
        
        # 按板块分组
        for stock in all_stocks:
            sector = stock['sector']
            if sector not in all_results:
                all_results[sector] = []
            all_results[sector].append(stock)
        
        # 每个板块内按评分排序
        for sector in all_results:
            all_results[sector].sort(key=lambda x: x['score'], reverse=True)
        
        # 记录预测
        if record:
            predictions = [{
                'code': s['code'],
                'name': s['name'],
                'score': s['score'],
                'strategy_signals': s['strategy_signals']
            } for s in all_stocks]
            self.evaluator.record_prediction(predictions)
        
        total = sum(len(r) for r in all_results.values())
        self.logger.info(f"扫描完成: {len(all_results)} 个板块, {total} 只股票")
        
        return all_results

    def scan_all_stocks(self, min_score: int = 55, max_stocks: int = 1000) -> List[Dict]:
        """
        扫描全A股
        
        Args:
            min_score: 最低评分
            max_stocks: 最大扫描数量
            
        Returns:
            符合条件的股票列表
        """
        self.logger.info(f"开始全A股扫描...")
        
        # 批量获取实时数据
        all_codes = list(self.stock_pool.keys())
        self.logger.info(f"股票总数: {len(all_codes)}")
        
        # 分批获取实时数据
        realtime_data = self._get_realtime_batch(all_codes)
        self.logger.info(f"获取到 {len(realtime_data)} 只股票实时数据")
        
        # 第一轮：快速筛选
        candidates = []
        for code, name in self.stock_pool.items():
            if code not in realtime_data:
                continue
            
            realtime = realtime_data[code]
            change_pct = realtime.get('change_pct', 0)
            
            # 快速过滤：跌幅太大的跳过
            if change_pct < -5:
                continue
            
            # 快速评分
            quick_score = 50
            if 0 < change_pct < 3:
                quick_score += 8
            if realtime['price'] > realtime['open'] and change_pct > 0:
                quick_score += 5
            
            candidates.append({
                'code': code,
                'name': name,
                'realtime': realtime,
                'quick_score': quick_score
            })
        
        # 按快速评分排序，限制数量
        candidates.sort(key=lambda x: x['quick_score'], reverse=True)
        candidates = candidates[:max_stocks]
        
        self.logger.info(f"快速筛选: {len(candidates)} 只股票进入深度分析")
        
        # 第二轮：深度分析
        results = []
        for i, candidate in enumerate(candidates):
            code = candidate['code']
            name = candidate['name']
            realtime = candidate['realtime']
            
            # 获取历史数据
            history = self._get_history_data(code)
            
            # 分析
            result = self.analyze_stock(code, name, realtime, history)
            if result and result['score'] >= min_score:
                results.append(result)
            
            if (i + 1) % 100 == 0:
                self.logger.info(f"已分析 {i + 1}/{len(candidates)} 只")
        
        # 按评分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # 记录预测
        predictions = [{
            'code': s['code'],
            'name': s['name'],
            'score': s['score'],
            'strategy_signals': s['strategy_signals']
        } for s in results]
        self.evaluator.record_prediction(predictions)
        
        self.logger.info(f"扫描完成: {len(results)} 只股票评分 >= {min_score}")
        
        return results
        
        self.logger.info(f"全A股扫描完成: {len(results)} 只股票评分 >= {min_score}")
        
        # 记录预测
        predictions = [{
            'code': s['code'],
            'name': s['name'],
            'score': s['score'],
            'strategy_signals': s['strategy_signals']
        } for s in results[:max_stocks]]
        
        self.evaluator.record_prediction(predictions)
        
        return results[:max_stocks]

    def generate_full_report(self, all_results: Dict[str, List[Dict]], top_per_sector: int = 3) -> str:
        """生成完整报告"""
        total_stocks = sum(len(r) for r in all_results.values())
        
        report = f"""
{'='*60}
🔮 【每日板块扫描报告】{datetime.now().strftime('%Y-%m-%d %H:%M')}
{'='*60}

📊 市场概况：
   扫描板块: {len(all_results)} 个
   扫描股票: {total_stocks} 只

"""
        
        # 每个板块的TOP股票
        for sector, results in all_results.items():
            if not results:
                continue
            
            report += f"""
{'='*50}
📈 {sector}板块 (共{len(results)}只)
{'='*50}
"""
            
            for i, stock in enumerate(results[:top_per_sector], 1):
                expected = stock.get('expected_move', {})
                report += f"""
{i}. {stock['code']} {stock['name']}
   现价: {stock['price']:.2f}  涨跌: {stock['change']:+.2f}%
   评分: {stock['score']:.0f}  信号: {stock['reasons']}
   预期: {expected.get('expected_pct', 0):+.2f}%  目标: {expected.get('target_price', 0):.2f}
"""
        
        # 汇总所有股票，取TOP10
        all_stocks = []
        for results in all_results.values():
            all_stocks.extend(results)
        
        all_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        report += f"""
{'='*60}
🏆 全市场TOP 10
{'='*60}
"""
        
        for i, stock in enumerate(all_stocks[:10], 1):
            expected = stock.get('expected_move', {})
            report += f"""
{i}. [{stock.get('sector', '其他')}] {stock['code']} {stock['name']}
   现价: {stock['price']:.2f}  涨跌: {stock['change']:+.2f}%
   评分: {stock['score']:.0f}  信号: {stock['reasons']}
   预期: {expected.get('expected_pct', 0):+.2f}%
"""
        
        report += f"""
{'='*60}
⚠️ 免责声明
{'='*60}
以上分析仅供参考，不构成投资建议。
投资有风险，入市需谨慎。
"""
        
        return report

    def get_watchlist(self, all_results: Dict[str, List[Dict]], min_score: int = 55) -> List[Dict]:
        """获取监测列表"""
        watchlist = []
        
        for sector, results in all_results.items():
            for stock in results:
                if stock['score'] >= min_score:
                    watchlist.append(stock)
        
        watchlist.sort(key=lambda x: x['score'], reverse=True)
        
        return watchlist

    def update_strategy_weights(self):
        """更新策略权重"""
        self.evaluator.update_weights()

    def get_evaluation_report(self) -> str:
        """获取策略评估报告"""
        return self.evaluator.get_evaluation_report()
