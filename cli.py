"""
量化交易系统 CLI 入口
统一命令行界面
"""

import argparse
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

from utils import setup_logging, get_logger, get_config


def cmd_scan(args):
    """扫描市场"""
    from scheduler.predictor import StockPredictor
    from scheduler.email_bot import EmailBot
    
    logger = get_logger('CLI')
    config = get_config()
    predictor = StockPredictor(
        fundamental_weight=args.fund_weight,
    )
    
    if args.all:
        # 全A股扫描
        logger.info("开始全A股扫描...")
        results = predictor.scan_all_stocks(min_score=args.min_score, max_stocks=args.top)
        
        print(f"\n全A股扫描完成: {len(results)} 只股票 (含基本面评分)")
        header = f"{'#':<3} {'代码':<8} {'名称':<10} {'现价':<8} {'涨跌幅':<8} {'评分':<6} {'信号'}"
        print(f"\n{header}")
        print("-" * 70)
        
        for i, stock in enumerate(results[:args.top], 1):
            print(f"{i:<3} {stock['code']:<8} {stock['name']:<10} {stock['price']:.2f}{'':<4} {stock['change']:+.2f}%{'':<3} {stock['score']:<6.0f} {stock['reasons'][:60]}")
        
        if args.email and results:
            report = _build_email_report(results, args.top)
            _send_email_report(report, config, logger)
    else:
        # 按板块扫描
        logger.info("开始按板块扫描...")
        all_results = predictor.scan_all_sectors()
        
        # 生成报告
        report = predictor.generate_full_report(all_results, top_per_sector=args.top)
        print(report)
        
        if args.email and all_results:
            _send_email_report(report, config, logger)


def cmd_review(args):
    """复盘"""
    from scheduler.reviewer import StockReviewer
    
    logger = get_logger('CLI')
    logger.info("开始复盘...")
    
    reviewer = StockReviewer()
    pred_file = Path("data/prediction_history.json")
    
    if pred_file.exists():
        history = json.loads(pred_file.read_text('utf-8'))
        if not history:
            print("预测历史为空")
            return
        
        latest = history[-1]
        predictions = latest.get('predictions', [])
        predictions.sort(key=lambda x: x.get('score', 0), reverse=True)
        top10 = predictions[:10]
        print(f"复盘日期: {latest.get('date', 'N/A')}, 预测共 {len(predictions)} 只, 复盘前 {len(top10)} 只")
        
        result = reviewer.review(top10)
        report = reviewer.generate_report(result)
        
        print(f"\n复盘结果:")
        print(f"  胜率: {result['win_rate']:.1f}%")
        print(f"  平均涨幅: {result['avg_change']:.2f}%")
        for stock in result['stocks']:
            icon = '✅' if stock['is_win'] else '❌'
            print(f"  {icon} {stock['code']} {stock['name']}: {stock['change']:+.2f}%")
        
        if args.email:
            _send_email_report(report, get_config(), logger)
    else:
        print("没有找到预测历史文件")


def _build_email_report(results: list, top_n: int) -> str:
    """从 StockPredictor 扫描结果生成邮件报告文本"""
    from datetime import datetime
    
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    top = results[:top_n]
    
    report = f"""
{"=" * 65}
  AI量化交易系统 - 全A股扫描报告
  生成时间: {date_str}
  有效信号: {len(results)} 只 → 精选 Top {len(top)}
{"=" * 65}

{"─" * 65}
  Top {len(top)} 精选推荐
{"─" * 65}
"""
    for i, stock in enumerate(top, 1):
        exp = stock.get('expected_move', {})
        has_fund = stock.get('has_fundamental', False)
        report += f"""
{i:2d}. {stock['code']} {stock['name']}
    现价: ¥{stock['price']:.2f}  涨跌: {stock['change']:+.2f}%  评分: {stock['score']}
    信号: {stock.get('reasons', '')}
    RSI: {stock.get('tech_details', {}).get('rsi', 'N/A')}  """
        if has_fund:
            report += f" 技术分={stock.get('tech_score','N/A')} 基本面分={stock.get('fund_score','N/A')}"
        report += f"""
    预期涨幅: {exp.get('expected_pct', 0):+.2f}%  目标: ¥{exp.get('target_price', 0):.2f}  止损: ¥{exp.get('stop_loss', 0):.2f}
"""
    
    report += f"""
{"─" * 65}
  免责声明
{"─" * 65}
  以上分析基于技术指标+基本面+AI规则引擎，仅供参考，不构成投资建议。
  股市有风险，投资需谨慎。

  系统: stock-ai-monitor v0.1.0
{"=" * 65}
"""
    return report


def _send_email_report(report: str, config, logger) -> bool:
    """发送邮件报告"""
    from scheduler.email_bot import EmailBot
    
    email_cfg = config.email
    if not email_cfg.sender_email or not email_cfg.receiver_emails:
        logger.warning("邮件配置不完整，跳过发送")
        return False
    
    bot = EmailBot(
        smtp_server=email_cfg.smtp_server,
        smtp_port=email_cfg.smtp_port,
        sender_email=email_cfg.sender_email,
        sender_password=email_cfg.sender_password,
        receiver_emails=[r for r in email_cfg.receiver_emails if r],
    )
    
    from datetime import datetime
    subject = f"AI量化选股 - {datetime.now().strftime('%m-%d %H:%M')}"
    ok = bot.send(subject, report)
    if ok:
        logger.info(f"邮件发送成功 → {email_cfg.receiver_emails}")
    else:
        logger.warning("邮件发送失败")
    return ok
    
    logger = get_logger('CLI')
    logger.info("开始复盘...")
    
    reviewer = StockReviewer()
    
    # 从文件加载昨日预测
    import json
    from pathlib import Path
    
    pred_file = Path("data/predictions.json")
    if pred_file.exists():
        with open(pred_file, 'r') as f:
            predictions = json.load(f)
        
        result = reviewer.review(predictions)
        
        print(f"\n复盘结果:")
        print(f"  胜率: {result['win_rate']:.1f}%")
        print(f"  平均涨幅: {result['avg_change']:.2f}%")
        
        for stock in result['stocks']:
            icon = '✅' if stock['is_win'] else '❌'
            print(f"  {icon} {stock['code']} {stock['name']}: {stock['change']:+.2f}%")
    else:
        print("没有找到昨日预测记录")


def cmd_update(args):
    """更新策略权重"""
    from scheduler.predictor import StockPredictor
    
    logger = get_logger('CLI')
    logger.info("更新策略权重 (含基本面策略)...")
    
    predictor = StockPredictor()
    predictor.update_strategy_weights()
    
    print("✅ 策略权重更新完成 (8策略: 7技术面 + 1基本面)")
    print("\n当前权重:")
    strategy_labels = {
        'ma_cross': 'MA均线交叉', 'rsi_reversal': 'RSI反转',
        'macd_signal': 'MACD信号', 'kdj_signal': 'KDJ信号',
        'bollinger_band': '布林带', 'momentum': '动量策略',
        'volume_price': '量价关系', 'fundamental': '基本面评分'
    }
    for strategy, weight in sorted(predictor.evaluator.strategy_weights.items(),
                                    key=lambda x: x[1], reverse=True):
        label = strategy_labels.get(strategy, strategy)
        bar = '█' * int(weight * 20)
        print(f"  {label:<12} {weight:.3f} {bar}")
    logger.info("权重更新完成")


def cmd_search(args):
    """搜索GitHub策略"""
    from github_strategy_searcher import GitHubStrategySearcher
    
    logger = get_logger('CLI')
    logger.info("搜索GitHub策略...")
    
    searcher = GitHubStrategySearcher()
    strategies = searcher.search_strategies(force=args.force)
    
    print(f"\n找到 {len(strategies)} 个策略")
    print(searcher.get_strategy_report())


def cmd_refresh(args):
    """刷新股票池"""
    from scheduler.predictor import StockPredictor
    
    logger = get_logger('CLI')
    logger.info("刷新股票池...")
    
    predictor = StockPredictor()
    stocks = predictor.refresh_stock_pool()
    
    print(f"\n股票池刷新完成: {len(stocks)} 只股票")
    
    # 统计板块
    sectors = predictor.get_sector_list()
    print(f"\n板块分布:")
    for sector in sectors:
        stocks_in_sector = predictor.get_sector_stocks(sector)
        print(f"  {sector}: {len(stocks_in_sector)} 只")


def cmd_backtest(args):
    """回测"""
    from backtest_engine import BacktestEngine, BacktestConfig
    from strategies import get_strategy
    
    logger = get_logger('CLI')
    logger.info(f"开始回测 {args.stock}...")
    
    # 获取数据
    from scrapers import BaoStockScraper
    
    with BaoStockScraper() as scraper:
        # 这里需要实现获取历史数据的逻辑
        pass
    
    print("回测功能需要配合数据源使用")


def cmd_schedule(args):
    """启动定时任务"""
    from scheduler import Scheduler
    
    logger = get_logger('CLI')
    config = get_config()
    
    scheduler_config = {
        'push_type': config.schedule.push_type,
        'smtp_server': config.email.smtp_server,
        'smtp_port': config.email.smtp_port,
        'sender_email': config.email.sender_email,
        'sender_password': config.email.sender_password,
        'receiver_emails': config.email.receiver_emails,
    }
    
    scheduler = Scheduler(scheduler_config)
    
    print("=" * 60)
    print("股票预测定时任务")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"\n定时任务:")
    print(f"  {config.schedule.morning_review} - 早盘复盘")
    print(f"  {config.schedule.afternoon_predict} - 尾盘预测")
    print(f"\n推送方式: {config.schedule.push_type}")
    print(f"\n按 Ctrl+C 停止...")
    
    try:
        scheduler.run()
    except KeyboardInterrupt:
        print("\n定时任务已停止")


def cmd_test(args):
    """测试功能"""
    from scheduler import EmailBot
    
    config = get_config()
    
    print("发送测试邮件...")
    
    bot = EmailBot(
        smtp_server=config.email.smtp_server,
        smtp_port=config.email.smtp_port,
        sender_email=config.email.sender_email,
        sender_password=config.email.sender_password,
        receiver_emails=config.email.receiver_emails
    )
    
    content = f"""
📊 量化交易系统测试邮件

发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

系统功能:
1. 每日 {config.schedule.morning_review} 早盘复盘
2. 每日 {config.schedule.afternoon_predict} 尾盘预测

⚠️ 以上仅供参考，不构成投资建议
"""
    
    subject = f"📈 系统测试 - {datetime.now().strftime('%Y-%m-%d')}"
    result = bot.send(subject, content)
    
    if result:
        print("✅ 测试邮件发送成功！")
    else:
        print("❌ 邮件发送失败")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='量化交易系统',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    parser.add_argument('-q', '--quiet', action='store_true', help='静默模式')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # scan 命令
    scan_parser = subparsers.add_parser('scan', help='扫描市场 (含基本面评分)')
    scan_parser.add_argument('--top', type=int, default=10, help='显示前N个')
    scan_parser.add_argument('--all', action='store_true', help='全A股扫描')
    scan_parser.add_argument('--min-score', type=int, default=55, help='最低评分')
    scan_parser.add_argument('--fund-weight', type=float, default=0.3,
                             help='基本面权重 (0-1, 默认0.3)')
    scan_parser.add_argument('--email', action='store_true',
                             help='扫描完成后发送邮件报告')
    
    # review 命令
    review_parser = subparsers.add_parser('review', help='复盘昨日预测')
    review_parser.add_argument('--email', action='store_true', help='复盘完成后发送邮件报告')
    
    # update 命令
    subparsers.add_parser('update', help='更新策略权重')
    
    # search 命令
    search_parser = subparsers.add_parser('search', help='搜索GitHub策略')
    search_parser.add_argument('--force', action='store_true', help='强制更新')
    
    # refresh 命令
    subparsers.add_parser('refresh', help='刷新股票池')
    
    # backtest 命令
    bt_parser = subparsers.add_parser('backtest', help='回测策略')
    bt_parser.add_argument('stock', help='股票代码')
    bt_parser.add_argument('--strategy', default='ma', help='策略名称')
    
    # schedule 命令
    subparsers.add_parser('schedule', help='启动定时任务')
    
    # test 命令
    subparsers.add_parser('test', help='测试邮件发送')
    
    args = parser.parse_args()
    
    # 设置日志
    if args.verbose:
        setup_logging('DEBUG')
    elif args.quiet:
        setup_logging('WARNING')
    else:
        setup_logging('INFO')
    
    # 执行命令
    if args.command == 'scan':
        cmd_scan(args)
    elif args.command == 'review':
        cmd_review(args)
    elif args.command == 'backtest':
        cmd_backtest(args)
    elif args.command == 'schedule':
        cmd_schedule(args)
    elif args.command == 'test':
        cmd_test(args)
    elif args.command == 'update':
        cmd_update(args)
    elif args.command == 'search':
        cmd_search(args)
    elif args.command == 'refresh':
        cmd_refresh(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
