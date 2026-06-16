"""
GitHub Actions 定时任务脚本
"""

import os
import sys
import logging
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scheduler.predictor import StockPredictor
from scheduler.email_bot import EmailBot


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def get_email_config():
    """从环境变量获取邮件配置"""
    return {
        'smtp_server': os.environ.get('EMAIL_SMTP_SERVER', 'smtp.qq.com'),
        'smtp_port': int(os.environ.get('EMAIL_SMTP_PORT', '465')),
        'sender_email': os.environ.get('EMAIL_SENDER', ''),
        'sender_password': os.environ.get('EMAIL_PASSWORD', ''),
        'receiver_emails': os.environ.get('EMAIL_RECEIVERS', '').split(',')
    }


def run_scan():
    """运行全A股扫描"""
    print(f"开始全A股扫描 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建预测器
    predictor = StockPredictor()
    print(f"股票池: {len(predictor.stock_pool)} 只股票")
    
    # 扫描
    all_results = predictor.scan_all_sectors(max_per_sector=0)
    total = sum(len(r) for r in all_results.values())
    print(f"扫描完成: {total} 只股票")
    
    # 生成报告
    report = predictor.generate_full_report(all_results, top_per_sector=5)
    
    # 发送邮件
    config = get_email_config()
    if config['sender_email'] and config['receiver_emails']:
        email_bot = EmailBot(**config)
        subject = f'📊 全A股扫描报告 - {datetime.now().strftime("%Y-%m-%d")}'
        email_bot.send(subject, report)
        print("邮件发送成功")
    else:
        print("邮件配置不完整，跳过发送")
    
    print(report)
    return report


def run_refresh():
    """刷新股票池"""
    print(f"刷新股票池 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    predictor = StockPredictor()
    stocks = predictor.refresh_stock_pool()
    print(f"股票池刷新完成: {len(stocks)} 只股票")


if __name__ == '__main__':
    setup_logging()
    
    command = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    
    if command == 'scan':
        run_scan()
    elif command == 'refresh':
        run_refresh()
    elif command == 'test':
        # 测试邮件配置
        config = get_email_config()
        if config['sender_email'] and config['receiver_emails']:
            email_bot = EmailBot(**config)
            subject = f'📧 测试邮件 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            content = '这是一封测试邮件，用于验证邮件配置是否正确。'
            result = email_bot.send(subject, content)
            print(f"邮件发送{'成功' if result else '失败'}")
        else:
            print("邮件配置不完整")
    else:
        print(f"未知命令: {command}")
        print("可用命令: scan, refresh, test")
        sys.exit(1)
