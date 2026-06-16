# AI信号监控系统

用于聚合多个平台的AI股票信号，生成共识信号和风险评估。

## 功能特性

- **多平台信号聚合**: 支持东方财富、同花顺、AKShare、BaoStock等平台
- **基本面分析**: 包含市盈率、市净率、ROE、毛利率等财务指标
- **共识分析**: 通过投票、加权评分、置信度加权等多种方法分析共识
- **风险评估**: 评估信号的风险等级，过滤高风险信号
- **定时任务**: 支持定时扫描和报告生成
- **通知推送**: 支持控制台、钉钉、邮件等通知方式

## 安装依赖

```bash
pip install -r requirements.txt
```

## 快速开始

### 1. 执行一次扫描

```bash
# 扫描指定股票
python main.py --stocks 600519 600900

# 扫描配置文件中的股票
python main.py --once
```

### 2. 运行定时任务

```bash
python main.py --schedule
```

### 3. 使用Python API

```python
from scrapers import AKShareScraper, BaoStockScraper
from signal_aggregator import SignalAggregator

aggregator = SignalAggregator()

# 使用AKShare获取财务数据
with AKShareScraper() as scraper:
    signal = scraper.get_stock_signal('600519')
    if signal:
        aggregator.add_signal(signal)

# 使用BaoStock获取行情数据
with BaoStockScraper() as scraper:
    signal = scraper.get_stock_signal('600519')
    if signal:
        aggregator.add_signal(signal)

# 生成报告
result = aggregator.aggregate_all()
print(result.to_report())
```

## 核心模块

### 爬虫模块 (scrapers/)

| 爬虫 | 数据类型 | 状态 |
|------|----------|------|
| EastMoneyScraper | 行情数据 | ⚠️ 网络问题 |
| TongHuaShunScraper | 行情数据 | ✅ 可用 |
| AKShareScraper | 行情+财务 | ✅ 可用 |
| BaoStockScraper | 行情+基本面 | ✅ 可用 |

### 信号聚合模块 (signal_aggregator/)

- `SignalAggregator`: 信号聚合器
- `ConsensusAnalyzer`: 共识分析器
- `RiskAnalyzer`: 风险分析器

### 通知推送模块 (notifiers/)

- `ConsoleNotifier`: 控制台输出
- `DingTalkNotifier`: 钉钉机器人推送
- `EmailNotifier`: 邮件推送

## 配置文件

编辑 `config/settings.yaml` 配置系统参数：

```yaml
# 监控股票列表
watchlist:
  - code: "600519"
    name: "贵州茅台"
  - code: "600900"
    name: "长江电力"

# 定时任务配置
schedule:
  enabled: true
  morning_scan: "09:15"
  midday_scan: "11:30"
  afternoon_scan: "14:30"
  evening_report: "15:30"

# 通知配置
notification:
  dingtalk:
    enabled: false
    webhook_url: "your_webhook_url"
  email:
    enabled: false
    smtp_server: "smtp.gmail.com"
    sender_email: "your_email@gmail.com"
    sender_password: "your_password"
    receiver_emails:
      - "receiver@example.com"
```

## 财务数据指标

| 指标 | 说明 | 来源 |
|------|------|------|
| pe | 市盈率（动态） | BaoStock |
| pb | 市净率 | BaoStock |
| roe | 净资产收益率 | AKShare |
| gross_margin | 毛利率 | AKShare |
| net_margin | 净利率 | AKShare |
| debt_ratio | 资产负债率 | AKShare |
| revenue_growth | 营收增长率 | AKShare |
| net_profit_growth | 净利润增长率 | AKShare |
| operating_cashflow | 经营现金流 | AKShare |

## 评分算法

评分基于以下指标：

- **技术面指标 (30%)**: 涨跌幅、换手率、成交量
- **估值指标 (30%)**: 市盈率、市净率
- **盈利能力指标 (25%)**: ROE、毛利率、净利率
- **成长性指标 (15%)**: 营收增长率、净利润增长率

## 运行测试

```bash
# 运行所有测试
python -m unittest discover tests -v

# 运行爬虫测试
python -m unittest tests.test_scrapers -v

# 运行聚合器测试
python -m unittest tests.test_aggregator -v
```

## 项目结构

```
stock-ai-monitor/
├── signal_aggregator/           # 信号聚合模块
│   ├── models.py               # 数据模型
│   ├── aggregator.py           # 聚合器核心
│   └── analyzers/              # 分析器
├── scrapers/                    # 爬虫模块
│   ├── base_scraper.py         # 爬虫基类
│   ├── eastmoney.py            # 东方财富爬虫
│   ├── tonghuashun.py          # 同花顺爬虫
│   ├── akshare_scraper.py      # AKShare爬虫
│   └── baostock_scraper.py     # BaoStock爬虫
├── notifiers/                   # 通知推送模块
│   ├── base_notifier.py        # 通知基类
│   ├── console_notifier.py     # 控制台通知
│   ├── dingtalk_notifier.py    # 钉钉通知
│   └── email_notifier.py       # 邮件通知
├── config/                      # 配置文件
│   ├── settings.yaml           # 主配置
│   └── cookies.yaml            # Cookie配置
├── tests/                       # 测试用例
├── main.py                      # 主程序入口
├── requirements.txt             # 依赖
└── README.md                    # 说明文档
```

## 使用示例

### 扫描指定股票

```bash
python main.py --stocks 600519 600900 000858
```

### 运行定时监控

```bash
python main.py --schedule
```

### 查看帮助

```bash
python main.py --help
```

## 注意事项

1. 本系统仅用于信号分析，不提供投资建议
2. 投资有风险，决策需谨慎
3. 请遵守各平台的使用条款
4. 建议使用代理IP避免被封禁
