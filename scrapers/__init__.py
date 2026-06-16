"""
爬虫模块
用于从各平台获取AI股票信号
"""

from .base_scraper import BaseScraper
from .eastmoney import EastMoneyScraper
from .tonghuashun import TongHuaShunScraper
from .akshare_scraper import AKShareScraper
from .baostock_scraper import BaoStockScraper

# 雪球爬虫暂时禁用（需要登录cookie）
# from .xueqiu import XueQiuScraper

__all__ = [
    'BaseScraper',
    'EastMoneyScraper',
    'TongHuaShunScraper',
    'AKShareScraper',
    'BaoStockScraper',
    # 'XueQiuScraper'
]
