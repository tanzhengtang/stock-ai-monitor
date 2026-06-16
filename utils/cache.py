"""
数据缓存模块
缓存股票数据，减少重复请求
"""

import os
import json
import pickle
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any
import logging

# 缓存目录
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class DataCache:
    """数据缓存
    
    支持：
    1. 基于文件的持久化缓存
    2. 内存缓存
    3. 自动过期
    """
    
    def __init__(self, cache_dir: Path = None, expire_hours: int = 24):
        """
        初始化缓存
        
        Args:
            cache_dir: 缓存目录
            expire_hours: 缓存过期时间（小时）
        """
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.expire_hours = expire_hours
        self.logger = logging.getLogger('DataCache')
        
        # 内存缓存
        self._memory_cache = {}
    
    def _get_key(self, prefix: str, params: dict) -> str:
        """生成缓存键"""
        # 排序参数
        sorted_params = sorted(params.items())
        param_str = f"{prefix}_{str(sorted_params)}"
        return hashlib.md5(param_str.encode()).hexdigest()
    
    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.pkl"
    
    def get(self, prefix: str, params: dict) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            prefix: 缓存前缀
            params: 参数
            
        Returns:
            缓存数据，如果不存在或过期返回None
        """
        key = self._get_key(prefix, params)
        
        # 先检查内存缓存
        if key in self._memory_cache:
            data, timestamp = self._memory_cache[key]
            if datetime.now() - timestamp < timedelta(hours=self.expire_hours):
                return data
            else:
                del self._memory_cache[key]
        
        # 检查文件缓存
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    data, timestamp = pickle.load(f)
                
                # 检查是否过期
                if datetime.now() - timestamp < timedelta(hours=self.expire_hours):
                    # 加载到内存
                    self._memory_cache[key] = (data, timestamp)
                    return data
                else:
                    # 删除过期缓存
                    cache_path.unlink()
            except Exception as e:
                self.logger.warning(f"读取缓存失败: {e}")
        
        return None
    
    def set(self, prefix: str, params: dict, data: Any):
        """
        设置缓存
        
        Args:
            prefix: 缓存前缀
            params: 参数
            data: 数据
        """
        key = self._get_key(prefix, params)
        timestamp = datetime.now()
        
        # 保存到内存
        self._memory_cache[key] = (data, timestamp)
        
        # 保存到文件
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump((data, timestamp), f)
        except Exception as e:
            self.logger.warning(f"保存缓存失败: {e}")
    
    def clear(self, prefix: str = None):
        """
        清除缓存
        
        Args:
            prefix: 缓存前缀，如果为None清除所有
        """
        if prefix:
            # 清除指定前缀的内存缓存
            keys_to_remove = [k for k in self._memory_cache if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._memory_cache[key]
        else:
            # 清除所有
            self._memory_cache.clear()
        
        # 清除文件缓存
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                cache_file.unlink()
            except Exception:
                pass
    
    def clear_expired(self):
        """清除过期缓存"""
        now = datetime.now()
        
        # 清除内存缓存
        expired_keys = [
            k for k, (_, timestamp) in self._memory_cache.items()
            if now - timestamp >= timedelta(hours=self.expire_hours)
        ]
        for key in expired_keys:
            del self._memory_cache[key]
        
        # 清除文件缓存
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                with open(cache_file, 'rb') as f:
                    _, timestamp = pickle.load(f)
                if now - timestamp >= timedelta(hours=self.expire_hours):
                    cache_file.unlink()
            except Exception:
                pass


# 全局缓存实例
_cache = None


def get_cache(expire_hours: int = 24) -> DataCache:
    """获取缓存实例"""
    global _cache
    if _cache is None:
        _cache = DataCache(expire_hours=expire_hours)
    return _cache
