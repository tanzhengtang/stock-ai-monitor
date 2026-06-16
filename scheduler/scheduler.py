"""
定时任务调度器
每日复盘、预测和实时监测
"""

import schedule
import time
import logging
from datetime import datetime
from typing import List, Dict

from .reviewer import StockReviewer
from .predictor import StockPredictor
from .qq_bot import QQBot
from .email_bot import EmailBot


class Scheduler:
    """定时任务调度器
    
    功能：
    1. 每日10:50 复盘昨日推荐股票
    2. 每日15:30 按板块扫描预测
    3. 每日16:00 更新策略权重
    4. 每周日20:00 搜索GitHub策略
    5. 实时监测止损止盈
    """

    def __init__(self, config: Dict = None):
        """
        初始化调度器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.logger = logging.getLogger('Scheduler')
        
        # 初始化组件
        self.reviewer = StockReviewer()
        self.predictor = StockPredictor()
        
        # 推送方式
        self.push_type = self.config.get('push_type', 'email')
        
        if self.push_type == 'qq':
            self.bot = QQBot(
                webhook_url=self.config.get('qq_webhook', '')
            )
        else:
            self.bot = EmailBot(
                smtp_server=self.config.get('smtp_server', ''),
                smtp_port=self.config.get('smtp_port', 465),
                sender_email=self.config.get('sender_email', ''),
                sender_password=self.config.get('sender_password', ''),
                receiver_emails=self.config.get('receiver_emails', [])
            )
        
        # 记录
        self.last_predictions = []
        self.watchlist = []
        
        # 实时监测器
        self.monitor = None

    def setup_schedule(self):
        """设置定时任务"""
        # 每日凌晨2:00 刷新股票池
        schedule.every().day.at("02:00").do(self.refresh_stock_pool)
        
        # 每日10:50 复盘
        schedule.every().day.at("10:50").do(self.morning_review)
        
        # 每日15:30 预测
        schedule.every().day.at("15:30").do(self.afternoon_predict)
        
        # 每日16:00 更新策略权重
        schedule.every().day.at("16:00").do(self.update_strategy_weights)
        
        # 每周日20:00 搜索GitHub策略
        schedule.every().sunday.at("20:00").do(self.search_github_strategies)
        
        self.logger.info("定时任务已设置")
        self.logger.info("  - 02:00 刷新股票池")
        self.logger.info("  - 10:50 早盘复盘")
        self.logger.info("  - 15:30 尾盘预测")
        self.logger.info("  - 16:00 策略权重更新")
        self.logger.info("  - 周日 20:00 GitHub策略搜索")

    def _send_message(self, report_type: str, content: str):
        """发送消息"""
        if self.push_type == 'qq':
            self.bot.send(content)
        else:
            self.bot.send_stock_report(report_type, content)

    def morning_review(self):
        """早盘复盘"""
        self.logger.info("开始早盘复盘...")
        
        try:
            review_result = self.reviewer.review(self.last_predictions)
            report = self.reviewer.generate_report(review_result)
            self._send_message('review', report)
            self.logger.info("早盘复盘完成")
            
        except Exception as e:
            self.logger.error(f"早盘复盘失败: {e}")

    def afternoon_predict(self):
        """尾盘预测（按板块扫描）"""
        self.logger.info("开始尾盘预测...")
        
        try:
            # 按板块扫描
            all_results = self.predictor.scan_all_sectors()
            
            # 保存预测结果
            self.last_predictions = []
            for sector, results in all_results.items():
                for stock in results:
                    self.last_predictions.append(stock)
            
            # 获取监测列表
            self.watchlist = self.predictor.get_watchlist(all_results, min_score=55)
            
            # 生成报告
            report = self.predictor.generate_full_report(all_results, top_per_sector=3)
            
            # 推送
            self._send_message('predict', report)
            
            # 启动实时监测
            if self.watchlist:
                self._start_monitor()
            
            self.logger.info("尾盘预测完成")
            
        except Exception as e:
            self.logger.error(f"尾盘预测失败: {e}")

    def refresh_stock_pool(self):
        """刷新股票池（每日凌晨执行）"""
        self.logger.info("开始刷新股票池...")
        
        try:
            self.predictor.refresh_stock_pool()
            self.logger.info("股票池刷新完成")
            
        except Exception as e:
            self.logger.error(f"股票池刷新失败: {e}")

    def _start_monitor(self):
        """启动实时监测"""
        try:
            from realtime_monitor import RealtimeMonitor
            
            # 停止旧的监测
            if self.monitor and self.monitor.is_running():
                self.monitor.stop()
            
            # 创建新的监测
            self.monitor = RealtimeMonitor()
            
            # 设置回调
            self.monitor.on_stop_loss = self._on_stop_loss
            self.monitor.on_take_profit = self._on_take_profit
            
            # 加载监测列表
            for stock in self.watchlist:
                self.monitor.add_stock(
                    code=stock['code'],
                    name=stock['name'],
                    buy_price=stock['price'],
                    stop_loss_pct=1.0,  # 止损1%
                    take_profit_pct=5.0  # 止盈5%
                )
            
            # 启动监测（每分钟更新）
            self.monitor.start(interval=60)
            
            self.logger.info(f"实时监测已启动: {len(self.watchlist)} 只股票")
            
        except Exception as e:
            self.logger.error(f"启动实时监测失败: {e}")

    def _on_stop_loss(self, trigger: Dict):
        """止损回调"""
        self.logger.warning(f"止损触发: {trigger['message']}")
        
        # 发送邮件
        content = f"""
⚠️ 【止损提醒】

{trigger['message']}

股票代码: {trigger['code']}
股票名称: {trigger['name']}
买入价格: {trigger['buy_price']:.2f}
当前价格: {trigger['current_price']:.2f}
亏损幅度: {trigger['change_pct']:.2f}%
止损阈值: {trigger['threshold']:.1f}%

请及时处理！

⚠️ 以上仅供参考，不构成投资建议
"""
        
        subject = f"⚠️ 止损提醒 - {trigger['name']} ({trigger['code']})"
        self._send_message('stop_loss', content)

    def _on_take_profit(self, trigger: Dict):
        """止盈回调"""
        self.logger.info(f"止盈触发: {trigger['message']}")
        
        # 发送邮件
        content = f"""
✅ 【止盈提醒】

{trigger['message']}

股票代码: {trigger['code']}
股票名称: {trigger['name']}
买入价格: {trigger['buy_price']:.2f}
当前价格: {trigger['current_price']:.2f}
盈利幅度: {trigger['change_pct']:.2f}%
止盈阈值: +{trigger['threshold']:.1f}%

可以考虑止盈！

⚠️ 以上仅供参考，不构成投资建议
"""
        
        subject = f"✅ 止盈提醒 - {trigger['name']} ({trigger['code']})"
        self._send_message('take_profit', content)

    def update_strategy_weights(self):
        """更新策略权重"""
        self.logger.info("开始更新策略权重...")
        
        try:
            self.predictor.update_strategy_weights()
            report = self.predictor.get_evaluation_report()
            self._send_message('strategy_report', report)
            self.logger.info("策略权重更新完成")
            
        except Exception as e:
            self.logger.error(f"策略权重更新失败: {e}")

    def search_github_strategies(self):
        """搜索GitHub策略（每周执行）"""
        self.logger.info("开始搜索GitHub策略...")
        
        try:
            from github_strategy_searcher import GitHubStrategySearcher
            
            searcher = GitHubStrategySearcher()
            strategies = searcher.search_strategies()
            report = searcher.get_strategy_report()
            self._send_message('github_strategies', report)
            
            self.logger.info(f"GitHub策略搜索完成，找到 {len(strategies)} 个策略")
            
        except Exception as e:
            self.logger.error(f"GitHub策略搜索失败: {e}")

    def run(self):
        """运行调度器"""
        self.setup_schedule()
        
        self.logger.info("调度器已启动，等待任务...")
        
        while True:
            schedule.run_pending()
            time.sleep(60)


# 测试代码
if __name__ == '__main__':
    scheduler = Scheduler()
    
    # 测试复盘
    print("测试早盘复盘...")
    scheduler.last_predictions = [
        {'code': '600519', 'name': '贵州茅台'},
        {'code': '601318', 'name': '中国平安'}
    ]
    scheduler.morning_review()
    
    # 测试预测
    print("\n测试尾盘预测...")
    scheduler.afternoon_predict()
