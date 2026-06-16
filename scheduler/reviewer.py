"""
股票复盘模块
对预测结果进行复盘分析，包含回测功能
"""

import requests
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import json


class StockReviewer:
    """股票复盘器
    
    功能：
    1. 获取预测股票的实时行情
    2. 获取历史数据进行回测分析
    3. 评估策略有效性
    4. 生成深度复盘报告
    """

    def __init__(self, data_dir: str = None):
        self.logger = logging.getLogger('StockReviewer')
        self.data_dir = Path(data_dir or 'data')
        self.data_dir.mkdir(exist_ok=True)

    def get_realtime_quotes(self, stock_codes: List[str]) -> Dict:
        """
        获取实时行情
        """
        results = {}
        
        sina_codes = []
        for code in stock_codes:
            if code.startswith('6'):
                sina_codes.append(f'sh{code}')
            else:
                sina_codes.append(f'sz{code}')
        
        codes_str = ','.join(sina_codes)
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
                        prev_close = float(data[2]) if data[2] else 0
                        current = float(data[3]) if data[3] else 0
                        high = float(data[4]) if data[4] else 0
                        low = float(data[5]) if data[5] else 0
                        
                        if prev_close > 0:
                            change_pct = (current - prev_close) / prev_close * 100
                        else:
                            change_pct = 0
                        
                        results[code] = {
                            'name': name,
                            'price': current,
                            'prev_close': prev_close,
                            'high': high,
                            'low': low,
                            'change_pct': change_pct
                        }
                except Exception as e:
                    continue
                    
        except Exception as e:
            self.logger.error(f"获取行情失败: {e}")
        
        return results

    def get_history_data(self, stock_code: str, days: int = 60) -> Optional[List[Dict]]:
        """
        获取历史数据（使用新浪财经）
        """
        try:
            # 转换代码格式
            if stock_code.startswith('6'):
                sina_code = f'sh{stock_code}'
            else:
                sina_code = f'sz{stock_code}'
            
            # 使用新浪财经获取历史数据
            url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sina_code}&scale=240&ma=no&datalen={days}'
            
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                # 解析返回的JSON数据
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
                
                return history
            
            return None
            
        except Exception as e:
            self.logger.warning(f"获取历史数据失败 {stock_code}: {e}")
            return None

    def calculate_technical_indicators(self, history: List[Dict]) -> Dict:
        """
        计算技术指标
        """
        if not history or len(history) < 20:
            return {}
        
        closes = [h['close'] for h in history]
        volumes = [h['volume'] for h in history]
        
        # 均线
        ma5 = np.mean(closes[-5:])
        ma10 = np.mean(closes[-10:])
        ma20 = np.mean(closes[-20:])
        
        # RSI
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
        else:
            rsi = 50
        
        # 涨跌幅统计
        changes = np.diff(closes) / closes[:-1] * 100
        avg_change = np.mean(changes)
        volatility = np.std(changes)
        
        # 胜率（上涨天数占比）
        win_rate = np.sum(changes > 0) / len(changes) * 100
        
        # 最大回撤
        peak = closes[0]
        max_drawdown = 0
        for c in closes:
            if c > peak:
                peak = c
            drawdown = (peak - c) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return {
            'ma5': ma5,
            'ma10': ma10,
            'ma20': ma20,
            'rsi': rsi,
            'avg_change': avg_change,
            'volatility': volatility,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'period_return': (closes[-1] - closes[0]) / closes[0] * 100
        }

    def backtest_ma_strategy(self, history: List[Dict], short_window: int = 5, long_window: int = 20) -> Dict:
        """
        回测均线策略
        """
        if not history or len(history) < long_window:
            return {'success': False, 'message': '数据不足'}
        
        closes = [h['close'] for h in history]
        
        # 计算均线
        signals = []
        for i in range(long_window, len(closes)):
            ma_short = np.mean(closes[i-short_window:i])
            ma_long = np.mean(closes[i-long_window:i])
            
            if ma_short > ma_long:
                signals.append('buy')
            else:
                signals.append('sell')
        
        # 模拟交易
        initial_capital = 100000
        capital = initial_capital
        position = 0
        trades = []
        
        for i, signal in enumerate(signals):
            idx = i + long_window
            price = closes[idx]
            
            if signal == 'buy' and position == 0:
                # 买入
                shares = int(capital * 0.9 / price / 100) * 100
                if shares > 0:
                    cost = shares * price
                    capital -= cost
                    position = shares
                    trades.append({
                        'date': history[idx]['date'],
                        'action': 'buy',
                        'price': price,
                        'shares': shares
                    })
            
            elif signal == 'sell' and position > 0:
                # 卖出
                revenue = position * price
                capital += revenue
                trades.append({
                    'date': history[idx]['date'],
                    'action': 'sell',
                    'price': price,
                    'shares': position
                })
                position = 0
        
        # 最终资产
        final_value = capital + position * closes[-1]
        total_return = (final_value - initial_capital) / initial_capital * 100
        
        # 计算胜率
        winning_trades = 0
        total_trades = len([t for t in trades if t['action'] == 'sell'])
        
        # 简化计算：统计盈利交易
        buy_price = 0
        for trade in trades:
            if trade['action'] == 'buy':
                buy_price = trade['price']
            elif trade['action'] == 'sell' and buy_price > 0:
                if trade['price'] > buy_price:
                    winning_trades += 1
        
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        return {
            'success': True,
            'strategy': f'MA{short_window}_{long_window}',
            'initial_capital': initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'trades': trades[-5:]  # 最近5笔交易
        }

    def review(self, predictions: List[Dict], buy_prices: Dict = None) -> Dict:
        """
        复盘预测结果（带回测分析）
        
        Args:
            predictions: 预测的股票列表
            buy_prices: 买入价格 {'code': price}
        """
        if not predictions:
            return {
                'stocks': [],
                'win_rate': 0,
                'avg_change': 0,
                'total': 0
            }
        
        stock_codes = [p['code'] for p in predictions]
        
        # 获取实时行情
        quotes = self.get_realtime_quotes(stock_codes)
        
        # 生成复盘结果
        stocks = []
        for pred in predictions:
            code = pred['code']
            quote = quotes.get(code, {})
            
            change_pct = quote.get('change_pct', 0)
            
            # 获取历史数据进行回测
            history = self.get_history_data(code, days=60)
            
            # 计算技术指标
            tech_indicators = {}
            backtest_result = {}
            
            if history:
                tech_indicators = self.calculate_technical_indicators(history)
                backtest_result = self.backtest_ma_strategy(history)
            
            # 计算持仓盈亏
            buy_price = buy_prices.get(code) if buy_prices else None
            pnl_pct = None
            if buy_price and quote.get('price'):
                pnl_pct = (quote['price'] - buy_price) / buy_price * 100
            
            stocks.append({
                'code': code,
                'name': quote.get('name', pred.get('name', '')),
                'price': quote.get('price', 0),
                'change': change_pct,
                'pnl_pct': pnl_pct,
                'buy_price': buy_price,
                'is_win': change_pct > 0,
                'tech_indicators': tech_indicators,
                'backtest': backtest_result
            })
        
        # 计算统计
        win_count = sum(1 for s in stocks if s['is_win'])
        total = len(stocks)
        win_rate = win_count / total * 100 if total > 0 else 0
        avg_change = sum(s['change'] for s in stocks) / total if total > 0 else 0
        
        return {
            'stocks': stocks,
            'win_rate': win_rate,
            'avg_change': avg_change,
            'win_count': win_count,
            'total': total,
            'review_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def generate_report(self, review_result: Dict) -> str:
        """
        生成深度复盘报告
        """
        report = f"""
📊 【深度复盘报告】{datetime.now().strftime('%Y-%m-%d')}

{'='*50}

一、持仓股票表现
"""
        
        for stock in review_result['stocks']:
            icon = '📈' if stock['change'] > 0 else '📉' if stock['change'] < 0 else '➡️'
            
            report += f"""
{icon} {stock['name']} ({stock['code']})
   当前价: {stock['price']:.2f}
   今日涨跌: {stock['change']:+.2f}%"""
            
            if stock['buy_price']:
                report += f"""
   买入价: {stock['buy_price']:.2f}
   持仓盈亏: {stock['pnl_pct']:+.2f}%"""
            
            # 技术指标
            tech = stock.get('tech_indicators', {})
            if tech:
                report += f"""

   【技术指标】
   MA5: {tech.get('ma5', 0):.2f} | MA10: {tech.get('ma10', 0):.2f} | MA20: {tech.get('ma20', 0):.2f}
   RSI: {tech.get('rsi', 0):.1f}
   60日收益: {tech.get('period_return', 0):+.2f}%
   最大回撤: {tech.get('max_drawdown', 0):.2f}%
   历史胜率: {tech.get('win_rate', 0):.1f}%"""
            
            # 回测结果
            bt = stock.get('backtest', {})
            if bt.get('success'):
                report += f"""

   【回测分析】
   策略: {bt.get('strategy', 'N/A')}
   回测收益: {bt.get('total_return', 0):+.2f}%
   交易次数: {bt.get('total_trades', 0)}
   策略胜率: {bt.get('win_rate', 0):.1f}%"""
            
            report += "\n"
        
        # 总结
        report += f"""
{'='*50}

二、整体统计

   推荐股票数: {review_result['total']}
   今日胜率: {review_result['win_rate']:.1f}% ({review_result['win_count']}/{review_result['total']})
   平均涨跌: {review_result['avg_change']:+.2f}%

{'='*50}

三、后续建议

"""
        
        # 根据结果给出建议
        if review_result['win_rate'] >= 60:
            report += "✅ 今日表现良好，可继续关注相关策略\n"
        elif review_result['win_rate'] >= 40:
            report += "⚠️ 表现一般，建议观望为主\n"
        else:
            report += "❌ 表现不佳，建议控制仓位\n"
        
        report += """
   1. 设好止损位（建议-5%）
   2. 不要追涨杀跌
   3. 关注大盘走势

⚠️ 以上仅供参考，不构成投资建议
投资有风险，入市需谨慎
"""
        
        return report


# 测试代码
if __name__ == '__main__':
    reviewer = StockReviewer()
    
    # 测试复盘
    test_predictions = [
        {'code': '601238', 'name': '广汽集团'},
        {'code': '002230', 'name': '科大讯飞'}
    ]
    
    test_buy_prices = {
        '601238': 5.90,
        '002230': 41.50
    }
    
    result = reviewer.review(test_predictions, test_buy_prices)
    report = reviewer.generate_report(result)
    print(report)
