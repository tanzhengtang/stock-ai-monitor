"""
GitHub Actions配置生成器
"""

import os
import yaml


def create_config():
    """从环境变量创建配置文件"""
    config = {
        'push_type': 'email',
        'email': {
            'smtp_server': os.environ.get('EMAIL_SMTP_SERVER', 'smtp.qq.com'),
            'smtp_port': int(os.environ.get('EMAIL_SMTP_PORT', '465')),
            'sender_email': os.environ.get('EMAIL_SENDER', ''),
            'sender_password': os.environ.get('EMAIL_PASSWORD', ''),
            'receiver_emails': os.environ.get('EMAIL_RECEIVERS', '').split(',')
        },
        'schedule': {
            'morning_review': '10:50',
            'afternoon_predict': '15:30'
        }
    }
    
    os.makedirs('config', exist_ok=True)
    
    with open('config/settings.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    print("配置文件创建成功")


if __name__ == '__main__':
    create_config()
