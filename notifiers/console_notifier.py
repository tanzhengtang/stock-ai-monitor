"""
控制台通知器
将消息输出到控制台
"""

from typing import Optional

from .base_notifier import BaseNotifier


class ConsoleNotifier(BaseNotifier):
    """控制台通知器
    
    将消息输出到控制台，用于调试和测试。
    """

    def __init__(self):
        super().__init__(name="ConsoleNotifier")

    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送消息到控制台
        
        Args:
            message: 消息内容
            title: 消息标题
            
        Returns:
            是否发送成功
        """
        try:
            if title:
                print(f"\n{'=' * 60}")
                print(f"【{title}】")
                print('=' * 60)
            
            print(message)
            return True
        except Exception as e:
            self.logger.error(f"控制台输出失败: {e}")
            return False
