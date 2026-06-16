"""
AI信号监控系统主程序
"""

import os
import sys
import time
import logging
import signal
import yaml
from datetime import datetime
from typing import List, Dict

from signal_aggregator import SignalAggregator, PlatformSignal
from scrapers import EastMoneyScraper, TongHuaShunScraper, AKShareScraper, BaoStockScraper
from notifiers import ConsoleNotifier, DingTalkNotifier, EmailNotifier


class StockMonitor:
    """股票监控系统"""
    
    def __init__(self, config_path: str = None):
        """
        初始化监控系统
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = self._load_config(config_path)
        
        # 设置日志
        self._setup_logging()
        
        # 初始化组件
        self.aggregator = SignalAggregator()
        self.notifiers = self._init_notifiers()
        self.scrapers = self._init_scrapers()
        
        # 监控股票列表
        self.watchlist = self.config.get('watchlist', [])
        
        # 运行状态
        self.running = False
        
        self.logger.info("股票监控系统初始化完成")

    def _load_config(self, config_path: str = None) -> Dict:
        """加载配置文件"""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml')
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        
        return {}

    def _setup_logging(self):
        """设置日志"""
        log_level = logging.DEBUG if self.config.get('app', {}).get('debug', False) else logging.INFO
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('stock_monitor.log', encoding='utf-8')
            ]
        )
        
        self.logger = logging.getLogger('StockMonitor')

    def _init_notifiers(self) -> List:
        """初始化通知器"""
        notifiers = []
        
        notification_config = self.config.get('notification', {})
        
        # 控制台通知器
        if notification_config.get('console', {}).get('enabled', True):
            notifiers.append(ConsoleNotifier())
        
        # 钉钉通知器
        dingtalk_config = notification_config.get('dingtalk', {})
        if dingtalk_config.get('enabled', False) and dingtalk_config.get('webhook_url'):
            notifiers.append(DingTalkNotifier(
                webhook_url=dingtalk_config['webhook_url'],
                secret=dingtalk_config.get('secret')
            ))
        
        # 邮件通知器
        email_config = notification_config.get('email', {})
        if email_config.get('enabled', False) and email_config.get('sender_email'):
            notifiers.append(EmailNotifier(
                smtp_server=email_config.get('smtp_server', 'smtp.gmail.com'),
                smtp_port=email_config.get('smtp_port', 465),
                sender_email=email_config['sender_email'],
                sender_password=email_config['sender_password'],
                receiver_emails=email_config.get('receiver_emails', [])
            ))
        
        return notifiers

    def _init_scrapers(self) -> List:
        """初始化爬虫"""
        scrapers = []
        
        # 东方财富爬虫
        try:
            scrapers.append(EastMoneyScraper())
        except Exception as e:
            self.logger.warning(f"东方财富爬虫初始化失败: {e}")
        
        # 同花顺爬虫
        try:
            scrapers.append(TongHuaShunScraper())
        except Exception as e:
            self.logger.warning(f"同花顺爬虫初始化失败: {e}")
        
        # AKShare爬虫
        try:
            scrapers.append(AKShareScraper())
        except Exception as e:
            self.logger.warning(f"AKShare爬虫初始化失败: {e}")
        
        # BaoStock爬虫
        try:
            scrapers.append(BaoStockScraper())
        except Exception as e:
            self.logger.warning(f"BaoStock爬虫初始化失败: {e}")
        
        return scrapers

    def scan_stocks(self, stock_codes: List[str] = None):
        """
        扫描股票
        
        Args:
            stock_codes: 股票代码列表，如果为None则扫描所有监控股票
        """
        if stock_codes is None:
            stock_codes = [item['code'] for item in self.watchlist]
        
        self.logger.info(f"开始扫描 {len(stock_codes)} 只股票")
        
        # 清除旧信号
        self.aggregator.clear_signals()
        
        # 遍历股票和爬虫
        for stock_code in stock_codes:
            for scraper in self.scrapers:
                try:
                    signal = scraper.get_stock_signal(stock_code)
                    if signal:
                        self.aggregator.add_signal(signal)
                        self.logger.debug(f"获取到信号: {stock_code} - {scraper.platform.value}")
                except Exception as e:
                    self.logger.warning(f"获取信号失败: {stock_code} - {scraper.platform.value} - {e}")
        
        self.logger.info(f"扫描完成，共获取 {len(self.aggregator.get_all_stock_codes())} 只股票信号")

    def generate_report(self) -> str:
        """生成分析报告"""
        result = self.aggregator.aggregate_all()
        return result.to_report()

    def send_notifications(self):
        """发送通知"""
        result = self.aggregator.aggregate_all()
        
        for notifier in self.notifiers:
            try:
                notifier.send_report(result)
                self.logger.info(f"通知发送成功: {notifier.name}")
            except Exception as e:
                self.logger.error(f"通知发送失败: {notifier.name} - {e}")

    def run_once(self):
        """执行一次扫描和通知"""
        self.logger.info("=" * 60)
        self.logger.info("开始执行扫描任务")
        self.logger.info("=" * 60)
        
        # 扫描股票
        self.scan_stocks()
        
        # 生成报告
        report = self.generate_report()
        print(report)
        
        # 发送通知
        if self.config.get('notification', {}).get('enabled', True):
            self.send_notifications()
        
        self.logger.info("扫描任务完成")

    def run_schedule(self):
        """运行定时任务"""
        import schedule
        
        schedule_config = self.config.get('schedule', {})
        
        if not schedule_config.get('enabled', True):
            self.logger.info("定时任务已禁用")
            return
        
        # 设置定时任务
        morning = schedule_config.get('morning_scan', '09:15')
        midday = schedule_config.get('midday_scan', '11:30')
        afternoon = schedule_config.get('afternoon_scan', '14:30')
        evening = schedule_config.get('evening_report', '15:30')
        
        schedule.every().day.at(morning).do(self.run_once)
        schedule.every().day.at(midday).do(self.run_once)
        schedule.every().day.at(afternoon).do(self.run_once)
        schedule.every().day.at(evening).do(self.run_once)
        
        self.logger.info(f"定时任务已设置: {morning}, {midday}, {afternoon}, {evening}")
        
        # 运行定时任务
        self.running = True
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次

    def stop(self):
        """停止监控"""
        self.running = False
        self.logger.info("监控系统正在停止...")
        
        # 关闭爬虫
        for scraper in self.scrapers:
            try:
                scraper.close()
            except Exception:
                pass
        
        self.logger.info("监控系统已停止")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI信号监控系统')
    parser.add_argument('--config', '-c', help='配置文件路径')
    parser.add_argument('--once', '-o', action='store_true', help='执行一次扫描')
    parser.add_argument('--schedule', '-s', action='store_true', help='运行定时任务')
    parser.add_argument('--stocks', '-t', nargs='+', help='指定股票代码')
    
    args = parser.parse_args()
    
    # 创建监控系统
    monitor = StockMonitor(config_path=args.config)
    
    # 处理信号
    def signal_handler(signum, frame):
        print("\n收到停止信号，正在退出...")
        monitor.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        if args.once:
            # 执行一次扫描
            monitor.run_once()
        elif args.schedule:
            # 运行定时任务
            print("启动定时任务监控...")
            print("按 Ctrl+C 停止")
            monitor.run_schedule()
        elif args.stocks:
            # 扫描指定股票
            monitor.scan_stocks(args.stocks)
            report = monitor.generate_report()
            print(report)
        else:
            # 默认执行一次扫描
            monitor.run_once()
    except KeyboardInterrupt:
        print("\n用户中断，正在退出...")
    finally:
        monitor.stop()


if __name__ == '__main__':
    main()
