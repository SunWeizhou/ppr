"""
Zotero 智能提取器

从用户的 Zotero 文献库中自动提取研究兴趣和关键词。
"""

import os
import re
import sqlite3
import sys
import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class ZoteroExtractor:
    """从 Zotero 提取研究兴趣"""

    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: Zotero 数据库路径 (zotero.sqlite)
        """
        self.db_path = db_path
        self.papers: List[Dict] = []

    def detect_zotero_path(self) -> Optional[str]:
        """自动检测 Zotero 数据库路径"""
        possible_paths = []

        if os.name == 'nt':  # Windows
            appdata = os.environ.get('APPDATA', '')
            local_appdata = os.environ.get('LOCALAPPDATA', '')
            possible_paths = [
                os.path.join(appdata, "Zotero", "Zotero", "zotero.sqlite"),
                os.path.join(local_appdata, "Zotero", "Zotero", "zotero.sqlite"),
                os.path.expanduser("~/Zotero/zotero.sqlite"),
                os.path.expanduser("~/Documents/Zotero/zotero.sqlite"),
            ]
        elif sys.platform == 'darwin':  # macOS
            possible_paths = [
                os.path.expanduser("~/Zotero/zotero.sqlite"),
                os.path.expanduser("~/Library/Application Support/Zotero/zotero.sqlite"),
                os.path.expanduser("~/Library/Application Support/Zotero/Profiles/*/zotero.sqlite"),
            ]
        else:  # Linux
            possible_paths = [
                os.path.expanduser("~/Zotero/zotero.sqlite"),
                os.path.expanduser("~/.zotero/zotero.sqlite"),
            ]

        for path in possible_paths:
            matches = glob.glob(path) if any(char in path for char in "*?[") else [path]
            for resolved_path in matches:
                if os.path.exists(resolved_path):
                    self.db_path = resolved_path
                    return resolved_path

        return None

    def load_papers(self, limit: int = 500) -> List[Dict]:
        """从 Zotero 数据库加载论文

        Args:
            limit: 最大加载数量

        Returns:
            论文列表 [{'title': ..., 'abstract': ..., 'tags': [...], 'year': ...}]
        """
        if not self.db_path:
            if not self.detect_zotero_path():
                return []

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Zotero 数据库结构查询
            # 获取最近添加的论文
            query = """
            SELECT
                idv.value as title,
                idv2.value as abstract,
                items.dateAdded
            FROM items
            LEFT JOIN itemData id ON items.itemID = id.itemID
            LEFT JOIN itemDataValues idv ON id.valueID = idv.valueID
            LEFT JOIN itemData id2 ON items.itemID = id2.itemID
            LEFT JOIN itemDataValues idv2 ON id2.valueID = idv2.valueID
            LEFT JOIN itemFields if1 ON id.fieldID = if1.fieldID
            LEFT JOIN itemFields if2 ON id2.fieldID = if2.fieldID
            WHERE if1.fieldName = 'title'
            AND (if2.fieldName = 'abstractNote' OR if2.fieldName IS NULL)
            ORDER BY items.dateAdded DESC
            LIMIT ?
            """

            cursor.execute(query, (limit,))

            self.papers = []
            for row in cursor.fetchall():
                if row['title']:
                    self.papers.append({
                        'title': row['title'],
                        'abstract': row['abstract'] or '',
                        'year': self._extract_year(row['dateAdded'])
                    })

            conn.close()
            logger.info(f"Loaded {len(self.papers)} papers from Zotero")
            return self.papers

        except Exception as e:
            logger.error(f"Error loading from Zotero: {e}")
            return []

    def _extract_year(self, date_str: str) -> Optional[int]:
        """从日期字符串提取年份"""
        if date_str:
            match = re.search(r'(\d{4})', date_str)
            if match:
                return int(match.group(1))
        return None

    def extract_keywords(self, top_k: int = 50) -> Dict[str, float]:
        """从论文中提取关键词

        Args:
            top_k: 返回前 k 个关键词

        Returns:
            {keyword: score}
        """
        if not self.papers:
            self.load_papers()

        # 收集所有文本
        all_text = []
        for paper in self.papers:
            text = paper.get('title', '') + ' ' + paper.get('abstract', '')
            all_text.append(text.lower())

        # 预定义的学术关键词模式
        academic_patterns = [
            # 统计学习理论
            r'\b(generalization bound|excess risk|sample complexity|minimax)\b',
            r'\b(uniform convergence|rademacher|pac-bayes|pac bayes)\b',
            r'\b(convergence rate|asymptotic|non-asymptotic|finite sample)\b',

            # 深度学习
            r'\b(neural network|deep learning|overparameterization)\b',
            r'\b(double descent|implicit regularization|implicit bias)\b',
            r'\b(neural tangent|ntk|infinite width)\b',

            # 大模型
            r'\b(in-context learning|icl|large language model|llm)\b',
            r'\b(transformer|attention|self-attention)\b',
            r'\b(scaling law|emergent|chain of thought)\b',

            # 优化
            r'\b(stochastic gradient|sgd|optimization|convergence)\b',
            r'\b(convex|nonconvex|non-convex)\b',

            # 统计
            r'\b(bayesian|posterior|prior|mcmc)\b',
            r'\b(high-dimensional|sparse|lasso)\b',
            r'\b(nonparametric|kernel|density estimation)\b',

            # 因果
            r'\b(causal|treatment effect|instrumental)\b',

            # 不确定性
            r'\b(uncertainty|calibration|conformal)\b',
            r'\b(confidence interval|prediction interval)\b',

            # 强化学习
            r'\b(reinforcement learning|policy gradient|reward)\b',
            r'\b(bandit|exploration|exploitation)\b',

            # 图学习
            r'\b(graph neural|gnn|message passing)\b',

            # 常见 ML 术语
            r'\b(classification|regression|clustering)\b',
            r'\b(representation learning|feature learning)\b',
            r'\b(transfer learning|domain adaptation)\b',
        ]

        # 统计关键词出现频率
        keyword_counts = Counter()

        for text in all_text:
            for pattern in academic_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    keyword_counts[match] += 1

        # 标准化得分
        total_papers = len(self.papers) if self.papers else 1
        keyword_scores = {}

        for keyword, count in keyword_counts.most_common(top_k):
            # 基于频率计算权重
            frequency = count / total_papers
            if frequency > 0.3:
                weight = 5.0
            elif frequency > 0.2:
                weight = 4.5
            elif frequency > 0.1:
                weight = 4.0
            elif frequency > 0.05:
                weight = 3.5
            else:
                weight = 3.0

            keyword_scores[keyword] = weight

        return keyword_scores

    def match_to_templates(self, keywords: Dict[str, float]) -> Dict[str, float]:
        """将提取的关键词匹配到预定义模板

        Args:
            keywords: {keyword: score}

        Returns:
            {template_subfield: match_score}
        """
        from .templates import RESEARCH_TEMPLATES

        matches = {}

        for field_key, field_data in RESEARCH_TEMPLATES.items():
            for sf_key, sf_data in field_data.get('subfields', {}).items():
                sf_keywords = set(sf_data.get('keywords', []))
                full_key = f"{field_key}.{sf_key}"

                # 计算匹配度
                matched = sf_keywords & set(keywords.keys())
                if matched:
                    match_score = sum(keywords.get(k, 0) for k in matched) / len(sf_keywords)
                    matches[full_key] = match_score

        return dict(sorted(matches.items(), key=lambda x: x[1], reverse=True))

    def get_recommended_config(self) -> Dict:
        """获取推荐的配置

        Returns:
            推荐的配置字典
        """
        keywords = self.extract_keywords()
        matches = self.match_to_templates(keywords)

        # 选择匹配度最高的子领域
        selected_fields = {}
        for full_key, score in matches.items():
            if score > 0.3:  # 阈值
                field_key, sf_key = full_key.split('.')
                if field_key not in selected_fields:
                    selected_fields[field_key] = []
                selected_fields[field_key].append(sf_key)

        from .templates import generate_config_from_selections
        config = generate_config_from_selections(selected_fields)

        # 添加提取的关键词
        for kw, weight in keywords.items():
            if kw not in config['keywords']:
                config['keywords'][kw] = {
                    'weight': weight,
                    'category': 'secondary'
                }

        return {
            'config': config,
            'extracted_keywords': keywords,
            'matched_subfields': matches,
            'paper_count': len(self.papers)
        }

    def print_summary(self):
        """打印提取结果摘要"""
        result = self.get_recommended_config()

        print("\n" + "=" * 50)
        print("  Zotero 分析结果")
        print("=" * 50)

        print(f"\n  分析了 {result['paper_count']} 篇论文")

        print("\n  提取的主要关键词:")
        for kw, score in list(result['extracted_keywords'].items())[:15]:
            print(f"    - {kw}: {score:.1f}")

        print("\n  匹配的研究方向:")
        for full_key, score in list(result['matched_subfields'].items())[:10]:
            field_key, sf_key = full_key.split('.')
            from .templates import RESEARCH_TEMPLATES
            field_name = RESEARCH_TEMPLATES.get(field_key, {}).get('name', field_key)
            sf_name = RESEARCH_TEMPLATES.get(field_key, {}).get('subfields', {}).get(sf_key, {}).get('name', sf_key)
            print(f"    - {field_name} > {sf_name}: {score:.2f}")


if __name__ == "__main__":
    # 测试
    extractor = ZoteroExtractor()
    if extractor.detect_zotero_path():
        extractor.load_papers()
        extractor.print_summary()
    else:
        print("未找到 Zotero 数据库")
