"""
GitHub Actions 定时任务脚本
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scheduler.predictor import StockPredictor
from scheduler.email_bot import EmailBot
from scheduler.reviewer import StockReviewer


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def get_email_config():
    """从环境变量或配置文件获取邮件配置"""
    import yaml
    
    # 先尝试从配置文件读取
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if config.get('email', {}).get('sender_email'):
                return config['email']
    
    # 从环境变量读取
    return {
        'smtp_server': os.environ.get('EMAIL_SMTP_SERVER', 'smtp.qq.com'),
        'smtp_port': int(os.environ.get('EMAIL_SMTP_PORT', '465')),
        'sender_email': os.environ.get('EMAIL_SENDER', ''),
        'sender_password': os.environ.get('EMAIL_PASSWORD', ''),
        'receiver_emails': os.environ.get('EMAIL_RECEIVERS', '').split(',')
    }


def send_email(subject, content):
    """发送邮件"""
    config = get_email_config()
    if config['sender_email'] and config['receiver_emails']:
        email_bot = EmailBot(**config)
        result = email_bot.send(subject, content)
        print(f"邮件发送{'成功' if result else '失败'}")
        return result
    else:
        print("邮件配置不完整，跳过发送")
        return False


def load_predictions():
    """加载昨日预测结果"""
    pred_file = Path(__file__).parent / 'data' / 'prediction_history.json'
    
    if not pred_file.exists():
        print("没有找到预测历史文件")
        return []
    
    try:
        with open(pred_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        if not history:
            print("预测历史为空")
            return []
        
        # 获取最近一次预测
        latest = history[-1]
        predictions = latest.get('predictions', [])
        
        print(f"加载预测记录: {latest.get('date', 'N/A')}")
        print(f"预测股票数: {len(predictions)}")
        
        return predictions
    except Exception as e:
        print(f"加载预测历史失败: {e}")
        return []


def run_review():
    """运行早盘复盘"""
    print(f"开始早盘复盘 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 加载昨日预测
    predictions = load_predictions()
    
    if not predictions:
        print("没有昨日预测记录，跳过复盘")
        return
    
    # 复盘
    reviewer = StockReviewer()
    result = reviewer.review(predictions)
    
    # 生成报告
    report = reviewer.generate_report(result)
    
    # 发送邮件
    subject = f'📊 早盘复盘报告 - {datetime.now().strftime("%Y-%m-%d")}'
    send_email(subject, report)
    
    print(report)
    return report


def run_scan():
    """运行全A股扫描"""
    print(f"开始全A股扫描 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建预测器
    predictor = StockPredictor()
    print(f"股票池: {len(predictor.stock_pool)} 只股票")
    
    # 扫描全A股（3000只）
    results = predictor.scan_all_stocks(min_score=55, max_stocks=3000)
    print(f"扫描完成: {len(results)} 只股票评分 >= 55")
    
    # 生成报告
    report = f'''
{'='*60}
🔮 【全A股预测报告】{datetime.now().strftime('%Y-%m-%d %H:%M')}
{'='*60}

📊 扫描概况：
   股票总数: {len(predictor.stock_pool)} 只
   有效信号: {len(results)} 只

{'='*60}
🏆 TOP 20 推荐股票
{'='*60}
'''
    
    for i, stock in enumerate(results[:20], 1):
        expected = stock.get('expected_move', {})
        report += f'''
{i:2d}. {stock['code']} {stock['name']}
    现价: {stock['price']:.2f}  涨跌: {stock['change']:+.2f}%
    评分: {stock['score']:.0f}  信号: {stock['reasons']}
    预期涨幅: {expected.get('expected_pct', 0):+.2f}%
    目标价: {expected.get('target_price', 0):.2f}  止损价: {expected.get('stop_loss', 0):.2f}
'''
    
    report += f'''
{'='*60}
⚠️ 免责声明
{'='*60}
以上分析仅供参考，不构成投资建议。
投资有风险，入市需谨慎。
'''
    
    # 发送邮件
    subject = f'📊 全A股扫描报告 - {datetime.now().strftime("%Y-%m-%d")}'
    send_email(subject, report)
    
    print(report)
    return report


def run_refresh():
    """刷新股票池"""
    print(f"刷新股票池 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    predictor = StockPredictor()
    stocks = predictor.refresh_stock_pool()
    print(f"股票池刷新完成: {len(stocks)} 只股票")


def run_test():
    """测试邮件配置"""
    subject = f'📧 测试邮件 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    content = '这是一封测试邮件，用于验证邮件配置是否正确。'
    send_email(subject, content)


if __name__ == '__main__':
    setup_logging()
    
    command = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    
    if command == 'scan':
        run_scan()
    elif command == 'review':
        run_review()
    elif command == 'refresh':
        run_refresh()
    elif command == 'test':
        run_test()
    else:
        print(f"未知命令: {command}")
        print("可用命令: scan, review, refresh, test")
        sys.exit(1)
