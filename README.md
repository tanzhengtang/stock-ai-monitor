# AI量化交易系统

基于多平台信号聚合的A股量化分析系统

## 功能特性

- 📊 **全A股扫描** - 5000+只股票自动分析
- 📈 **多策略分析** - 7种量化策略综合评分
- 🔔 **实时监测** - 止损止盈自动提醒
- 📧 **邮件推送** - 每日报告自动发送
- 🤖 **GitHub Actions** - 全自动化运行

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/stock-ai-monitor.git
cd stock-ai-monitor
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置

```bash
# 复制配置模板
cp config/settings.template.yaml config/settings.yaml

# 编辑配置文件，填入你的邮箱信息
vim config/settings.yaml
```

### 4. 运行

```bash
# 扫描市场
python cli.py scan --top 10

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
| `EMAIL_SMTP_PORT` | SMTP端口 (如: 465) |
| `EMAIL_SENDER` | 发件人邮箱 |
| `EMAIL_PASSWORD` | 邮箱授权码 |
| `EMAIL_RECEIVERS` | 收件人邮箱 |

### 定时任务

| 北京时间 | 任务 |
|----------|------|
| 02:00 | 刷新股票池 |
| 10:50 | 早盘复盘 |
| **15:30** | **全A股扫描预测** |
| 16:00 | 策略更新 |
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
├── scheduler/                 # 定时任务
├── scrapers/                  # 爬虫模块
├── signal_aggregator/         # 信号聚合
├── trading/                   # 量化交易
├── tests/                     # 测试用例
├── cli.py                    # CLI入口
└── requirements.txt          # 依赖
```

## CLI 命令

```bash
# 扫描市场
python cli.py scan --top 10

# 全A股扫描
python cli.py scan --all --min-score 55

# 刷新股票池
python cli.py refresh

# 更新策略权重
python cli.py update

# 测试邮件
python cli.py test

# 启动定时任务
python cli.py schedule
```

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
