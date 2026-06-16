"""
钉钉通知器
将消息推送到钉钉机器人
"""

import hashlib
import hmac
import base64
import time
import urllib.parse
from typing import Optional

import requests

from .base_notifier import BaseNotifier


class DingTalkNotifier(BaseNotifier):
    """钉钉通知器
    
    通过钉钉机器人Webhook推送消息。
    
    配置步骤：
    1. 在钉钉群中添加自定义机器人
    2. 获取Webhook地址
    3. 设置加签（可选）
    """

    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        """
        初始化钉钉通知器
        
        Args:
            webhook_url: 钉钉机器人Webhook地址
            secret: 加签密钥（可选）
        """
        super().__init__(name="DingTalkNotifier")
        self.webhook_url = webhook_url
        self.secret = secret

    def _get_sign(self) -> tuple:
        """
        获取签名
        
        Returns:
            (timestamp, sign) 元组
        """
        if not self.secret:
            return '', ''
        
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f'{timestamp}\n{self.secret}'
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        
        return timestamp, sign

    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送消息到钉钉
        
        Args:
            message: 消息内容
            title: 消息标题
            
        Returns:
            是否发送成功
        """
        try:
            # 构建请求URL
            url = self.webhook_url
            if self.secret:
                timestamp, sign = self._get_sign()
                url = f"{url}&timestamp={timestamp}&sign={sign}"
            
            # 构建消息体
            if title:
                # Markdown格式
                data = {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": title,
                        "text": f"## {title}\n\n{message}"
                    }
                }
            else:
                # 文本格式
                data = {
                    "msgtype": "text",
                    "text": {
                        "content": message
                    }
                }
            
            # 发送请求
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            
            if result.get('errcode') == 0:
                self.logger.info("钉钉消息发送成功")
                return True
            else:
                self.logger.error(f"钉钉消息发送失败: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"钉钉消息发送异常: {e}")
            return False

    def send_at_mobiles(self, message: str, at_mobiles: list = None, title: Optional[str] = None) -> bool:
        """
        发送消息并@指定用户
        
        Args:
            message: 消息内容
            at_mobiles: 要@的手机号列表
            title: 消息标题
            
        Returns:
            是否发送成功
        """
        try:
            # 构建请求URL
            url = self.webhook_url
            if self.secret:
                timestamp, sign = self._get_sign()
                url = f"{url}&timestamp={timestamp}&sign={sign}"
            
            # 构建消息体
            data = {
                "msgtype": "text",
                "text": {
                    "content": message
                },
                "at": {
                    "atMobiles": at_mobiles or [],
                    "isAtAll": False
                }
            }
            
            # 发送请求
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            
            if result.get('errcode') == 0:
                self.logger.info("钉钉消息发送成功")
                return True
            else:
                self.logger.error(f"钉钉消息发送失败: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"钉钉消息发送异常: {e}")
            return False
