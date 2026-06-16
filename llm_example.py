"""
大模型对接示例
演示如何使用不同的大模型进行股票分析
"""

import os
from ai_analyzer import AIAnalyzer
from llm import DeepSeekLLM, OpenAILLM, LocalLLM


def show_deepseek_models():
    """展示DeepSeek可用模型"""
    print("=" * 60)
    print("DeepSeek 可用模型")
    print("=" * 60)
    
    models = DeepSeekLLM.list_models()
    for model in models:
        print(f"\n模型ID: {model['id']}")
        print(f"  名称: {model['name']}")
        print(f"  描述: {model['description']}")
        print(f"  上下文窗口: {model['context_window']} tokens")
        print(f"  最大输出: {model['max_output']} tokens")
        print(f"  输入成本: ¥{model['cost_per_1k_input']}/千token")
        print(f"  输出成本: ¥{model['cost_per_1k_output']}/千token")
        print(f"  适用场景: {model['use_case']}")
    
    print("\n" + "-" * 60)
    print("推荐模型（按场景）：")
    for scenario, model_id in DeepSeekLLM.RECOMMENDED_MODELS.items():
        print(f"  {scenario}: {model_id}")


def test_rule_based():
    """测试规则分析"""
    print("\n" + "=" * 60)
    print("测试规则分析（无需API）")
    print("=" * 60)
    
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


def test_deepseek_chat():
    """测试DeepSeek-V3（通用对话）"""
    print("\n" + "=" * 60)
    print("测试 DeepSeek-V3 (deepseek-chat)")
    print("=" * 60)
    
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    
    if not api_key:
        print("DEEPSEEK_API_KEY 未设置，跳过测试")
        print("设置方法：export DEEPSEEK_API_KEY='your_api_key'")
        return
    
    # 使用 deepseek-chat 模型
    analyzer = AIAnalyzer(model_type="deepseek", api_key=api_key, model="deepseek-chat")
    
    print(f"模型信息: {analyzer.get_model_info()}")
    
    # 验证连接
    if analyzer.llm and analyzer.llm.validate_connection():
        print("DeepSeek-V3 连接成功")
    else:
        print("DeepSeek 连接失败")
        return
    
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


def test_deepseek_reasoner():
    """测试DeepSeek-R1（推理模型）"""
    print("\n" + "=" * 60)
    print("测试 DeepSeek-R1 (deepseek-reasoner)")
    print("=" * 60)
    
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    
    if not api_key:
        print("DEEPSEEK_API_KEY 未设置，跳过测试")
        return
    
    # 使用 deepseek-reasoner 模型
    analyzer = AIAnalyzer(model_type="deepseek-reasoner", api_key=api_key)
    
    print(f"模型信息: {analyzer.get_model_info()}")
    
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


def test_openai():
    """测试OpenAI"""
    print("\n" + "=" * 60)
    print("测试OpenAI")
    print("=" * 60)
    
    api_key = os.environ.get('OPENAI_API_KEY', '')
    
    if not api_key:
        print("OPENAI_API_KEY 未设置，跳过测试")
        print("设置方法：export OPENAI_API_KEY='your_api_key'")
        return
    
    analyzer = AIAnalyzer(model_type="openai", api_key=api_key, model="gpt-4o-mini")
    
    print(f"模型信息: {analyzer.get_model_info()}")
    
    # 验证连接
    if analyzer.llm and analyzer.llm.validate_connection():
        print("OpenAI 连接成功")
    else:
        print("OpenAI 连接失败")
        return
    
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


def test_local():
    """测试本地模型"""
    print("\n" + "=" * 60)
    print("测试本地模型（Ollama）")
    print("=" * 60)
    
    base_url = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
    model = os.environ.get('OLLAMA_MODEL', 'qwen2.5:7b')
    
    analyzer = AIAnalyzer(model_type="local", base_url=base_url, model=model)
    
    print(f"模型信息: {analyzer.get_model_info()}")
    
    # 验证连接
    if analyzer.llm and analyzer.llm.validate_connection():
        print("本地模型 连接成功")
    else:
        print("本地模型 连接失败")
        print("请确保 Ollama 服务已启动：ollama serve")
        return
    
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


def main():
    """主函数"""
    print("大模型对接示例")
    print()
    
    # 1. 展示DeepSeek模型
    show_deepseek_models()
    
    # 2. 测试规则分析
    test_rule_based()
    
    # 3. 测试DeepSeek-V3
    test_deepseek_chat()
    
    # 4. 测试DeepSeek-R1
    test_deepseek_reasoner()
    
    # 5. 测试OpenAI
    test_openai()
    
    # 6. 测试本地模型
    test_local()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    print("\n使用说明：")
    print("1. 规则分析：无需API，直接使用")
    print("2. DeepSeek-V3：export DEEPSEEK_API_KEY='your_key'")
    print("3. DeepSeek-R1：export DEEPSEEK_API_KEY='your_key'（推理能力更强）")
    print("4. OpenAI：export OPENAI_API_KEY='your_key'")
    print("5. 本地模型：ollama serve && ollama pull qwen2.5:7b")


if __name__ == '__main__':
    main()
