"""
邮件推送模块
通过SMTP发送邮件
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Optional
import logging


class EmailBot:
    """邮件推送
    
    功能：
    1. 发送文本邮件
    2. 发送HTML邮件
    3. 支持多个收件人
    """

    def __init__(
        self,
        smtp_server: str = '',
        smtp_port: int = 465,
        sender_email: str = '',
        sender_password: str = '',
        receiver_emails: List[str] = None
    ):
        """
        初始化邮件推送
        
        Args:
            smtp_server: SMTP服务器地址
            smtp_port: SMTP端口
            sender_email: 发件人邮箱
            sender_password: 发件人密码/授权码
            receiver_emails: 收件人邮箱列表
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.receiver_emails = receiver_emails or []
        self.logger = logging.getLogger('EmailBot')

    def send(self, subject: str, content: str, is_html: bool = False) -> bool:
        """
        发送邮件
        
        Args:
            subject: 邮件主题
            content: 邮件内容
            is_html: 是否HTML格式
            
        Returns:
            是否发送成功
        """
        if not self.smtp_server or not self.sender_email:
            self.logger.warning("邮件配置不完整")
            print(f"[邮件预览] 主题: {subject}")
            print(f"[邮件预览] 内容:\n{content}")
            return False
        
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.receiver_emails)
            
            # 添加内容
            if is_html:
                msg.attach(MIMEText(content, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(content, 'plain', 'utf-8'))
            
            # 发送
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.sender_email, self.sender_password)
                server.sendmail(
                    self.sender_email,
                    self.receiver_emails,
                    msg.as_string()
                )
            
            self.logger.info(f"邮件发送成功: {subject}")
            return True
            
        except Exception as e:
            self.logger.error(f"邮件发送失败: {e}")
            return False

    def send_stock_report(self, report_type: str, content: str) -> bool:
        """
        发送股票报告
        
        Args:
            report_type: 报告类型 ('review'复盘, 'predict'预测)
            content: 报告内容
            
        Returns:
            是否发送成功
        """
        # 生成主题
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        if report_type == 'review':
            subject = f"📊 股票早盘复盘 - {date_str}"
        elif report_type == 'predict':
            subject = f"🔮 明日股票预测 - {date_str}"
        else:
            subject = f"📈 股票分析报告 - {date_str}"
        
        # 转换为HTML
        html_content = self._to_html(content)
        
        return self.send(subject, html_content, is_html=True)

    def _to_html(self, content: str) -> str:
        """
        将文本转换为HTML
        
        Args:
            content: 文本内容
            
        Returns:
            HTML内容
        """
        # 替换换行符
        html = content.replace('\n', '<br>')
        
        # 替换特殊标记
        html = html.replace('✅', '<span style="color: green;">✅</span>')
        html = html.replace('❌', '<span style="color: red;">❌</span>')
        html = html.replace('⚠️', '<span style="color: orange;">⚠️</span>')
        
        # 包装成HTML
        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .content {{
            background-color: #fff;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        .footer {{
            margin-top: 20px;
            font-size: 12px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h2>股票分析报告</h2>
    </div>
    <div class="content">
        {html}
    </div>
    <div class="footer">
        <p>⚠️ 以上仅供参考，不构成投资建议</p>
        <p>投资有风险，入市需谨慎</p>
    </div>
</body>
</html>
"""
        return html_template


# 测试代码
if __name__ == '__main__':
    # 测试邮件
    bot = EmailBot(
        smtp_server='smtp.qq.com',
        smtp_port=465,
        sender_email='your_email@qq.com',
        sender_password='your_password',
        receiver_emails=['receiver@example.com']
    )
    
    test_content = """
📊 【早盘复盘】2026-06-16

昨日推荐股票表现：
✅ 600519 贵州茅台: +1.50%
❌ 601318 中国平安: -0.80%
✅ 600036 招商银行: +0.30%

整体胜率：66.7%
平均涨幅：+0.33%

⚠️ 以上仅供参考，不构成投资建议
"""
    
    print("测试邮件预览：")
    print(test_content)
    
    # 实际发送需要配置邮箱
    # bot.send_stock_report('review', test_content)
