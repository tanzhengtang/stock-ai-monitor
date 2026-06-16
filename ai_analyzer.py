"""
AI分析器模块
使用大语言模型进行股票分析，带有约束提示词
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime

from config.ai_prompts import (
    get_system_prompt,
    get_user_message,
    get_risk_warning,
    validate_response,
    FORBIDDEN_WORDS,
    RECOMMENDED_WORDS
)
from signal_aggregator.models import AggregatedSignal, SignalType
from llm import BaseLLM, DeepSeekLLM, OpenAILLM, LocalLLM
from memory_system import MemorySystem


class AIAnalyzer:
    """AI分析器
    
    使用大语言模型进行股票分析，带有约束提示词。
    
    支持多种大模型：
    - DeepSeek
    - OpenAI
    - 本地模型（Ollama）
    - 基于规则的分析（无需API）
    """

    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        model_type: str = "rule",
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        memory_path: str = "data/memory"
    ):
        """
        初始化AI分析器
        
        Args:
            llm: 大模型实例
            model_type: 模型类型 ('deepseek', 'openai', 'local', 'rule')
            api_key: API密钥
            base_url: API基础URL
            model: 模型名称
                - DeepSeek: 'deepseek-chat', 'deepseek-reasoner', 'deepseek-coder'
                - OpenAI: 'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'
                - Local: 'qwen2.5:7b', 'llama3.1:8b' 等
            memory_path: 记忆系统存储路径
        """
        self.logger = logging.getLogger('AIAnalyzer')
        self.system_prompt = get_system_prompt()
        
        # 初始化记忆系统
        self.memory = MemorySystem(storage_path=memory_path)
        
        # 初始化大模型
        if llm:
            self.llm = llm
        elif model_type == "deepseek":
            # 默认使用 deepseek-chat，适合股票分析
            self.llm = DeepSeekLLM(api_key=api_key, base_url=base_url, model=model or "deepseek-chat")
        elif model_type == "deepseek-reasoner":
            # 使用推理模型，适合复杂分析
            self.llm = DeepSeekLLM(api_key=api_key, base_url=base_url, model="deepseek-reasoner")
        elif model_type == "openai":
            self.llm = OpenAILLM(api_key=api_key, base_url=base_url, model=model)
        elif model_type == "local":
            self.llm = LocalLLM(base_url=base_url, model=model)
        else:
            self.llm = None
        
        self.model_type = model_type

    def analyze_stock(
        self,
        stock_code: str,
        stock_name: str,
        current_price: float,
        change_pct: float,
        volume: float,
        turnover: float,
        ma5: float,
        ma10: float,
        ma20: float,
        macd: str,
        rsi: float,
        kdj: str,
        aggregated_signal: Optional[AggregatedSignal] = None
    ) -> Dict:
        """
        分析股票
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            current_price: 当前价格
            change_pct: 涨跌幅
            volume: 成交量
            turnover: 换手率
            ma5: 5日均线
            ma10: 10日均线
            ma20: 20日均线
            macd: MACD指标
            rsi: RSI指标
            kdj: KDJ指标
            aggregated_signal: 聚合信号
            
        Returns:
            分析结果
        """
        # 优先使用大模型分析
        if self.llm:
            try:
                return self._llm_analysis(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    current_price=current_price,
                    change_pct=change_pct,
                    volume=volume,
                    turnover=turnover,
                    ma5=ma5,
                    ma10=ma10,
                    ma20=ma20,
                    macd=macd,
                    rsi=rsi,
                    kdj=kdj,
                    aggregated_signal=aggregated_signal
                )
            except Exception as e:
                self.logger.warning(f"大模型分析失败，回退到规则分析: {e}")
        
        # 回退到规则分析
        return self._rule_based_analysis(
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=current_price,
            change_pct=change_pct,
            volume=volume,
            turnover=turnover,
            ma5=ma5,
            ma10=ma10,
            ma20=ma20,
            macd=macd,
            rsi=rsi,
            kdj=kdj,
            aggregated_signal=aggregated_signal
        )

    def _llm_analysis(
        self,
        stock_code: str,
        stock_name: str,
        current_price: float,
        change_pct: float,
        volume: float,
        turnover: float,
        ma5: float,
        ma10: float,
        ma20: float,
        macd: str,
        rsi: float,
        kdj: str,
        aggregated_signal: Optional[AggregatedSignal] = None
    ) -> Dict:
        """
        使用大模型进行分析
        """
        # 生成用户消息
        user_message = get_user_message(
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=current_price,
            change_pct=change_pct,
            volume=volume,
            turnover=turnover,
            ma5=ma5,
            ma10=ma10,
            ma20=ma20,
            macd=macd,
            rsi=rsi,
            kdj=kdj
        )
        
        # 添加聚合信号信息
        if aggregated_signal:
            user_message += f"\n\n多平台信号汇总："
            user_message += f"\n- 共识信号：{aggregated_signal.consensus.value}"
            user_message += f"\n- 综合评分：{aggregated_signal.weighted_score:.1f}"
            user_message += f"\n- 置信度：{aggregated_signal.confidence:.1%}"
            user_message += f"\n- 风险等级：{aggregated_signal.risk_level}"
        
        # 添加历史分析记录
        stock_history = self.memory.get_stock_history(stock_code)
        if stock_history:
            user_message += f"\n\n该股票历史分析记录："
            for record in stock_history[-3:]:  # 最近3条
                user_message += f"\n- {record.content}"
        
        # 获取个性化提示词
        personalized_prompt = self.memory.generate_personalized_prompt()
        
        # 组合系统提示词
        full_system_prompt = self.system_prompt + "\n\n" + personalized_prompt
        
        # 调用大模型
        response = self.llm.chat_with_system(
            system_prompt=full_system_prompt,
            user_message=user_message,
            temperature=0.3,  # 低温度以获得更稳定的输出
            max_tokens=2000
        )
        
        # 验证回复
        is_valid, reason = validate_response(response)
        if not is_valid:
            self.logger.warning(f"大模型回复不符合约束: {reason}")
            # 添加风险提示
            response += "\n\n⚠️ 免责声明：以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。"
        
        # 解析回复
        analysis = self._parse_llm_response(
            response=response,
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=current_price,
            aggregated_signal=aggregated_signal
        )
        
        # 记录分析历史
        self.memory.record_analysis(
            stock_code=stock_code,
            stock_name=stock_name,
            signal_type=analysis['signal_type'],
            score=analysis['tech_score'],
            reasons=analysis['reasons']
        )
        
        return analysis

    def _parse_llm_response(
        self,
        response: str,
        stock_code: str,
        stock_name: str,
        current_price: float,
        aggregated_signal: Optional[AggregatedSignal] = None
    ) -> Dict:
        """
        解析大模型回复
        """
        # 尝试从回复中提取信号类型
        signal_type = "hold"
        confidence = "medium"
        
        if "买入" in response or "看多" in response or "🟢" in response:
            signal_type = "buy"
        elif "卖出" in response or "看空" in response or "🔴" in response:
            signal_type = "sell"
        else:
            signal_type = "hold"
        
        # 提取置信度
        if "高" in response and "置信" in response:
            confidence = "high"
        elif "低" in response and "置信" in response:
            confidence = "low"
        
        # 计算止损止盈
        if signal_type == "buy":
            stop_loss = current_price * 0.97
            target_price = current_price * 1.06
            position_size = 20 if confidence == "high" else 10
        elif signal_type == "sell":
            stop_loss = current_price * 1.03
            target_price = current_price * 0.97
            position_size = 0
        else:
            stop_loss = 0
            target_price = 0
            position_size = 0
        
        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'signal_type': signal_type,
            'confidence': confidence,
            'tech_score': aggregated_signal.weighted_score if aggregated_signal else 50,
            'reasons': [response],  # 完整回复作为原因
            'risks': ["投资有风险，入市需谨慎", "以上分析仅供参考，不构成投资建议"],
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'stop_loss_pct': 3.0 if signal_type == "buy" else 0,
            'target_price': target_price,
            'target_pct': 6.0 if signal_type == "buy" else 0,
            'position_size': position_size,
            'timestamp': datetime.now().isoformat(),
            'llm_response': response,
            'model_type': self.model_type,
            'disclaimer': "以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。"
        }

    def _rule_based_analysis(
        self,
        stock_code: str,
        stock_name: str,
        current_price: float,
        change_pct: float,
        volume: float,
        turnover: float,
        ma5: float,
        ma10: float,
        ma20: float,
        macd: str,
        rsi: float,
        kdj: str,
        aggregated_signal: Optional[AggregatedSignal] = None
    ) -> Dict:
        """
        基于规则的分析
        """
        # 计算技术指标得分
        tech_score = 0
        reasons = []
        risks = []
        
        # 1. 均线分析
        if current_price > ma5 > ma10 > ma20:
            tech_score += 20
            reasons.append("均线多头排列，趋势向上")
        elif current_price < ma5 < ma10 < ma20:
            tech_score -= 20
            reasons.append("均线空头排列，趋势向下")
        else:
            reasons.append("均线交织，方向不明")
        
        # 2. RSI分析
        if rsi < 30:
            tech_score += 15
            reasons.append(f"RSI={rsi:.1f}，超卖区域，可能反弹")
        elif rsi > 70:
            tech_score -= 15
            reasons.append(f"RSI={rsi:.1f}，超买区域，注意回调风险")
            risks.append("RSI超买，存在回调风险")
        else:
            reasons.append(f"RSI={rsi:.1f}，处于正常区间")
        
        # 3. 涨跌幅分析
        if 0 < change_pct < 3:
            tech_score += 10
            reasons.append(f"涨幅{change_pct:.2f}%，温和上涨")
        elif change_pct > 5:
            tech_score += 5
            reasons.append(f"涨幅{change_pct:.2f}%，涨幅较大")
            risks.append("涨幅较大，注意追高风险")
        elif -3 < change_pct < 0:
            tech_score -= 5
            reasons.append(f"跌幅{change_pct:.2f}%，小幅调整")
        elif change_pct < -5:
            tech_score -= 15
            reasons.append(f"跌幅{change_pct:.2f}%，跌幅较大")
            risks.append("跌幅较大，注意止损")
        
        # 4. 换手率分析
        if 3 < turnover < 10:
            tech_score += 10
            reasons.append(f"换手率{turnover:.2f}%，交投活跃")
        elif turnover > 15:
            tech_score += 5
            reasons.append(f"换手率{turnover:.2f}%，换手过高")
            risks.append("换手率过高，注意筹码松动")
        
        # 5. 聚合信号分析
        if aggregated_signal:
            if aggregated_signal.consensus in [SignalType.STRONG_BUY, SignalType.BUY]:
                tech_score += 15
                reasons.append(f"多平台看多信号，评分{aggregated_signal.weighted_score:.1f}")
            elif aggregated_signal.consensus in [SignalType.SELL, SignalType.STRONG_SELL]:
                tech_score -= 15
                reasons.append(f"多平台看空信号，评分{aggregated_signal.weighted_score:.1f}")
                risks.append("多平台看空，建议谨慎")
        
        # 6. MACD分析
        if "金叉" in macd:
            tech_score += 10
            reasons.append("MACD金叉，短期看多")
        elif "死叉" in macd:
            tech_score -= 10
            reasons.append("MACD死叉，短期看空")
            risks.append("MACD死叉，注意调整")
        
        # 确定信号类型
        if tech_score >= 30:
            signal_type = "buy"
            confidence = "high"
        elif tech_score >= 15:
            signal_type = "buy"
            confidence = "medium"
        elif tech_score <= -30:
            signal_type = "sell"
            confidence = "high"
        elif tech_score <= -15:
            signal_type = "sell"
            confidence = "medium"
        else:
            signal_type = "hold"
            confidence = "low"
        
        # 计算止损止盈
        if signal_type == "buy":
            stop_loss = current_price * 0.97  # 3%止损
            target_price = current_price * 1.06  # 6%止盈
            position_size = 20 if confidence == "high" else 10
        elif signal_type == "sell":
            stop_loss = current_price * 1.03
            target_price = current_price * 0.97
            position_size = 0
        else:
            stop_loss = 0
            target_price = 0
            position_size = 0
        
        # 添加通用风险提示
        risks.append("投资有风险，入市需谨慎")
        risks.append("以上分析仅供参考，不构成投资建议")
        
        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'signal_type': signal_type,
            'confidence': confidence,
            'tech_score': tech_score,
            'reasons': reasons,
            'risks': risks,
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'stop_loss_pct': 3.0 if signal_type == "buy" else 0,
            'target_price': target_price,
            'target_pct': 6.0 if signal_type == "buy" else 0,
            'position_size': position_size,
            'timestamp': datetime.now().isoformat(),
            'model_type': 'rule',
            'disclaimer': "以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。"
        }

    def format_report(self, analysis: Dict) -> str:
        """
        格式化分析报告
        
        Args:
            analysis: 分析结果
            
        Returns:
            格式化的报告
        """
        signal_type = analysis['signal_type']
        confidence = analysis['confidence']
        
        # 信号图标
        if signal_type == "buy":
            signal_icon = "🟢"
            signal_text = "买入信号"
        elif signal_type == "sell":
            signal_icon = "🔴"
            signal_text = "卖出信号"
        else:
            signal_icon = "🟡"
            signal_text = "观望信号"
        
        # 置信度文本
        confidence_text = {"high": "高", "medium": "中", "low": "低"}.get(confidence, "中")
        
        # 模型类型
        model_type = analysis.get('model_type', 'rule')
        model_text = {
            'deepseek': 'DeepSeek',
            'openai': 'OpenAI',
            'local': '本地模型',
            'rule': '规则引擎'
        }.get(model_type, model_type)
        
        report = f"""
{'='*60}
📊 AI短线交易分析报告
{'='*60}

【股票代码】{analysis['stock_code']}
【股票名称】{analysis['stock_name']}
【信号类型】{signal_icon} {signal_text}
【置信度】{confidence_text}
【综合评分】{analysis['tech_score']}
【分析模型】{model_text}

📈 分析依据：
"""
        
        for i, reason in enumerate(analysis['reasons'], 1):
            # 如果是大模型回复，截取前200字符
            if len(reason) > 200:
                report += f"  {i}. {reason[:200]}...\n"
            else:
                report += f"  {i}. {reason}\n"
        
        report += "\n⚠️ 风险提示：\n"
        for risk in analysis['risks']:
            report += f"  - {risk}\n"
        
        if signal_type == "buy":
            report += f"""
💰 交易建议：
  - 建议价格：{analysis['entry_price']:.2f}
  - 止损位置：{analysis['stop_loss']:.2f}（跌幅{analysis['stop_loss_pct']:.1f}%）
  - 目标位置：{analysis['target_price']:.2f}（涨幅{analysis['target_pct']:.1f}%）
  - 建议仓位：{analysis['position_size']}%
"""
        elif signal_type == "sell":
            report += f"""
💰 交易建议：
  - 建议价格：{analysis['entry_price']:.2f}
  - 止损位置：{analysis['stop_loss']:.2f}
  - 建议操作：考虑减仓或离场
"""
        else:
            report += """
💰 交易建议：
  - 当前建议观望
  - 等待更明确的信号
"""
        
        report += f"""
⏰ 分析时间：{analysis['timestamp']}

{'='*60}
⚠️ 免责声明：{analysis['disclaimer']}
{'='*60}
"""
        
        return report

    def get_model_info(self) -> Dict:
        """获取模型信息"""
        if self.llm:
            return self.llm.get_model_info()
        return {
            'name': 'Rule-based',
            'model_type': 'rule',
            'has_api_key': False
        }

    def update_preference(self, **kwargs):
        """
        更新用户偏好
        
        Args:
            **kwargs: 偏好字段和值
        """
        self.memory.update_preference(**kwargs)

    def record_feedback(
        self,
        stock_code: str,
        feedback_type: str,
        content: str
    ):
        """
        记录用户反馈
        
        Args:
            stock_code: 股票代码
            feedback_type: 反馈类型 ('positive', 'negative', 'neutral')
            content: 反馈内容
        """
        self.memory.record_feedback(stock_code, feedback_type, content)

    def get_memory_statistics(self) -> Dict:
        """获取记忆统计信息"""
        return self.memory.get_statistics()


# 测试代码
if __name__ == '__main__':
    import os
    
    # 测试规则分析
    print("=== 测试规则分析 ===")
    analyzer = AIAnalyzer(model_type="rule")
    
    analysis = analyzer.analyze_stock(
        stock_code='600519',
        stock_name='贵州茅台',
        current_price=1800.0,
        change_pct=2.5,
        volume=5000000,
        turnover=0.4,
        ma5=1790.0,
        ma10=1780.0,
        ma20=1750.0,
        macd='MACD金叉',
        rsi=55.0,
        kdj='KDJ金叉'
    )
    
    print(analyzer.format_report(analysis))
    
    # 测试DeepSeek（如果有API Key）
    deepseek_key = os.environ.get('DEEPSEEK_API_KEY', '')
    if deepseek_key:
        print("\n=== 测试DeepSeek分析 ===")
        analyzer = AIAnalyzer(model_type="deepseek", api_key=deepseek_key)
        print(f"模型信息: {analyzer.get_model_info()}")
    else:
        print("\n=== DeepSeek API Key 未设置，跳过测试 ===")
