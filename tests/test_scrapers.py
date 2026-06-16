"""
爬虫模块测试用例
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from scrapers.base_scraper import BaseScraper
from scrapers.eastmoney import EastMoneyScraper
from scrapers.tonghuashun import TongHuaShunScraper
from scrapers.akshare_scraper import AKShareScraper
from scrapers.baostock_scraper import BaoStockScraper
from signal_aggregator.models import Platform, SignalType, PlatformSignal, AnalysisType


class TestBaseScraper(unittest.TestCase):
    """测试爬虫基类"""

    def test_score_to_signal_type(self):
        """测试评分转换为信号类型"""
        # 创建一个具体的子类来测试
        class TestScraper(BaseScraper):
            def get_stock_signal(self, stock_code):
                return None
            def get_hot_stocks(self):
                return []
        
        scraper = TestScraper(
            platform=Platform.EASTMONEY,
            base_url='http://test.com'
        )
        
        self.assertEqual(scraper.score_to_signal_type(90), SignalType.STRONG_BUY)
        self.assertEqual(scraper.score_to_signal_type(70), SignalType.BUY)
        self.assertEqual(scraper.score_to_signal_type(50), SignalType.NEUTRAL)
        self.assertEqual(scraper.score_to_signal_type(30), SignalType.SELL)
        self.assertEqual(scraper.score_to_signal_type(10), SignalType.STRONG_SELL)


class TestEastMoneyScraper(unittest.TestCase):
    """测试东方财富爬虫"""

    def setUp(self):
        self.scraper = EastMoneyScraper()

    def test_convert_stock_code(self):
        """测试股票代码转换"""
        # 上海股票
        self.assertEqual(self.scraper._convert_stock_code('600519'), '1.600519')
        self.assertEqual(self.scraper._convert_stock_code('688001'), '1.688001')
        
        # 深圳股票
        self.assertEqual(self.scraper._convert_stock_code('000001'), '0.000001')
        self.assertEqual(self.scraper._convert_stock_code('300001'), '0.300001')
        
        # 无效代码
        self.assertIsNone(self.scraper._convert_stock_code('999999'))

    def test_calculate_score_from_quote(self):
        """测试从行情数据计算评分"""
        # 上涨股票
        quote_data = {'f170': 5.0, 'f168': 3.0, 'f50': 1.5}
        score = self.scraper._calculate_score_from_quote(quote_data)
        self.assertGreater(score, 50)
        
        # 下跌股票
        quote_data = {'f170': -5.0, 'f168': 3.0, 'f50': 1.5}
        score = self.scraper._calculate_score_from_quote(quote_data)
        self.assertLess(score, 50)
        
        # 平盘
        quote_data = {'f170': 0, 'f168': 1.0, 'f50': 1.0}
        score = self.scraper._calculate_score_from_quote(quote_data)
        self.assertEqual(score, 50)

    def test_generate_reasons(self):
        """测试生成理由"""
        # 上涨
        quote_data = {'f170': 6.0, 'f168': 6.0, 'f50': 2.5}
        reasons = self.scraper._generate_reasons(quote_data)
        self.assertIn('涨幅较大', reasons)
        self.assertIn('换手率活跃', reasons)
        self.assertIn('成交量放大', reasons)
        
        # 下跌
        quote_data = {'f170': -6.0, 'f168': 1.0, 'f50': 0.8}
        reasons = self.scraper._generate_reasons(quote_data)
        self.assertIn('跌幅较大', reasons)

    @patch('scrapers.base_scraper.BaseScraper.get_json')
    def test_get_stock_signal(self, mock_get_json):
        """测试获取股票信号"""
        # Mock返回数据
        mock_get_json.return_value = {
            'data': {
                'f58': '平安银行',
                'f170': 2.5,
                'f168': 3.0,
                'f50': 1.2
            }
        }
        
        signal = self.scraper.get_stock_signal('000001')
        
        self.assertIsNotNone(signal)
        self.assertEqual(signal.stock_code, '000001')
        self.assertEqual(signal.platform, Platform.EASTMONEY)
        self.assertIsInstance(signal.score, float)
        self.assertIsInstance(signal.signal_type, SignalType)

    def tearDown(self):
        self.scraper.close()


class TestTongHuaShunScraper(unittest.TestCase):
    """测试同花顺爬虫"""

    def setUp(self):
        self.scraper = TongHuaShunScraper()

    def test_calculate_score(self):
        """测试计算评分"""
        # 上涨
        quote_data = {'change_pct': 5.0, 'volume': 2000000}
        score = self.scraper._calculate_score(quote_data)
        self.assertGreater(score, 50)
        
        # 下跌
        quote_data = {'change_pct': -5.0, 'volume': 2000000}
        score = self.scraper._calculate_score(quote_data)
        self.assertLess(score, 50)

    def test_generate_reasons(self):
        """测试生成理由"""
        quote_data = {'change_pct': 6.0, 'volume': 2000000}
        reasons = self.scraper._generate_reasons(quote_data)
        self.assertIn('涨幅较大', reasons)
        self.assertIn('成交量活跃', reasons)

    def test_calculate_confidence(self):
        """测试计算置信度"""
        quote_data = {'volume': 1000000, 'price': 10.0}
        confidence = self.scraper._calculate_confidence(quote_data)
        self.assertGreater(confidence, 0.6)

    def tearDown(self):
        self.scraper.close()


class TestAKShareScraper(unittest.TestCase):
    """测试AKShare爬虫"""

    def setUp(self):
        self.scraper = AKShareScraper()

    def test_calculate_score(self):
        """测试计算评分"""
        # 上涨，低市盈率
        data = {
            'change_pct': 5.0,
            'pe': 12,
            'pb': 1.5,
            'roe': 15,
            'volume': 2000000
        }
        score = self.scraper._calculate_score(data)
        self.assertGreater(score, 60)
        
        # 下跌，高市盈率
        data = {
            'change_pct': -5.0,
            'pe': 150,
            'pb': 10,
            'roe': 5,
            'volume': 500000
        }
        score = self.scraper._calculate_score(data)
        self.assertLess(score, 40)

    def test_generate_reasons(self):
        """测试生成理由"""
        data = {
            'change_pct': 6.0,
            'pe': 12,
            'pb': 0.8,
            'roe': 25,
            'total_mv': 200000000000
        }
        reasons = self.scraper._generate_reasons(data)
        self.assertIn('涨幅较大', reasons)
        self.assertIn('低市盈率', reasons)
        self.assertIn('破净股', reasons)
        self.assertIn('ROE优秀', reasons)
        self.assertIn('大盘股', reasons)

    def test_calculate_confidence(self):
        """测试计算置信度"""
        data = {
            'price': 10.0,
            'pe': 15,
            'pb': 1.5,
            'revenue': 1000000000,
            'net_profit': 100000000,
            'roe': 15,
            'gross_margin': 50,
            'operating_cashflow': 80000000,
            'net_profit_growth': 20
        }
        confidence = self.scraper._calculate_confidence(data)
        self.assertGreater(confidence, 0.8)

    def tearDown(self):
        self.scraper.close()


class TestBaoStockScraper(unittest.TestCase):
    """测试BaoStock爬虫"""

    def setUp(self):
        self.scraper = BaoStockScraper()

    def test_convert_stock_code(self):
        """测试股票代码转换"""
        # 上海股票
        self.assertEqual(self.scraper._convert_stock_code('600519'), 'sh.600519')
        
        # 深圳股票
        self.assertEqual(self.scraper._convert_stock_code('000001'), 'sz.000001')
        self.assertEqual(self.scraper._convert_stock_code('300001'), 'sz.300001')
        
        # 无效代码
        self.assertIsNone(self.scraper._convert_stock_code('999999'))

    def test_calculate_score(self):
        """测试计算评分"""
        # 上涨，低市盈率
        data = {
            'change_pct': 5.0,
            'pe': 12,
            'pb': 1.5,
            'roe': 15,
            'profit_growth': 20
        }
        score = self.scraper._calculate_score(data)
        self.assertGreater(score, 60)
        
        # 下跌，高市盈率
        data = {
            'change_pct': -5.0,
            'pe': 150,
            'pb': 10,
            'roe': 5,
            'profit_growth': -10
        }
        score = self.scraper._calculate_score(data)
        self.assertLess(score, 40)

    def test_generate_reasons(self):
        """测试生成理由"""
        data = {
            'change_pct': 6.0,
            'pe': 12,
            'pb': 0.8,
            'roe': 25,
            'profit_growth': 35
        }
        reasons = self.scraper._generate_reasons(data)
        self.assertIn('涨幅较大', reasons)
        self.assertIn('低市盈率', reasons)
        self.assertIn('破净股', reasons)
        self.assertIn('ROE优秀', reasons)
        self.assertIn('高成长', reasons)

    def test_calculate_confidence(self):
        """测试计算置信度"""
        data = {
            'price': 10.0,
            'pe': 15,
            'pb': 1.5,
            'roe': 15,
            'profit_growth': 20
        }
        confidence = self.scraper._calculate_confidence(data)
        self.assertGreater(confidence, 0.8)

    def tearDown(self):
        self.scraper.close()


class TestScraperIntegration(unittest.TestCase):
    """爬虫集成测试"""

    def test_all_scrapers_instantiation(self):
        """测试所有爬虫可以正常实例化"""
        scrapers = [
            EastMoneyScraper(),
            TongHuaShunScraper(),
            AKShareScraper(),
            BaoStockScraper()
        ]
        
        for scraper in scrapers:
            self.assertIsNotNone(scraper.platform)
            self.assertIsNotNone(scraper.base_url)
            scraper.close()

    def test_scraper_context_manager(self):
        """测试爬虫上下文管理器"""
        with EastMoneyScraper() as scraper:
            self.assertIsNotNone(scraper)


if __name__ == '__main__':
    unittest.main()
