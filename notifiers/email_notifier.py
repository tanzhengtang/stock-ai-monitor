"""
邮件通知器
通过邮件发送消息
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

from .base_notifier import BaseNotifier


class EmailNotifier(BaseNotifier):
    """邮件通知器
    
    通过SMTP发送邮件通知。
    
    配置步骤：
    1. 获取SMTP服务器地址和端口
    2. 获取发件人邮箱和密码
    3. 设置收件人邮箱列表
    """

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        sender_email: str,
        sender_password: str,
        receiver_emails: List[str]
    ):
        """
        初始化邮件通知器
        
        Args:
            smtp_server: SMTP服务器地址
            smtp_port: SMTP服务器端口
            sender_email: 发件人邮箱
            sender_password: 发件人邮箱密码或授权码
            receiver_emails: 收件人邮箱列表
        """
        super().__init__(name="EmailNotifier")
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.receiver_emails = receiver_emails

    def send(self, message: str, title: Optional[str] = None) -> bool:
        """
        发送邮件
        
        Args:
            message: 消息内容
            title: 邮件标题
            
        Returns:
            是否发送成功
        """
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = title or 'AI信号分析报告'
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.receiver_emails)
            
            # 添加HTML内容
            html_content = self._markdown_to_html(message)
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # 发送邮件
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.sender_email, self.sender_password)
                server.sendmail(
                    self.sender_email,
                    self.receiver_emails,
                    msg.as_string()
                )
            
            self.logger.info(f"邮件发送成功，收件人: {self.receiver_emails}")
            return True
            
        except Exception as e:
            self.logger.error(f"邮件发送失败: {e}")
            return False

    def _markdown_to_html(self, markdown_text: str) -> str:
        """
        将Markdown转换为HTML
        
        Args:
            markdown_text: Markdown文本
            
        Returns:
            HTML文本
        """
        # 简单的Markdown转HTML
        html = markdown_text
        
        # 标题
        html = html.replace('# ', '<h1>').replace('\n', '</h1>\n', 1) if '# ' in html else html
        html = html.replace('## ', '<h2>').replace('\n', '</h2>\n', 1) if '## ' in html else html
        html = html.replace('### ', '<h3>').replace('\n', '</h3>\n', 1) if '### ' in html else html
        
        # 加粗
        import re
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
        
        # 换行
        html = html.replace('\n', '<br>')
        
        # 包装成HTML
        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                h1, h2, h3 {{ color: #2c3e50; }}
                strong {{ color: #e74c3c; }}
                pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>
        """
