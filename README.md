# AI量化交易系统

基于多平台信号聚合的A股量化分析系统，支持技术面+基本面多因子选股。

## 功能特性

- 📊 **全A股扫描** - 5000+只股票自动化分析
- 📈 **多策略分析** - 7种技术策略 + 基本面(PE/PB/ROE/增长)综合评分
- 🔔 **实时监测** - 止损止盈自动提醒
- 📧 **邮件推送** - 每日报告自动发送
- 🤖 **GitHub Actions** - 全自动化运行

## 分析流程

系统分两个阶段完成全A股选股：**多因子快筛** 和 **深度分析**。

### 阶段一：多因子快筛

适用于全量股票（5000+只），只用实时数据，无K线下载开销。

**数据来源：**
| 数据 | 来源 | 耗时 |
|------|------|------|
| 实时行情 (价格/涨跌/成交额/振幅) | 新浪 `hq.sinajs.cn` 批量API | ~6s/全量 |
| 基本面 (PE/PB/ROE/利润增长) | AKShare `stock_yjbb_em` 批量API | ~8s/11469只 |

**准入关卡（OR 逻辑，满足任一即放行）：**

| 条件 | 阈值 | 逻辑 |
|------|------|------|
| ① 常规技术通过 | `change_pct >= -3%` | 大多数正常股票直接通过 |
| ② 价值兜底 | `change >= -5%` 且 (PE<15 或 ROE>15%) | 小跌但基本面好的不遗漏 |
| ③ 深蹲抄底 | `change >= -8%` 且 (PE<10 且 ROE>15%) | 大跌但极度低估的进入分析 |
| ④ 活跃优质 | 成交额>5000万 且 (ROE>20% 或 利润增长>30%) | 高质量活跃股不遗漏 |

**多因子评分（技术面40% + 基本面60%）：**

| 类别 | 因子 | 得分规则 |
|------|------|---------|
| 技术面 | 涨跌幅 (max 40) | -8~-5%:5, -5~-3%:15, -3~0%:25, 0~2%:35, 2~5%:40, 5~8%:30 |
| 技术面 | 振幅 (max 10) | >5%:10, >2%:5 |
| 技术面 | 开盘位置 (max 10) | 高开高走:10 |
| 技术面 | 成交额 (max 10) | >1亿:10, >3000万:5 |
| 基本面 | PE市盈率 (max 25) | 0~10:25, 10~20:15, 20~40:5, >40:0 |
| 基本面 | PB市净率 (max 15) | <1:15, 1~3:10, 3~5:5, >5:0 |
| 基本面 | ROE (max 25) | >20%:25, 10~20%:15, 5~10%:5 |
| 基本面 | 利润增长 (max 25) | >50%:25, 20~50%:15, 0~20%:5 |

通过关卡的股票按评分降序排列，取前 `max_stocks` 只（默认500）进入深度分析。

### 阶段二：深度分析

对快筛入选的股票逐只进行完整分析。

**数据来源：**
| 数据 | 来源 | 耗时 |
|------|------|------|
| 历史K线 (60日) | 新浪K线API | ~0.2s/只 |
| 基本面缓存 | AKShare `stock_yjbb_em` (已缓存) | 内存查表 |

**技术面策略（7个，由策略评估器动态加权）：**

| 策略 | 信号判定 | 说明 |
|------|---------|------|
| `ma_cross` | MA5>MA10>MA20 → buy | 均线多头排列 |
| `rsi_reversal` | RSI<30 → strong_buy, <40 → buy | RSI超卖反转 |
| `macd_signal` | MACD > 0 → buy | MACD金叉 |
| `kdj_signal` | RSV < 20 → buy | KDJ超卖 |
| `bollinger_band` | 跌破下轨 → buy | 布林带支撑 |
| `momentum` | 20日涨幅 > 5% → buy | 动量趋势 |
| `volume_price` | 放量(>1.3x)且涨价 → buy | 量价配合 |

**基本面评分（第8策略 `fundamental`）：**

| 因子 | 得分规则 |
|------|---------|
| PE 市盈率 (15分) | <15:+15, <25:+10, >100:-15 |
| PB 市净率 (15分) | <1:+15, <2:+10, >10:-10 |
| ROE (15分) | >20%:+15, >10%:+10 |
| 利润增长 (15分) | >30%:+15, >10%:+10, <-10%:-10 |

**最终评分公式：**
```
final_score = tech_score × (1 - fundamental_weight) + fund_score × fundamental_weight
```
默认 `fundamental_weight = 0.3`（可通过 `--fund-weight` 参数调整）。

预期收益、止损位基于技术指标波动率计算，止损默认为当前价的 -5%。

## 数据源架构

| 职责 | 来源 | 方式 |
|------|------|------|
| 实时行情 (5000+只) | 新浪 `hq.sinajs.cn` | `_get_realtime_batch()` 批量 |
| 历史K线 (单只) | 新浪K线API | `_get_history_data()` 串行 |
| 基本面 (PE/PB/ROE/增长) | **AKShare** `stock_yjbb_em` | `_load_fundamental_batch()` 全量一次性 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
# 复制配置模板
cp config/settings.template.yaml config/settings.yaml

# 编辑配置文件，填入你的邮箱信息
vim config/settings.yaml
```

### 3. 运行

```bash
# 扫描市场（按板块）
python cli.py scan --top 10

# 全A股扫描
python cli.py scan --all --min-score 55

# 调整基本面权重（0~1）
python cli.py scan --fund-weight 0.5

# 更新策略权重（含基本面策略）
python cli.py update

# 启动定时任务
python cli.py schedule
```

## GitHub Actions 自动化

### 配置 Secrets

1. 进入仓库 → Settings → Secrets → Actions
2. 添加以下 Secrets：

| Secret名称 | 说明 |
|------------|------|
| `EMAIL_SMTP_SERVER` | SMTP服务器 (如: smtp.qq.com) |
| `EMAIL_SMTP_PORT` | SMTP端口 (如: 587) |
| `EMAIL_SENDER` | 发件人邮箱 |
| `EMAIL_PASSWORD` | 邮箱授权码 |
| `EMAIL_RECEIVERS` | 收件人邮箱 |

### 定时任务

| 北京时间 | 任务 |
|----------|------|
| 02:00 | 刷新股票池 |
| 14:00 | 尾盘预测 |
| 16:00 | 复盘 + 策略更新 |
| 周日 20:00 | GitHub策略搜索 |

### 手动触发

进入 Actions → Run workflow → 选择任务

## 项目结构

```
stock-ai-monitor/
├── .github/workflows/         # GitHub Actions
├── config/                    # 配置文件
│   ├── settings.template.yaml # 配置模板
│   └── settings.yaml         # 真实配置（不提交）
├── scheduler/                 # 调度器 + 预测器 + 复盘 + 邮件
├── scrapers/                  # 数据爬虫 (baostock/akshare/eastmoney/tonghuashun)
├── signal_aggregator/         # 多平台信号聚合
├── llm/                       # LLM大模型接口
├── strategies.py              # 15个技术策略
├── backtest_engine.py         # 回测引擎
├── strategy_evaluator.py      # 策略评估 (8策略含基本面)
├── ai_analyzer.py             # AI分析引擎
├── memory_system.py           # AI记忆系统
├── tests/                     # 测试用例
├── cli.py                     # CLI入口
└── requirements.txt           # 依赖
```

## CLI 命令

```bash
# 扫描市场（含基本面评分）
python cli.py scan --top 10

# 全A股扫描
python cli.py scan --all --min-score 50

# 调整基本面权重
python cli.py scan --fund-weight 0.5

# 刷新股票池
python cli.py refresh

# 更新策略权重（8策略：7技术面+1基本面）
python cli.py update

# 测试邮件
python cli.py test

# 启动定时任务
python cli.py schedule
```

## 策略权重

系统自动追踪8个策略的历史表现并动态调整权重：

| 策略 | 类型 | 说明 |
|------|------|------|
| MA均线交叉 | 技术面 | 短期MA上穿长期MA |
| RSI反转 | 技术面 | 超买超卖反转信号 |
| MACD信号 | 技术面 | MACD金叉死叉 |
| KDJ信号 | 技术面 | KDJ超买超卖 |
| 布林带 | 技术面 | 价格触及上下轨 |
| 动量策略 | 技术面 | N日收益率趋势 |
| 量价关系 | 技术面 | 成交量与价格配合 |
| 基本面评分 | 基本面 | PE/PB/ROE/利润增长综合 |

> 运行 `python cli.py update` 后，系统基于近30天历史表现自动调整各策略权重。

## 安全说明

- ✅ 配置文件已加入 `.gitignore`，不会被提交
- ✅ 敏感信息通过 GitHub Secrets 存储
- ✅ 配置模板可安全公开

## 免责声明

⚠️ **本系统仅供学习和研究使用，不构成投资建议。**

- 股市有风险，投资需谨慎
- 历史数据不代表未来表现
- 请勿将本系统作为唯一投资依据

## License

MIT License
