"""
策略评估器
根据历史预测结果评估和调整策略权重
"""

import json
import numpy as np
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from collections import defaultdict


class StrategyEvaluator:
    """策略评估器
    
    功能：
    1. 记录每次预测结果
    2. 统计各策略的历史胜率
    3. 动态调整策略权重
    4. 生成策略评估报告
    """

    def __init__(self, data_dir: str = None):
        self.logger = logging.getLogger('StrategyEvaluator')
        self.data_dir = Path(data_dir or 'data')
        self.data_dir.mkdir(exist_ok=True)
        
        # 历史记录文件
        self.history_file = self.data_dir / 'prediction_history.json'
        self.weights_file = self.data_dir / 'strategy_weights.json'
        
        # 策略列表（必须在加载权重之前定义）
        self.strategies = [
            'ma_cross',       # 均线交叉
            'rsi_reversal',   # RSI反转
            'macd_signal',    # MACD信号
            'kdj_signal',     # KDJ信号
            'bollinger_band', # 布林带
            'momentum',       # 动量
            'volume_price',   # 量价关系
            'fundamental',    # 基本面 (PE/PB/ROE/增长)
        ]
        
        # 加载历史数据
        self.history = self._load_history()
        self.strategy_weights = self._load_weights()

    def _load_history(self) -> List[Dict]:
        """加载历史记录"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"加载历史记录失败: {e}")
        return []

    def _save_history(self):
        """保存历史记录"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存历史记录失败: {e}")

    def _load_weights(self) -> Dict[str, float]:
        """加载策略权重"""
        default_weights = {s: 1.0 / len(self.strategies) for s in self.strategies}
        
        if self.weights_file.exists():
            try:
                with open(self.weights_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"加载权重失败: {e}")
        
        return default_weights

    def _save_weights(self):
        """保存策略权重"""
        try:
            with open(self.weights_file, 'w', encoding='utf-8') as f:
                json.dump(self.strategy_weights, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存权重失败: {e}")

    def record_prediction(self, predictions: List[Dict]):
        """
        记录预测结果
        
        Args:
            predictions: 预测列表，每个包含:
                - code: 股票代码
                - name: 股票名称
                - score: 综合评分
                - strategy_signals: 各策略信号 {'ma_cross': 'buy', ...}
                - predict_date: 预测日期
        """
        record = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat(),
            'predictions': predictions
        }
        
        self.history.append(record)
        
        # 只保留最近90天的记录
        cutoff_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        self.history = [h for h in self.history if h['date'] >= cutoff_date]
        
        self._save_history()
        self.logger.info(f"记录预测结果: {len(predictions)} 只股票")

    def record_actual_result(self, date: str, results: Dict[str, Dict]):
        """
        记录实际结果
        
        Args:
            date: 预测日期
            results: 实际结果 {code: {'change': 涨跌幅, 'is_win': bool}}
        """
        for record in self.history:
            if record['date'] == date:
                for pred in record['predictions']:
                    code = pred['code']
                    if code in results:
                        pred['actual_change'] = results[code]['change']
                        pred['is_win'] = results[code]['is_win']
                
                self._save_history()
                self.logger.info(f"更新实际结果: {date}")
                break

    def evaluate_strategies(self, days: int = 30) -> Dict[str, Dict]:
        """
        评估各策略的历史表现
        
        Args:
            days: 评估天数
            
        Returns:
            各策略的评估结果
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        recent_history = [h for h in self.history if h['date'] >= cutoff_date]
        
        if not recent_history:
            return {}
        
        # 统计各策略的表现
        strategy_stats = defaultdict(lambda: {
            'total': 0,
            'wins': 0,
            'losses': 0,
            'total_return': 0,
            'returns': []
        })
        
        for record in recent_history:
            for pred in record['predictions']:
                if 'actual_change' not in pred:
                    continue
                
                actual_change = pred['actual_change']
                is_win = pred.get('is_win', actual_change > 0)
                
                # 遍历各策略信号
                strategy_signals = pred.get('strategy_signals', {})
                for strategy, signal in strategy_signals.items():
                    stats = strategy_stats[strategy]
                    stats['total'] += 1
                    
                    # 如果策略信号与实际结果一致
                    if (signal == 'buy' and is_win) or (signal == 'sell' and not is_win):
                        stats['wins'] += 1
                    else:
                        stats['losses'] += 1
                    
                    stats['returns'].append(actual_change)
                    stats['total_return'] += actual_change
        
        # 计算评估指标
        results = {}
        for strategy, stats in strategy_stats.items():
            if stats['total'] > 0:
                win_rate = stats['wins'] / stats['total'] * 100
                avg_return = np.mean(stats['returns']) if stats['returns'] else 0
                sharpe = self._calculate_sharpe(stats['returns']) if stats['returns'] else 0
                
                results[strategy] = {
                    'total': stats['total'],
                    'wins': stats['wins'],
                    'losses': stats['losses'],
                    'win_rate': win_rate,
                    'avg_return': avg_return,
                    'total_return': stats['total_return'],
                    'sharpe': sharpe,
                    'score': win_rate * 0.5 + (avg_return + 10) * 2.5 + sharpe * 10  # 综合评分
                }
        
        return results

    def _calculate_sharpe(self, returns: List[float], risk_free_rate: float = 0.03) -> float:
        """计算夏普比率"""
        if not returns or len(returns) < 2:
            return 0
        
        returns_array = np.array(returns) / 100
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        if std_return == 0:
            return 0
        
        # 年化夏普比率
        daily_rf = risk_free_rate / 252
        sharpe = (mean_return - daily_rf) / std_return * np.sqrt(252)
        
        return sharpe

    def update_weights(self, min_samples: int = 10):
        """
        根据历史表现更新策略权重
        
        Args:
            min_samples: 最小样本数
        """
        evaluation = self.evaluate_strategies(days=30)
        
        if not evaluation:
            self.logger.warning("没有足够的历史数据来更新权重")
            return
        
        # 计算新权重
        total_score = 0
        new_weights = {}
        
        for strategy in self.strategies:
            if strategy in evaluation and evaluation[strategy]['total'] >= min_samples:
                score = evaluation[strategy]['score']
                new_weights[strategy] = max(score, 10)  # 最低权重10
                total_score += new_weights[strategy]
            else:
                new_weights[strategy] = 50  # 默认权重
                total_score += 50
        
        # 归一化权重
        if total_score > 0:
            for strategy in new_weights:
                new_weights[strategy] = new_weights[strategy] / total_score
        
        # 平滑更新（避免权重剧烈变化）
        smooth_factor = 0.3
        for strategy in self.strategies:
            old_weight = self.strategy_weights.get(strategy, 0.5)
            new_weight = new_weights.get(strategy, 0.5)
            self.strategy_weights[strategy] = old_weight * (1 - smooth_factor) + new_weight * smooth_factor
        
        self._save_weights()
        self.logger.info(f"策略权重已更新: {self.strategy_weights}")

    def calculate_expected_move(self, stock_data: Dict, strategy_signals: Dict) -> Dict:
        """
        计算预期上涨点数和幅度
        
        Args:
            stock_data: 股票数据 {'price': 现价, 'high': 最高, 'low': 最低, ...}
            strategy_signals: 策略信号
            
        Returns:
            {
                'expected_pct': 预期涨幅百分比,
                'expected_points': 预期上涨点数,
                'target_price': 目标价,
                'stop_loss': 止损价,
                'confidence': 置信度
            }
        """
        current_price = stock_data.get('price', 0)
        if current_price <= 0:
            return {
                'expected_pct': 0,
                'expected_points': 0,
                'target_price': 0,
                'stop_loss': 0,
                'confidence': 0
            }
        
        # 基础预期
        base_expected = 2.0  # 基础预期2%
        
        # 根据策略信号调整
        signal_boost = 0
        buy_count = 0
        sell_count = 0
        
        for strategy, signal in strategy_signals.items():
            weight = self.strategy_weights.get(strategy, 0.5)
            if signal in ['buy', 'strong_buy']:
                buy_count += 1
                signal_boost += 1.5 * weight
            elif signal in ['sell', 'strong_sell']:
                sell_count += 1
                signal_boost -= 1.5 * weight
        
        # 根据RSI调整
        rsi = stock_data.get('rsi', 50)
        if rsi < 30:
            signal_boost += 1.0  # RSI超卖，反弹预期更高
        elif rsi > 70:
            signal_boost -= 0.5  # RSI超买，上涨空间有限
        
        # 根据波动率调整
        volatility = stock_data.get('volatility', 2.0)
        volatility_factor = volatility / 2.0  # 标准化
        
        # 计算预期
        expected_pct = (base_expected + signal_boost) * volatility_factor
        expected_pct = max(min(expected_pct, 10), -5)  # 限制在-5%到10%
        
        expected_points = current_price * expected_pct / 100
        target_price = current_price * (1 + expected_pct / 100)
        stop_loss = current_price * 0.95  # 止损5%
        
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

    def get_weighted_score(self, strategy_signals: Dict[str, str]) -> float:
        """
        根据策略权重计算加权评分
        
        Args:
            strategy_signals: 各策略信号 {'ma_cross': 'buy', 'rsi': 'sell', ...}
            
        Returns:
            加权评分 (0-100)
        """
        score = 50  # 基础分
        
        for strategy, signal in strategy_signals.items():
            weight = self.strategy_weights.get(strategy, 0.5)
            
            if signal == 'buy':
                score += 10 * weight
            elif signal == 'strong_buy':
                score += 20 * weight
            elif signal == 'sell':
                score -= 10 * weight
            elif signal == 'strong_sell':
                score -= 20 * weight
        
        return min(max(score, 0), 100)

    def get_evaluation_report(self) -> str:
        """
        生成策略评估报告
        """
        evaluation = self.evaluate_strategies(days=30)
        
        if not evaluation:
            return "暂无足够数据生成评估报告"
        
        report = f"""
📊 【策略评估报告】
评估周期: 最近30天
评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

{'='*50}

各策略表现：
"""
        
        # 按综合评分排序
        sorted_strategies = sorted(
            evaluation.items(),
            key=lambda x: x[1].get('score', 0),
            reverse=True
        )
        
        for strategy, stats in sorted_strategies:
            weight = self.strategy_weights.get(strategy, 0)
            report += f"""
📌 {strategy}
   胜率: {stats['win_rate']:.1f}% ({stats['wins']}/{stats['total']})
   平均收益: {stats['avg_return']:.2f}%
   夏普比率: {stats['sharpe']:.2f}
   当前权重: {weight:.2f}
"""
        
        report += f"""
{'='*50}

当前策略权重：
"""
        for strategy, weight in sorted(self.strategy_weights.items(), key=lambda x: x[1], reverse=True):
            bar = '█' * int(weight * 20)
            report += f"  {strategy:<15} {weight:.2f} {bar}\n"
        
        return report


# 测试代码
if __name__ == '__main__':
    evaluator = StrategyEvaluator()
    
    # 模拟记录
    test_predictions = [
        {
            'code': '600519',
            'name': '贵州茅台',
            'score': 70,
            'strategy_signals': {
                'ma_cross': 'buy',
                'rsi_reversal': 'neutral',
                'macd_signal': 'buy'
            }
        }
    ]
    
    evaluator.record_prediction(test_predictions)
    print(evaluator.get_evaluation_report())
