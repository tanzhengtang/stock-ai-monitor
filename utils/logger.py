"""
日志管理模块
统一日志配置和管理
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


# 日志目录
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class LogManager:
    """日志管理器
    
    单例模式，统一管理日志配置
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._setup_logging()
            LogManager._initialized = True
    
    def _setup_logging(self):
        """配置日志"""
        # 根日志配置
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # 清除现有处理器
        root_logger.handlers.clear()
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        root_logger.addHandler(console_handler)
        
        # 文件处理器（按天轮转）
        today = datetime.now().strftime('%Y-%m-%d')
        file_handler = TimedRotatingFileHandler(
            LOG_DIR / f"app_{today}.log",
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
        )
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)
        
        # 错误日志处理器
        error_handler = RotatingFileHandler(
            LOG_DIR / "error.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_format)
        root_logger.addHandler(error_handler)
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """获取日志器"""
        return logging.getLogger(name)


def setup_logging(level: str = "INFO"):
    """设置日志级别"""
    LogManager()
    logging.getLogger().setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    """获取日志器"""
    return LogManager.get_logger(name)
