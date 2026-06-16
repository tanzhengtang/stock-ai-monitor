"""
DeepSeek大模型接口
"""

import requests
import json
import logging
from typing import List, Dict, Optional

from .base_llm import BaseLLM


class DeepSeekLLM(BaseLLM):
    """DeepSeek大模型接口
    
    DeepSeek API兼容OpenAI格式，支持多种模型：
    
    模型系列：
    1. deepseek-chat (DeepSeek-V3) - 通用对话模型，性价比最高
    2. deepseek-reasoner (DeepSeek-R1) - 推理模型，复杂推理能力强
    3. deepseek-coder - 代码模型，代码生成和理解
    
    使用方法：
    1. 注册DeepSeek账号：https://platform.deepseek.com/
    2. 获取API Key
    3. 设置环境变量 DEEPSEEK_API_KEY 或直接传入
    """

    # 默认配置
    DEFAULT_BASE_URL = "https://api.deepseek.com"
    DEFAULT_MODEL = "deepseek-chat"
    
    # 可用模型及详细信息
    AVAILABLE_MODELS = {
        "deepseek-chat": {
            "name": "DeepSeek-V3",
            "description": "通用对话模型，性价比最高",
            "context_window": 65536,
            "max_output": 8192,
            "cost_per_1k_input": 0.001,   # 元/千token
            "cost_per_1k_output": 0.002,  # 元/千token
            "use_case": "通用对话、文本生成、问答"
        },
        "deepseek-reasoner": {
            "name": "DeepSeek-R1",
            "description": "推理模型，复杂推理能力强",
            "context_window": 65536,
            "max_output": 8192,
            "cost_per_1k_input": 0.004,   # 元/千token
            "cost_per_1k_output": 0.016,  # 元/千token
            "use_case": "复杂推理、数学计算、逻辑分析"
        },
        "deepseek-coder": {
            "name": "DeepSeek-Coder",
            "description": "代码模型，代码生成和理解",
            "context_window": 65536,
            "max_output": 8192,
            "cost_per_1k_input": 0.001,
            "cost_per_1k_output": 0.002,
            "use_case": "代码生成、代码理解、技术问答"
        }
    }
    
    # 推荐模型（按场景）
    RECOMMENDED_MODELS = {
        "stock_analysis": "deepseek-chat",      # 股票分析推荐
        "complex_reasoning": "deepseek-reasoner", # 复杂推理推荐
        "code_generation": "deepseek-coder",    # 代码生成推荐
        "cost_effective": "deepseek-chat",      # 性价比推荐
    }

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        timeout: int = 60
    ):
        """
        初始化DeepSeek接口
        
        Args:
            api_key: API密钥
            base_url: API基础URL
            model: 模型名称
            timeout: 请求超时时间
        """
        super().__init__(
            name="DeepSeek",
            api_key=api_key,
            base_url=base_url or self.DEFAULT_BASE_URL
        )
        
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout
        
        # 如果没有提供API Key，尝试从环境变量获取
        if not self.api_key:
            import os
            self.api_key = os.environ.get('DEEPSEEK_API_KEY', '')

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        调用DeepSeek API进行对话
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            模型回复
        """
        if not self.api_key:
            raise ValueError("DeepSeek API Key 未设置")
        
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
                self.logger.warning(f"DeepSeek响应格式异常: {result}")
                return ""
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"DeepSeek API请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"DeepSeek API调用异常: {e}")
            raise

    def validate_connection(self) -> bool:
        """
        验证DeepSeek连接
        
        Returns:
            是否连接成功
        """
        if not self.api_key:
            self.logger.warning("DeepSeek API Key 未设置")
            return False
        
        try:
            response = self.chat(
                [{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            return len(response) > 0
        except Exception as e:
            self.logger.error(f"DeepSeek连接验证失败: {e}")
            return False

    def get_model_info(self) -> Dict:
        """获取模型信息"""
        info = super().get_model_info()
        info.update({
            'model': self.model,
            'model_detail': self.AVAILABLE_MODELS.get(self.model, {}),
            'available_models': list(self.AVAILABLE_MODELS.keys()),
            'recommended_models': self.RECOMMENDED_MODELS,
            'provider': 'DeepSeek'
        })
        return info

    @classmethod
    def list_models(cls) -> List[Dict]:
        """
        列出所有可用模型
        
        Returns:
            模型信息列表
        """
        models = []
        for model_id, model_info in cls.AVAILABLE_MODELS.items():
            models.append({
                'id': model_id,
                **model_info
            })
        return models

    @classmethod
    def get_recommended_model(cls, scenario: str = "stock_analysis") -> str:
        """
        获取推荐模型
        
        Args:
            scenario: 使用场景
            
        Returns:
            推荐的模型名称
        """
        return cls.RECOMMENDED_MODELS.get(scenario, cls.DEFAULT_MODEL)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        估算调用成本
        
        Args:
            input_tokens: 输入token数
            output_tokens: 输出token数
            
        Returns:
            预估成本（元）
        """
        model_info = self.AVAILABLE_MODELS.get(self.model, {})
        cost_input = model_info.get('cost_per_1k_input', 0.001)
        cost_output = model_info.get('cost_per_1k_output', 0.002)
        
        return (input_tokens / 1000 * cost_input) + (output_tokens / 1000 * cost_output)
