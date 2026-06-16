"""
AI记忆系统
让AI能够记住用户偏好和历史分析
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    category: str  # 'preference', 'analysis', 'feedback', 'pattern'
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    importance: float = 0.5  # 0-1，重要性


@dataclass
class UserPreference:
    """用户偏好"""
    risk_tolerance: str = "medium"  # low, medium, high
    trading_style: str = "short"    # short, swing, long
    preferred_indicators: List[str] = field(default_factory=lambda: ["MA", "RSI", "MACD"])
    max_position_pct: float = 0.2
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.1
    excluded_stocks: List[str] = field(default_factory=list)
    preferred_sectors: List[str] = field(default_factory=list)


class MemorySystem:
    """记忆系统
    
    功能：
    1. 存储用户偏好
    2. 记录历史分析
    3. 存储用户反馈
    4. 识别交易模式
    5. 生成个性化提示词
    """

    def __init__(self, storage_path: str = "data/memory"):
        """
        初始化记忆系统
        
        Args:
            storage_path: 存储路径
        """
        self.storage_path = storage_path
        self.logger = logging.getLogger('MemorySystem')
        
        # 创建存储目录
        os.makedirs(storage_path, exist_ok=True)
        
        # 加载数据
        self.preferences = self._load_preferences()
        self.memories = self._load_memories()

    def _load_preferences(self) -> UserPreference:
        """加载用户偏好"""
        path = os.path.join(self.storage_path, "preferences.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return UserPreference(**data)
            except Exception as e:
                self.logger.warning(f"加载偏好失败: {e}")
        return UserPreference()

    def _save_preferences(self):
        """保存用户偏好"""
        path = os.path.join(self.storage_path, "preferences.json")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.preferences), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存偏好失败: {e}")

    def _load_memories(self) -> List[MemoryEntry]:
        """加载记忆"""
        path = os.path.join(self.storage_path, "memories.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return [MemoryEntry(**m) for m in data]
            except Exception as e:
                self.logger.warning(f"加载记忆失败: {e}")
        return []

    def _save_memories(self):
        """保存记忆"""
        path = os.path.join(self.storage_path, "memories.json")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                data = [asdict(m) for m in self.memories]
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存记忆失败: {e}")

    def update_preference(self, **kwargs):
        """
        更新用户偏好
        
        Args:
            **kwargs: 偏好字段和值
        """
        for key, value in kwargs.items():
            if hasattr(self.preferences, key):
                setattr(self.preferences, key, value)
                self.logger.info(f"更新偏好: {key} = {value}")
        
        self._save_preferences()

    def get_preferences(self) -> Dict:
        """获取用户偏好"""
        return asdict(self.preferences)

    def add_memory(
        self,
        category: str,
        content: str,
        metadata: Dict = None,
        importance: float = 0.5
    ) -> str:
        """
        添加记忆
        
        Args:
            category: 类别 ('preference', 'analysis', 'feedback', 'pattern')
            content: 内容
            metadata: 元数据
            importance: 重要性 (0-1)
            
        Returns:
            记忆ID
        """
        import uuid
        
        memory = MemoryEntry(
            id=str(uuid.uuid4())[:8],
            category=category,
            content=content,
            metadata=metadata or {},
            importance=importance
        )
        
        self.memories.append(memory)
        self._save_memories()
        
        self.logger.info(f"添加记忆: [{category}] {content[:50]}...")
        return memory.id

    def get_memories(
        self,
        category: Optional[str] = None,
        limit: int = 10,
        min_importance: float = 0
    ) -> List[MemoryEntry]:
        """
        获取记忆
        
        Args:
            category: 筛选类别
            limit: 返回数量
            min_importance: 最小重要性
            
        Returns:
            记忆列表
        """
        filtered = self.memories
        
        if category:
            filtered = [m for m in filtered if m.category == category]
        
        filtered = [m for m in filtered if m.importance >= min_importance]
        
        # 按重要性和时间排序
        filtered.sort(key=lambda x: (x.importance, x.created_at), reverse=True)
        
        return filtered[:limit]

    def search_memories(self, query: str, limit: int = 5) -> List[MemoryEntry]:
        """
        搜索记忆
        
        Args:
            query: 搜索关键词
            limit: 返回数量
            
        Returns:
            匹配的记忆
        """
        results = []
        query_lower = query.lower()
        
        for memory in self.memories:
            if query_lower in memory.content.lower():
                memory.access_count += 1
                results.append(memory)
        
        # 按访问次数和重要性排序
        results.sort(key=lambda x: (x.access_count, x.importance), reverse=True)
        
        return results[:limit]

    def record_analysis(
        self,
        stock_code: str,
        stock_name: str,
        signal_type: str,
        score: float,
        reasons: List[str],
        result: Optional[str] = None
    ):
        """
        记录分析历史
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            signal_type: 信号类型
            score: 评分
            reasons: 分析原因
            result: 交易结果
        """
        content = f"{stock_code} {stock_name}: {signal_type} (评分:{score:.1f})"
        
        metadata = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'signal_type': signal_type,
            'score': score,
            'reasons': reasons,
            'result': result
        }
        
        # 根据评分确定重要性
        importance = min(abs(score - 50) / 50, 1.0)
        
        self.add_memory('analysis', content, metadata, importance)

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
        metadata = {
            'stock_code': stock_code,
            'feedback_type': feedback_type
        }
        
        importance = 0.8 if feedback_type in ['positive', 'negative'] else 0.5
        
        self.add_memory('feedback', content, metadata, importance)

    def record_pattern(
        self,
        pattern_type: str,
        description: str,
        examples: List[str]
    ):
        """
        记录交易模式
        
        Args:
            pattern_type: 模式类型
            description: 描述
            examples: 示例
        """
        metadata = {
            'pattern_type': pattern_type,
            'examples': examples
        }
        
        self.add_memory('pattern', description, metadata, 0.7)

    def get_stock_history(self, stock_code: str) -> List[MemoryEntry]:
        """
        获取某只股票的历史分析
        
        Args:
            stock_code: 股票代码
            
        Returns:
            历史分析记录
        """
        return [
            m for m in self.memories
            if m.metadata.get('stock_code') == stock_code
        ]

    def get_successful_patterns(self) -> List[MemoryEntry]:
        """获取成功的交易模式"""
        return [
            m for m in self.memories
            if m.category == 'pattern' and m.importance >= 0.7
        ]

    def generate_personalized_prompt(self) -> str:
        """
        生成个性化提示词
        
        Returns:
            个性化提示词
        """
        prefs = self.preferences
        
        prompt = f"""
## 用户个性化设置

### 风险偏好
- 风险承受能力: {prefs.risk_tolerance}
- 交易风格: {prefs.trading_style}
- 最大仓位比例: {prefs.max_position_pct:.0%}
- 止损比例: {prefs.stop_loss_pct:.0%}
- 止盈比例: {prefs.take_profit_pct:.0%}

### 偏好指标
- 常用技术指标: {', '.join(prefs.preferred_indicators)}

### 偏好板块
"""
        if prefs.preferred_sectors:
            for sector in prefs.preferred_sectors:
                prompt += f"- {sector}\n"
        else:
            prompt += "- 未设置\n"
        
        prompt += "\n### 排除股票\n"
        if prefs.excluded_stocks:
            for stock in prefs.excluded_stocks:
                prompt += f"- {stock}\n"
        else:
            prompt += "- 无\n"
        
        # 添加历史成功模式
        patterns = self.get_successful_patterns()
        if patterns:
            prompt += "\n### 历史成功模式\n"
            for pattern in patterns[:3]:
                prompt += f"- {pattern.content}\n"
        
        # 添加最近的分析记录
        recent_analyses = self.get_memories(category='analysis', limit=5)
        if recent_analyses:
            prompt += "\n### 最近分析记录\n"
            for analysis in recent_analyses:
                prompt += f"- {analysis.content}\n"
        
        return prompt

    def get_statistics(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            统计信息
        """
        total = len(self.memories)
        
        categories = {}
        for m in self.memories:
            categories[m.category] = categories.get(m.category, 0) + 1
        
        return {
            'total_memories': total,
            'categories': categories,
            'preferences': asdict(self.preferences)
        }

    def clear_old_memories(self, days: int = 30):
        """
        清理旧记忆
        
        Args:
            days: 保留天数
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        
        original_count = len(self.memories)
        self.memories = [
            m for m in self.memories
            if m.created_at > cutoff_str or m.importance >= 0.8
        ]
        
        removed = original_count - len(self.memories)
        if removed > 0:
            self._save_memories()
            self.logger.info(f"清理了 {removed} 条旧记忆")


# 测试代码
if __name__ == '__main__':
    # 创建记忆系统
    memory = MemorySystem(storage_path="/tmp/test_memory")
    
    # 更新偏好
    memory.update_preference(
        risk_tolerance="medium",
        trading_style="short",
        preferred_indicators=["MA", "RSI", "MACD", "KDJ"],
        preferred_sectors=["科技", "消费", "新能源"]
    )
    
    # 记录分析
    memory.record_analysis(
        stock_code="600519",
        stock_name="贵州茅台",
        signal_type="buy",
        score=75.0,
        reasons=["均线多头排列", "RSI正常", "MACD金叉"]
    )
    
    # 记录反馈
    memory.record_feedback(
        stock_code="600519",
        feedback_type="positive",
        content="分析准确，成功获利"
    )
    
    # 记录模式
    memory.record_pattern(
        pattern_type="技术形态",
        description="均线多头排列+MACD金叉",
        examples=["600519 贵州茅台 2024-01-15"]
    )
    
    # 生成个性化提示词
    print("个性化提示词：")
    print(memory.generate_personalized_prompt())
    
    # 统计信息
    print("\n统计信息：")
    print(json.dumps(memory.get_statistics(), ensure_ascii=False, indent=2))
