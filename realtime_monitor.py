"""
实时行情监测模块
监测股票价格，到达止损止盈位时发送提醒
"""

import time
import requests
import logging
from datetime import datetime
from typing import List, Dict, Callable, Optional
from threading import Thread, Event
import json
from pathlib import Path


class RealtimeMonitor:
    """实时行情监测器
    
    功能：
    1. 实时监测股票价格
    2. 到达止损位/止盈位时触发回调
    3. 支持多只股票同时监测
    """

    def __init__(self, data_dir: str = None):
        self.logger = logging.getLogger('RealtimeMonitor')
        self.data_dir = Path(data_dir or 'data')
        self.data_dir.mkdir(exist_ok=True)
        
        # 监测列表
        self.watchlist: List[Dict] = []
        
        # 回调函数
        self.on_stop_loss: Optional[Callable] = None
        self.on_take_profit: Optional[Callable] = None
        self.on_price_update: Optional[Callable] = None
        
        # 控制标志
        self._stop_event = Event()
        self._monitor_thread: Optional[Thread] = None
        
        # 价格缓存
        self._last_prices: Dict[str, float] = {}

    def load_watchlist(self, watchlist: List[Dict]):
        """
        加载监测列表
        
        Args:
            watchlist: 监测列表，每个元素包含:
                - code: 股票代码
                - name: 股票名称
                - buy_price: 买入价格
                - stop_loss_pct: 止损百分比 (默认1.0%)
                - take_profit_pct: 止盈百分比 (默认5.0%)
        """
        self.watchlist = []
        
        for item in watchlist:
            self.watchlist.append({
                'code': item['code'],
                'name': item['name'],
                'buy_price': item.get('buy_price', 0),
                'stop_loss_pct': item.get('stop_loss_pct', 1.0),
                'take_profit_pct': item.get('take_profit_pct', 5.0),
                'current_price': 0,
                'change_pct': 0,
                'triggered': False
            })
        
        self.logger.info(f"加载监测列表: {len(self.watchlist)} 只股票")

    def add_stock(self, code: str, name: str, buy_price: float, 
                  stop_loss_pct: float = 1.0, take_profit_pct: float = 5.0):
        """
        添加监测股票
        
        Args:
            code: 股票代码
            name: 股票名称
            buy_price: 买入价格
            stop_loss_pct: 止损百分比
            take_profit_pct: 止盈百分比
        """
        # 检查是否已存在
        for item in self.watchlist:
            if item['code'] == code:
                # 更新
                item['buy_price'] = buy_price
                item['stop_loss_pct'] = stop_loss_pct
                item['take_profit_pct'] = take_profit_pct
                item['triggered'] = False
                self.logger.info(f"更新监测股票: {code} {name}")
                return
        
        # 新增
        self.watchlist.append({
            'code': code,
            'name': name,
            'buy_price': buy_price,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'current_price': 0,
            'change_pct': 0,
            'triggered': False
        })
        
        self.logger.info(f"添加监测股票: {code} {name}")

    def remove_stock(self, code: str):
        """移除监测股票"""
        self.watchlist = [item for item in self.watchlist if item['code'] != code]
        self.logger.info(f"移除监测股票: {code}")

    def get_realtime_prices(self) -> Dict[str, Dict]:
        """
        获取实时价格
        
        Returns:
            {code: {price, change_pct, ...}}
        """
        if not self.watchlist:
            return {}
        
        # 构建请求代码
        codes = []
        for item in self.watchlist:
            code = item['code']
            if code.startswith('6'):
                codes.append(f'sh{code}')
            else:
                codes.append(f'sz{code}')
        
        codes_str = ','.join(codes)
        url = f'http://hq.sinajs.cn/list={codes_str}'
        headers = {'Referer': 'https://finance.sina.com.cn'}
        
        results = {}
        
        try:
            resp = requests.get(url, headers=headers, timeout=5)
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
                        
                        change_pct = (current - prev_close) / prev_close * 100 if prev_close > 0 else 0
                        
                        results[code] = {
                            'name': name,
                            'price': current,
                            'prev_close': prev_close,
                            'high': high,
                            'low': low,
                            'change_pct': change_pct
                        }
                except:
                    continue
                    
        except Exception as e:
            self.logger.error(f"获取实时价格失败: {e}")
        
        return results

    def check_triggers(self, prices: Dict[str, Dict]) -> List[Dict]:
        """
        检查触发条件
        
        Args:
            prices: 实时价格
            
        Returns:
            触发列表
        """
        triggers = []
        
        for item in self.watchlist:
            code = item['code']
            
            if code not in prices:
                continue
            
            price_data = prices[code]
            current_price = price_data['price']
            
            if current_price <= 0:
                continue
            
            # 更新当前价格
            item['current_price'] = current_price
            
            # 计算相对于买入价的涨跌幅
            buy_price = item['buy_price']
            if buy_price <= 0:
                continue
            
            change_from_buy = (current_price - buy_price) / buy_price * 100
            
            # 检查是否已触发
            if item['triggered']:
                continue
            
            # 检查止损
            if change_from_buy <= -item['stop_loss_pct']:
                item['triggered'] = True
                triggers.append({
                    'type': 'stop_loss',
                    'code': code,
                    'name': item['name'],
                    'buy_price': buy_price,
                    'current_price': current_price,
                    'change_pct': change_from_buy,
                    'threshold': -item['stop_loss_pct'],
                    'message': f"⚠️ 止损提醒: {item['name']}({code}) 已触及止损位"
                })
            
            # 检查止盈
            elif change_from_buy >= item['take_profit_pct']:
                item['triggered'] = True
                triggers.append({
                    'type': 'take_profit',
                    'code': code,
                    'name': item['name'],
                    'buy_price': buy_price,
                    'current_price': current_price,
                    'change_pct': change_from_buy,
                    'threshold': item['take_profit_pct'],
                    'message': f"✅ 止盈提醒: {item['name']}({code}) 已触及止盈位"
                })
        
        return triggers

    def _monitor_loop(self, interval: int = 60):
        """
        监测循环
        
        Args:
            interval: 更新间隔（秒）
        """
        self.logger.info(f"开始实时监测，间隔 {interval} 秒")
        
        while not self._stop_event.is_set():
            try:
                # 获取实时价格
                prices = self.get_realtime_prices()
                
                # 更新价格
                for item in self.watchlist:
                    code = item['code']
                    if code in prices:
                        item['current_price'] = prices[code]['price']
                        item['change_pct'] = prices[code]['change_pct']
                
                # 价格更新回调
                if self.on_price_update:
                    self.on_price_update(self.watchlist)
                
                # 检查触发条件
                triggers = self.check_triggers(prices)
                
                # 触发回调
                for trigger in triggers:
                    if trigger['type'] == 'stop_loss' and self.on_stop_loss:
                        self.on_stop_loss(trigger)
                    elif trigger['type'] == 'take_profit' and self.on_take_profit:
                        self.on_take_profit(trigger)
                
                # 保存状态
                self._save_state()
                
            except Exception as e:
                self.logger.error(f"监测异常: {e}")
            
            # 等待
            self._stop_event.wait(interval)
        
        self.logger.info("实时监测已停止")

    def start(self, interval: int = 60):
        """
        启动监测
        
        Args:
            interval: 更新间隔（秒）
        """
        if self._monitor_thread and self._monitor_thread.is_alive():
            self.logger.warning("监测已在运行")
            return
        
        self._stop_event.clear()
        self._monitor_thread = Thread(target=self._monitor_loop, args=(interval,))
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        
        self.logger.info("实时监测已启动")

    def stop(self):
        """停止监测"""
        self._stop_event.set()
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        self.logger.info("实时监测已停止")

    def is_running(self) -> bool:
        """是否正在运行"""
        return self._monitor_thread is not None and self._monitor_thread.is_alive()

    def _save_state(self):
        """保存状态"""
        try:
            state_file = self.data_dir / 'monitor_state.json'
            state = {
                'timestamp': datetime.now().isoformat(),
                'watchlist': self.watchlist
            }
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass

    def get_status(self) -> Dict:
        """获取监测状态"""
        return {
            'is_running': self.is_running(),
            'watchlist_count': len(self.watchlist),
            'triggered_count': sum(1 for item in self.watchlist if item['triggered']),
            'watchlist': self.watchlist
        }

    def format_status(self) -> str:
        """格式化状态"""
        status = self.get_status()
        
        report = f"""
📊 【实时监测状态】

运行状态: {'✅ 运行中' if status['is_running'] else '❌ 已停止'}
监测股票: {status['watchlist_count']} 只
已触发: {status['triggered_count']} 只

{'='*50}
📋 监测列表
{'='*50}
"""
        
        for item in status['watchlist']:
            icon = '🔴' if item['triggered'] else '🟢'
            report += f"""
{icon} {item['code']} {item['name']}
   买入价: {item['buy_price']:.2f}
   现价: {item['current_price']:.2f}
   盈亏: {item['change_pct']:+.2f}%
   止损位: -{item['stop_loss_pct']:.1f}%  止盈位: +{item['take_profit_pct']:.1f}%
"""
        
        return report


# 测试代码
if __name__ == '__main__':
    monitor = RealtimeMonitor()
    
    # 添加监测股票
    monitor.add_stock('600519', '贵州茅台', 1800.0, 1.0, 5.0)
    monitor.add_stock('601318', '中国平安', 50.0, 1.0, 5.0)
    
    print(monitor.format_status())
    
    # 测试获取价格
    prices = monitor.get_realtime_prices()
    print("\n实时价格:")
    for code, data in prices.items():
        print(f"  {code}: {data['price']:.2f}")
