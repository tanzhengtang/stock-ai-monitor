"""
本地大模型接口
支持Ollama、LM Studio等本地部署的模型
"""

import requests
import json
import logging
from typing import List, Dict, Optional

from .base_llm import BaseLLM


class LocalLLM(BaseLLM):
    """本地大模型接口
    
    支持Ollama、LM Studio等本地部署的模型。
    
    使用方法：
    1. 安装Ollama：https://ollama.ai/
    2. 拉取模型：ollama pull qwen2.5:7b
    3. 启动服务：ollama serve
    """

    # 默认配置
    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "qwen2.5:7b"
    
    # 推荐模型
    RECOMMENDED_MODELS = [
        "qwen2.5:7b",          # 通义千问2.5 7B
        "qwen2.5:14b",         # 通义千问2.5 14B
        "llama3.1:8b",         # Llama 3.1 8B
        "deepseek-coder:6.7b", # DeepSeek Coder 6.7B
        "mistral:7b",          # Mistral 7B
    ]

    def __init__(
        self,
        base_url: str = "",
        model: str = "",
        timeout: int = 120
    ):
        """
        初始化本地模型接口
        
        Args:
            base_url: Ollama服务地址
            model: 模型名称
            timeout: 请求超时时间
        """
        super().__init__(
            name="Local",
            api_key="",  # 本地模型不需要API Key
            base_url=base_url or self.DEFAULT_BASE_URL
        )
        
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        调用本地模型进行对话
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            模型回复
        """
        # 构建请求URL（Ollama格式）
        url = f"{self.base_url}/v1/chat/completions"
        
        # 构建请求体
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            **kwargs
        }
        
        try:
            # 发送请求
            response = requests.post(
                url,
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
                self.logger.warning(f"本地模型响应格式异常: {result}")
                return ""
                
        except requests.exceptions.ConnectionError:
            self.logger.error(f"无法连接到本地模型服务: {self.base_url}")
            raise ConnectionError(f"请确保本地模型服务已启动: {self.base_url}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"本地模型请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"本地模型调用异常: {e}")
            raise

    def validate_connection(self) -> bool:
        """
        验证本地模型连接
        
        Returns:
            是否连接成功
        """
        try:
            # 检查Ollama服务是否运行
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            
            if response.status_code == 200:
                # 检查模型是否存在
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                
                if self.model in model_names:
                    self.logger.info(f"本地模型 {self.model} 可用")
                    return True
                else:
                    self.logger.warning(f"模型 {self.model} 不存在，可用模型: {model_names}")
                    return False
            else:
                return False
                
        except requests.exceptions.ConnectionError:
            self.logger.error(f"无法连接到本地模型服务: {self.base_url}")
            return False
        except Exception as e:
            self.logger.error(f"本地模型连接验证失败: {e}")
            return False

    def list_models(self) -> List[str]:
        """
        列出可用的本地模型
        
        Returns:
            模型名称列表
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                return [m['name'] for m in models]
            else:
                return []
                
        except Exception:
            return []

    def get_model_info(self) -> Dict:
        """获取模型信息"""
        info = super().get_model_info()
        info.update({
            'model': self.model,
            'recommended_models': self.RECOMMENDED_MODELS,
            'available_models': self.list_models(),
            'provider': 'Local (Ollama)'
        })
        return info
