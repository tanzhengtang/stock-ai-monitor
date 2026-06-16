"""
OpenAI大模型接口
"""

import requests
import json
import logging
from typing import List, Dict, Optional

from .base_llm import BaseLLM


class OpenAILLM(BaseLLM):
    """OpenAI大模型接口
    
    支持GPT-4、GPT-3.5-turbo等模型。
    
    使用方法：
    1. 注册OpenAI账号：https://platform.openai.com/
    2. 获取API Key
    3. 设置环境变量 OPENAI_API_KEY 或直接传入
    """

    # 默认配置
    DEFAULT_BASE_URL = "https://api.openai.com"
    DEFAULT_MODEL = "gpt-4o-mini"
    
    # 可用模型
    AVAILABLE_MODELS = [
        "gpt-4o",              # GPT-4 Omni
        "gpt-4o-mini",         # GPT-4 Omni Mini
        "gpt-4-turbo",         # GPT-4 Turbo
        "gpt-4",               # GPT-4
        "gpt-3.5-turbo",       # GPT-3.5 Turbo
    ]

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        timeout: int = 60
    ):
        """
        初始化OpenAI接口
        
        Args:
            api_key: API密钥
            base_url: API基础URL（支持第三方代理）
            model: 模型名称
            timeout: 请求超时时间
        """
        super().__init__(
            name="OpenAI",
            api_key=api_key,
            base_url=base_url or self.DEFAULT_BASE_URL
        )
        
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout
        
        # 如果没有提供API Key，尝试从环境变量获取
        if not self.api_key:
            import os
            self.api_key = os.environ.get('OPENAI_API_KEY', '')

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        调用OpenAI API进行对话
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            模型回复
        """
        if not self.api_key:
            raise ValueError("OpenAI API Key 未设置")
        
        # 构建请求URL
        url = f"{self.base_url}/v1/chat/completions"
        
        # 构建请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 构建请求体
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        try:
            # 发送请求
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            
            # 检查响应
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            
            # 提取回复
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            else:
                self.logger.warning(f"OpenAI响应格式异常: {result}")
                return ""
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"OpenAI API请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"OpenAI API调用异常: {e}")
            raise

    def validate_connection(self) -> bool:
        """
        验证OpenAI连接
        
        Returns:
            是否连接成功
        """
        if not self.api_key:
            self.logger.warning("OpenAI API Key 未设置")
            return False
        
        try:
            response = self.chat(
                [{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            return len(response) > 0
        except Exception as e:
            self.logger.error(f"OpenAI连接验证失败: {e}")
            return False

    def get_model_info(self) -> Dict:
        """获取模型信息"""
        info = super().get_model_info()
        info.update({
            'model': self.model,
            'available_models': self.AVAILABLE_MODELS,
            'provider': 'OpenAI'
        })
        return info
