"""
定时任务主程序
每日复盘和预测
"""

import yaml
import logging
import os
from datetime import datetime

from scheduler import Scheduler


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('scheduler.log', encoding='utf-8')
        ]
    )


def load_config():
    """加载配置"""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'scheduler.yaml')
    
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    return {}


def main():
    """主函数"""
    print("=" * 60)
    print("股票预测定时任务")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 设置日志
    setup_logging()
    
    # 加载配置
    config = load_config()
    
    print(f"\n配置信息:")
    print(f"  QQ机器人Webhook: {config.get('qq_webhook', '未配置')}")
    print(f"  目标群号: {config.get('group_id', '未配置')}")
    
    print(f"\n定时任务:")
    print(f"  10:50 - 早盘复盘")
    print(f"  15:30 - 尾盘预测")
    
    print(f"\n按 Ctrl+C 停止...")
    
    # 创建调度器
    scheduler = Scheduler(config)
    
    # 运行
    try:
        scheduler.run()
    except KeyboardInterrupt:
        print("\n\n定时任务已停止")


if __name__ == '__main__':
    main()
