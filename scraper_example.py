"""
爬虫模块使用示例
"""

import yaml
import os
from scrapers import EastMoneyScraper, TongHuaShunScraper, XueQiuScraper
from signal_aggregator import SignalAggregator


def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'cookies.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def main():
    """主函数"""
    print("=" * 60)
    print("爬虫模块使用示例")
    print("=" * 60)
    print()

    # 加载配置
    config = load_config()
    xueqiu_cookie = config.get('xueqiu', {}).get('cookie', '')

    # 创建聚合器
    aggregator = SignalAggregator()

    # 股票代码列表
    stock_codes = ['000001', '600519', '000858']

    # 使用东方财富爬虫
    print("【东方财富爬虫】")
    with EastMoneyScraper() as scraper:
        for code in stock_codes:
            signal = scraper.get_stock_signal(code)
            if signal:
                print(f"  {code} {signal.stock_name}: "
                      f"{signal.score:.1f}分 ({signal.signal_type.value})")
                aggregator.add_signal(signal)
            else:
                print(f"  {code}: 获取失败")

    print()

    # 使用同花顺爬虫
    print("【同花顺爬虫】")
    with TongHuaShunScraper() as scraper:
        for code in stock_codes:
            signal = scraper.get_stock_signal(code)
            if signal:
                print(f"  {code} {signal.stock_name}: "
                      f"{signal.score:.1f}分 ({signal.signal_type.value})")
                aggregator.add_signal(signal)
            else:
                print(f"  {code}: 获取失败")

    print()

    # 使用雪球爬虫（需要配置cookie）
    print("【雪球爬虫】")
    if xueqiu_cookie:
        with XueQiuScraper(cookie=xueqiu_cookie) as scraper:
            for code in stock_codes:
                signal = scraper.get_stock_signal(code)
                if signal:
                    print(f"  {code} {signal.stock_name}: "
                          f"{signal.score:.1f}分 ({signal.signal_type.value})")
                    aggregator.add_signal(signal)
                else:
                    print(f"  {code}: 获取失败")
    else:
        print("  未配置cookie，跳过雪球爬虫")
        print("  请在 config/cookies.yaml 中配置雪球cookie")

    print()

    # 聚合结果
    print("=" * 60)
    print("聚合结果")
    print("=" * 60)
    
    result = aggregator.aggregate_all()
    print(result.to_report())


if __name__ == '__main__':
    main()
