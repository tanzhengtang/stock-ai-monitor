"""
大语言模型接口模块
支持多种大模型：DeepSeek、OpenAI、本地模型等
"""

from .base_llm import BaseLLM
from .deepseek_llm import DeepSeekLLM
from .openai_llm import OpenAILLM
from .local_llm import LocalLLM

__all__ = [
    'BaseLLM',
    'DeepSeekLLM',
    'OpenAILLM',
    'LocalLLM'
]
