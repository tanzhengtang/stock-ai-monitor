"""
QQ机器人推送模块
通过Webhook推送消息
"""

import requests
import logging
from typing import Dict, Optional


class QQBot:
    """QQ机器人
    
    支持多种QQ机器人框架：
    1. go-cqhttp
    2. Mirai
    3. 其他支持HTTP POST的框架
    """

    def __init__(self, webhook_url: str = '', bot_type: str = 'go-cqhttp'):
        """
        初始化QQ机器人
        
        Args:
            webhook_url: Webhook地址
            bot_type: 机器人类型 ('go-cqhttp', 'mirai', 'custom')
        """
        self.webhook_url = webhook_url
        self.bot_type = bot_type
        self.logger = logging.getLogger('QQBot')
        
        # 消息队列
        self.message_queue = []

    def send(self, message: str, target_type: str = 'group', target_id: str = '') -> bool:
        """
        发送消息
        
        Args:
            message: 消息内容
            target_type: 目标类型 ('group'群聊, 'private'私聊)
            target_id: 目标ID (群号或QQ号)
            
        Returns:
            是否发送成功
        """
        if not self.webhook_url:
            self.logger.warning("Webhook URL未配置")
            print(f"[QQ Bot] 消息预览:\n{message}")
            return False
        
        try:
            if self.bot_type == 'go-cqhttp':
                return self._send_go_cqhttp(message, target_type, target_id)
            elif self.bot_type == 'mirai':
                return self._send_mirai(message, target_type, target_id)
            else:
                return self._send_custom(message)
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")
            return False

    def _send_go_cqhttp(self, message: str, target_type: str, target_id: str) -> bool:
        """
        go-cqhttp 发送消息
        
        go-cqhttp Webhook格式：
        POST /send_msg
        {
            "message_type": "group",
            "group_id": "123456",
            "message": "消息内容"
        }
        """
        data = {
            'message': message
        }
        
        if target_type == 'group':
            data['message_type'] = 'group'
            data['group_id'] = target_id
        elif target_type == 'private':
            data['message_type'] = 'private'
            data['user_id'] = target_id
        
        resp = requests.post(
            f"{self.webhook_url}/send_msg",
            json=data,
            timeout=10
        )
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get('status') == 'ok':
                self.logger.info(f"消息发送成功: {target_type} {target_id}")
                return True
        
        self.logger.error(f"消息发送失败: {resp.text}")
        return False

    def _send_mirai(self, message: str, target_type: str, target_id: str) -> bool:
        """
        Mirai 发送消息
        
        Mirai Webhook格式：
        POST /sendGroupMessage
        {
            "target": 123456,
            "messageChain": [{"type": "Plain", "text": "消息内容"}]
        }
        """
        if target_type == 'group':
            url = f"{self.webhook_url}/sendGroupMessage"
            data = {
                'target': int(target_id),
                'messageChain': [{'type': 'Plain', 'text': message}]
            }
        else:
            url = f"{self.webhook_url}/sendFriendMessage"
            data = {
                'target': int(target_id),
                'messageChain': [{'type': 'Plain', 'text': message}]
            }
        
        resp = requests.post(url, json=data, timeout=10)
        
        if resp.status_code == 200:
            self.logger.info(f"消息发送成功")
            return True
        
        return False

    def _send_custom(self, message: str) -> bool:
        """
        自定义Webhook发送
        
        简单的POST请求，发送消息内容
        """
        data = {
            'content': message,
            'timestamp': str(int(datetime.now().timestamp()))
        }
        
        resp = requests.post(
            self.webhook_url,
            json=data,
            timeout=10
        )
        
        return resp.status_code == 200

    def send_daily_report(self, report_type: str, content: str) -> bool:
        """
        发送每日报告
        
        Args:
            report_type: 报告类型 ('review'复盘, 'predict'预测)
            content: 报告内容
            
        Returns:
            是否发送成功
        """
        # 添加时间戳
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        message = f"[{timestamp}]\n{content}"
        
        return self.send(message)


# 测试代码
if __name__ == '__main__':
    # 测试（不发送实际消息）
    bot = QQBot(webhook_url='')
    
    test_message = """
📊 【早盘复盘】2026-06-15

昨日推荐股票表现：
✅ 600519 贵州茅台: +1.50%
❌ 601318 中国平安: -0.80%

整体胜率：50.0%
平均涨幅：+0.35%

⚠️ 以上仅供参考，不构成投资建议
"""
    
    print("测试消息预览：")
    print(test_message)
    
    # 实际发送需要配置webhook_url
    # bot.send(test_message, target_type='group', target_id='123456')
