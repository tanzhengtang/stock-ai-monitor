"""
大语言模型基类
定义大模型的通用接口
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any


class BaseLLM(ABC):
    """大语言模型基类
    
    所有大模型接口都应继承此类，实现抽象方法。
    """

    def __init__(self, name: str, api_key: str = "", base_url: str = ""):
        """
        初始化大模型
        
        Args:
            name: 模型名称
            api_key: API密钥
            base_url: API基础URL
        """
        self.name = name
        self.api_key = api_key
        self.base_url = base_url
        self.logger = logging.getLogger(f'LLM.{name}')

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        对话接口
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成token数
            
        Returns:
            模型回复
        """
        pass

    def chat_with_system(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        带系统提示词的对话
        
        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            temperature: 温度参数
            max_tokens: 最大生成token数
            
        Returns:
            模型回复
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        return self.chat(messages, temperature, max_tokens, **kwargs)

    def validate_connection(self) -> bool:
        """
        验证连接是否正常
        
        Returns:
            是否连接成功
        """
        try:
            response = self.chat(
                [{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            return len(response) > 0
        except Exception as e:
            self.logger.error(f"连接验证失败: {e}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            模型信息字典
        """
        return {
            'name': self.name,
            'base_url': self.base_url,
            'has_api_key': bool(self.api_key)
        }
