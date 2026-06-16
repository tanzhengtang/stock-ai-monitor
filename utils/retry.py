"""
重试机制模块
提供装饰器和工具函数实现重试逻辑
"""

import time
import logging
from functools import wraps
from typing import Callable, Type, Tuple, Optional


logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 延迟倍增因子
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    attempt_num = attempt + 1
                    
                    if attempt_num < max_attempts:
                        logger.warning(
                            f"{func.__name__} 第{attempt_num}次失败: {e}, "
                            f"{current_delay:.1f}秒后重试..."
                        )
                        
                        if on_retry:
                            on_retry(attempt_num, e)
                        
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} 第{max_attempts}次失败: {e}"
                        )
            
            raise last_exception
        
        return wrapper
    return decorator


def retry_with_fallback(
    max_attempts: int = 3,
    delay: float = 1.0,
    fallback_value: any = None,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    带回退值的重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 延迟时间
        fallback_value: 失败后的回退值
        exceptions: 需要重试的异常类型
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                    else:
                        logger.warning(f"{func.__name__} 失败，返回回退值: {e}")
                        return fallback_value
        
        return wrapper
    return decorator


class RetryableRequest:
    """可重试的请求封装"""
    
    def __init__(self, max_attempts: int = 3, delay: float = 1.0):
        self.max_attempts = max_attempts
        self.delay = delay
        self.logger = logging.getLogger('RetryableRequest')
    
    def get(self, url: str, **kwargs) -> Optional[str]:
        """
        发送GET请求
        
        Args:
            url: 请求URL
            **kwargs: requests.get的参数
            
        Returns:
            响应内容
        """
        import requests
        
        for attempt in range(self.max_attempts):
            try:
                response = requests.get(url, timeout=10, **kwargs)
                response.raise_for_status()
                return response.text
            except Exception as e:
                if attempt < self.max_attempts - 1:
                    self.logger.warning(f"请求失败: {e}, {self.delay}秒后重试...")
                    time.sleep(self.delay)
                else:
                    self.logger.error(f"请求最终失败: {e}")
                    return None
    
    def post(self, url: str, **kwargs) -> Optional[str]:
        """
        发送POST请求
        
        Args:
            url: 请求URL
            **kwargs: requests.post的参数
            
        Returns:
            响应内容
        """
        import requests
        
        for attempt in range(self.max_attempts):
            try:
                response = requests.post(url, timeout=10, **kwargs)
                response.raise_for_status()
                return response.text
            except Exception as e:
                if attempt < self.max_attempts - 1:
                    self.logger.warning(f"请求失败: {e}, {self.delay}秒后重试...")
                    time.sleep(self.delay)
                else:
                    self.logger.error(f"请求最终失败: {e}")
                    return None
