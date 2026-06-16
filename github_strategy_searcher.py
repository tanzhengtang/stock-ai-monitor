"""
GitHub策略搜索模块
从GitHub搜索可用的量化交易策略
"""

import requests
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import json
import hashlib


class GitHubStrategySearcher:
    """GitHub策略搜索器
    
    功能：
    1. 搜索GitHub上的量化策略仓库
    2. 分析策略代码
    3. 提取策略信号
    4. 生成策略报告
    """

    def __init__(self, data_dir: str = None):
        self.logger = logging.getLogger('GitHubStrategySearcher')
        self.data_dir = Path(data_dir or 'data')
        self.data_dir.mkdir(exist_ok=True)
        
        # 搜索缓存
        self.cache_file = self.data_dir / 'github_strategies.json'
        self.cache = self._load_cache()
        
        # 搜索关键词
        self.search_keywords = [
            'stock trading strategy python',
            'quantitative trading strategy',
            'stock prediction python',
            'trading signal python',
            'stock analysis python',
            'algorithmic trading',
            'technical analysis python',
        ]
        
        # 策略类型识别
        self.strategy_patterns = {
            'ma_cross': [r'MA.*cross', r'moving.*average', r'ma.*strategy'],
            'rsi': [r'RSI', r'relative.*strength'],
            'macd': [r'MACD'],
            'bollinger': [r'bollinger', r'BB.*band'],
            'kdj': [r'KDJ', r'stochastic'],
            'momentum': [r'momentum', r'ROC'],
            'volume': [r'volume.*price', r'OBV'],
            'pattern': [r'candlestick', r'pattern.*recognition'],
        }

    def _load_cache(self) -> Dict:
        """加载缓存"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"加载缓存失败: {e}")
        return {'last_update': None, 'strategies': []}

    def _save_cache(self):
        """保存缓存"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存缓存失败: {e}")

    def search_strategies(self, force: bool = False) -> List[Dict]:
        """
        搜索GitHub策略
        
        Args:
            force: 是否强制更新
            
        Returns:
            策略列表
        """
        # 检查是否需要更新
        if not force and self.cache.get('last_update'):
            last_update = datetime.fromisoformat(self.cache['last_update'])
            if datetime.now() - last_update < timedelta(days=7):
                self.logger.info("使用缓存策略")
                return self.cache.get('strategies', [])
        
        self.logger.info("开始搜索GitHub策略...")
        
        all_strategies = []
        
        for keyword in self.search_keywords:
            try:
                strategies = self._search_github(keyword)
                all_strategies.extend(strategies)
                
                # 限制请求数量
                if len(all_strategies) >= 50:
                    break
                    
            except Exception as e:
                self.logger.warning(f"搜索失败 [{keyword}]: {e}")
        
        # 去重
        unique_strategies = self._deduplicate(all_strategies)
        
        # 更新缓存
        self.cache = {
            'last_update': datetime.now().isoformat(),
            'strategies': unique_strategies
        }
        self._save_cache()
        
        self.logger.info(f"搜索完成，找到 {len(unique_strategies)} 个策略")
        
        return unique_strategies

    def _search_github(self, keyword: str) -> List[Dict]:
        """
        搜索GitHub
        """
        strategies = []
        
        # GitHub Search API
        url = 'https://api.github.com/search/repositories'
        params = {
            'q': keyword,
            'sort': 'stars',
            'order': 'desc',
            'per_page': 10
        }
        
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'StockAnalysisBot'
        }
        
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                items = data.get('items', [])
                
                for item in items:
                    strategy = self._parse_repo(item)
                    if strategy:
                        strategies.append(strategy)
            else:
                self.logger.warning(f"GitHub API请求失败: {resp.status_code}")
                
        except Exception as e:
            self.logger.warning(f"GitHub搜索失败: {e}")
        
        return strategies

    def _parse_repo(self, repo: Dict) -> Optional[Dict]:
        """
        解析仓库信息
        """
        try:
            name = repo.get('name', '')
            description = repo.get('description', '') or ''
            stars = repo.get('stargazers_count', 0)
            language = repo.get('language', '')
            url = repo.get('html_url', '')
            topics = repo.get('topics', [])
            
            # 只关注Python项目
            if language and language.lower() != 'python':
                return None
            
            # 识别策略类型
            strategy_types = self._identify_strategy_types(name + ' ' + description)
            
            # 计算质量分数
            quality_score = self._calculate_quality_score(stars, description, topics)
            
            return {
                'name': name,
                'description': description[:200],
                'stars': stars,
                'language': language,
                'url': url,
                'topics': topics[:5],
                'strategy_types': strategy_types,
                'quality_score': quality_score,
                'added_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            return None

    def _identify_strategy_types(self, text: str) -> List[str]:
        """
        识别策略类型
        """
        text_lower = text.lower()
        types = []
        
        for strategy_type, patterns in self.strategy_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    types.append(strategy_type)
                    break
        
        return types if types else ['other']

    def _calculate_quality_score(self, stars: int, description: str, topics: List[str]) -> float:
        """
        计算质量分数
        """
        score = 0
        
        # Stars分数
        if stars >= 1000:
            score += 30
        elif stars >= 100:
            score += 20
        elif stars >= 10:
            score += 10
        
        # 描述长度
        if len(description) > 100:
            score += 10
        elif len(description) > 50:
            score += 5
        
        # 相关topics
        relevant_topics = ['trading', 'stock', 'quantitative', 'algorithmic', 'backtest']
        for topic in topics:
            if topic.lower() in relevant_topics:
                score += 5
        
        return min(score, 100)

    def _deduplicate(self, strategies: List[Dict]) -> List[Dict]:
        """
        去重
        """
        seen = set()
        unique = []
        
        for strategy in strategies:
            key = strategy.get('url', '')
            if key and key not in seen:
                seen.add(key)
                unique.append(strategy)
        
        # 按质量分数排序
        unique.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        
        return unique[:30]  # 只保留前30个

    def get_strategy_report(self) -> str:
        """
        生成策略报告
        """
        strategies = self.cache.get('strategies', [])
        
        if not strategies:
            return "暂无策略数据，请先运行搜索"
        
        report = f"""
📊 【GitHub策略搜索报告】

搜索时间: {self.cache.get('last_update', 'N/A')}
策略数量: {len(strategies)}

{'='*50}

TOP 10 策略：

"""
        
        for i, strategy in enumerate(strategies[:10], 1):
            types = ', '.join(strategy.get('strategy_types', []))
            report += f"""{i}. {strategy['name']}
   描述: {strategy['description'][:80]}...
   Stars: {strategy['stars']} | 评分: {strategy['quality_score']:.0f}
   类型: {types}
   链接: {strategy['url']}

"""
        
        # 统计策略类型
        type_counts = {}
        for strategy in strategies:
            for st in strategy.get('strategy_types', []):
                type_counts[st] = type_counts.get(st, 0) + 1
        
        report += f"""{'='*50}

策略类型分布：

"""
        for st, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            bar = '█' * (count * 2)
            report += f"  {st:<15} {count:<3} {bar}\n"
        
        return report


# 测试代码
if __name__ == '__main__':
    searcher = GitHubStrategySearcher()
    
    print("搜索GitHub策略...")
    strategies = searcher.search_strategies()
    
    print(f"\n找到 {len(strategies)} 个策略")
    print(searcher.get_strategy_report())
