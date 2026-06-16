# GitHub Actions 部署指南

## 一、配置步骤

### 1. Fork 或 Clone 项目

```bash
git clone https://github.com/your-username/stock-ai-monitor.git
cd stock-ai-monitor
```

### 2. 配置 GitHub Secrets

进入仓库 → Settings → Secrets and variables → Actions → New repository secret

添加以下 Secrets：

| Secret名称 | 说明 | 示例 |
|------------|------|------|
| `EMAIL_SMTP_SERVER` | SMTP服务器 | `smtp.qq.com` |
| `EMAIL_SMTP_PORT` | SMTP端口 | `465` |
| `EMAIL_SENDER` | 发件人邮箱 | `your_email@qq.com` |
| `EMAIL_PASSWORD` | 邮箱授权码 | `your_authorization_code` |
| `EMAIL_RECEIVERS` | 收件人邮箱（多个用逗号分隔） | `receiver1@qq.com,receiver2@qq.com` |

### 3. 启用 GitHub Actions

进入仓库 → Actions → 启用 Actions

## 二、定时任务说明

| 北京时间 | UTC时间 | 任务 | 说明 |
|----------|---------|------|------|
| 02:00 | 18:00 | 刷新股票池 | 每日更新A股列表 |
| 10:50 | 02:50 | 早盘复盘 | 复盘昨日预测 |
| 15:30 | 07:30 | 尾盘预测 | 全A股扫描预测 |
| 16:00 | 08:00 | 策略更新 | 更新策略权重 |
| 周日 20:00 | 周日 12:00 | GitHub策略搜索 | 搜索新策略 |

## 三、手动触发

1. 进入仓库 → Actions
2. 选择 "Stock Analysis System"
3. 点击 "Run workflow"
4. 选择任务类型：
   - `scan`: 全A股扫描
   - `refresh`: 刷新股票池
   - `test`: 测试邮件

## 四、查看结果

### 1. 查看运行日志

进入 Actions → 点击对应的 workflow run → 查看日志

### 2. 查看邮件

扫描完成后，结果会发送到配置的收件人邮箱

### 3. 查看报告

每次运行会生成报告，保存在 Actions → Artifacts 中

## 五、常见问题

### Q1: 定时任务没有运行？

检查：
1. 仓库是否启用了 Actions
2. cron 表达式是否正确（UTC时间）
3. 仓库是否有活动（60天无活动会自动禁用）

### Q2: 邮件发送失败？

检查：
1. Secrets 配置是否正确
2. 邮箱授权码是否正确
3. SMTP 服务器和端口是否正确

### Q3: 如何修改定时时间？

编辑 `.github/workflows/stock_analysis.yml` 中的 cron 表达式：

```yaml
schedule:
  - cron: '30 7 * * 1-5'  # UTC 07:30 = 北京时间 15:30
```

### Q4: 如何添加更多股票？

1. 手动触发 `refresh` 任务
2. 或者等待每日自动刷新

## 六、注意事项

1. **时间格式**：GitHub Actions 使用 UTC 时间，北京时间 = UTC + 8
2. **运行限制**：免费账户每月有 2000 分钟的 Actions 时间
3. **网络限制**：GitHub Actions 可以访问外网，适合调用API
4. **数据持久化**：使用 Artifacts 保存报告，保留30天

## 七、进阶配置

### 添加钉钉通知

在 `.github/workflows/stock_analysis.yml` 中添加：

```yaml
- name: Send DingTalk notification
  if: success()
  uses: zcong1993/dingtalk-action@master
  with:
    dingtalk-token: ${{ secrets.DINGTALK_TOKEN }}
    body: |
      {
        "msgtype": "markdown",
        "markdown": {
          "title": "股票分析报告",
          "text": "## 扫描完成\n\n请查看邮箱获取详细报告"
        }
      }
```

### 添加微信通知

使用 Server酱 或 PushPlus 等服务：

```yaml
- name: Send WeChat notification
  if: success()
  run: |
    curl -X POST "https://sctapi.ftqq.com/${{ secrets.SERVERCHAN_KEY }}.send" \
      -d "title=股票分析报告&desp=扫描完成，请查看邮箱"
```
