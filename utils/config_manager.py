"""
统一配置管理模块
集中管理所有配置
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"


@dataclass
class EmailConfig:
    """邮件配置"""
    smtp_server: str = "smtp.qq.com"
    smtp_port: int = 465
    sender_email: str = ""
    sender_password: str = ""
    receiver_emails: list = field(default_factory=list)


@dataclass
class ScheduleConfig:
    """定时任务配置"""
    morning_review: str = "10:50"
    afternoon_predict: str = "15:30"
    push_type: str = "email"  # 'email' or 'qq'


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 1000000
    commission_rate: float = 0.0003
    min_commission: float = 5
    tax_rate: float = 0.001
    slippage: float = 0.001
    max_position_pct: float = 0.2
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.1
    max_holding_days: int = 20


@dataclass
class RiskConfig:
    """风险配置"""
    max_position_pct: float = 0.2
    max_total_position_pct: float = 0.8
    min_cash_ratio: float = 0.2
    max_daily_loss_pct: float = 0.03
    max_drawdown_pct: float = 0.1
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.15
    max_orders_per_day: int = 10


@dataclass
class AppConfig:
    """应用配置"""
    debug: bool = False
    log_level: str = "INFO"
    data_cache_hours: int = 24
    scan_stock_count: int = 50
    recommend_count: int = 10


class ConfigManager:
    """配置管理器
    
    单例模式，全局配置管理
    """
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self):
        """加载配置"""
        # 默认配置
        self._config = {
            'app': AppConfig(),
            'email': EmailConfig(),
            'schedule': ScheduleConfig(),
            'backtest': BacktestConfig(),
            'risk': RiskConfig()
        }
        
        # 从文件加载
        config_file = CONFIG_DIR / "settings.yaml"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f) or {}
                
                # 更新邮件配置
                if 'email' in file_config:
                    email_cfg = file_config['email']
                    self._config['email'] = EmailConfig(
                        smtp_server=email_cfg.get('smtp_server', 'smtp.qq.com'),
                        smtp_port=email_cfg.get('smtp_port', 465),
                        sender_email=email_cfg.get('sender_email', ''),
                        sender_password=email_cfg.get('sender_password', ''),
                        receiver_emails=email_cfg.get('receiver_emails', [])
                    )
                
                # 更新定时任务配置
                if 'schedule' in file_config:
                    sched_cfg = file_config['schedule']
                    self._config['schedule'] = ScheduleConfig(
                        morning_review=sched_cfg.get('morning_review', '10:50'),
                        afternoon_predict=sched_cfg.get('afternoon_predict', '15:30'),
                        push_type=file_config.get('push_type', 'email')
                    )
                
                # 更新回测配置
                if 'backtest' in file_config:
                    bt_cfg = file_config['backtest']
                    self._config['backtest'] = BacktestConfig(**bt_cfg)
                
            except Exception as e:
                print(f"加载配置文件失败: {e}")
    
    @property
    def app(self) -> AppConfig:
        return self._config['app']
    
    @property
    def email(self) -> EmailConfig:
        return self._config['email']
    
    @property
    def schedule(self) -> ScheduleConfig:
        return self._config['schedule']
    
    @property
    def backtest(self) -> BacktestConfig:
        return self._config['backtest']
    
    @property
    def risk(self) -> RiskConfig:
        return self._config['risk']
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置"""
        return getattr(self._config, key, default)
    
    def update(self, key: str, value: Any):
        """更新配置"""
        self._config[key] = value


# 全局配置实例
config = ConfigManager()


def get_config() -> ConfigManager:
    """获取配置管理器"""
    return config
