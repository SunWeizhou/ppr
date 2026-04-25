"""
统一配置管理器

将所有配置合并到单一的 user_profile.json 文件中
消除 user_config.json 和 keywords_config.json 之间的冗余。
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_FILE = Path(__file__).parent / "user_profile.json"


@dataclass
class KeywordConfig:
    """关键词配置"""
    weight: float
    category: str  # 'core', 'secondary', 'demote', 'dislike'


@dataclass
class Settings:
    """系统设置"""
    papers_per_day: int = 20
    lookback_days: int = 14
    pdf_auto_download_score: float = 2.5
    max_papers_per_author: int = 22
    recency_bonus_days: int = 7
    recency_bonus: float = 0.3
    prefer_theory: bool = True
    theory_enabled: bool = True
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class SourceConfig:
    """数据源配置"""
    arxiv_enabled: bool = True
    journal_enabled: bool = True
    scholar_enabled: bool = False
    lookback_days: int = 14


@dataclass
class ZoteroConfig:
    """Zotero 配置"""
    database_path: str = ""
    auto_detect: bool = True
    enabled: bool = True


@dataclass
class VenuePriority:
    """期刊/会议优先级"""
    statistics_journals: List[str] = field(default_factory=lambda: ["Annals of Statistics", "JASA", "Biometrika", "JRSS-B"])
    ml_journals: List[str] = field(default_factory=lambda: ["JMLR"])
    top_conferences: List[str] = field(default_factory=lambda: ["NeurIPS", "ICML", "ICLR", "COLT", "AISTATS"])
    theory_conferences: List[str] = field(default_factory=lambda: ["COLT", "AISTATS"])
    statistics_bonus: float = 1.0
    ml_journal_bonus: float = 0.8
    conference_bonus: float = 0.5
    theory_conference_bonus: float = 1.0


class ConfigManager:
    """统一配置管理器 - 单例模式"""

    _instance: Optional['ConfigManager'] = None

    def __new__(cls):
        if cls._instance is not None:
            return cls._instance

        instance = super().__new__(cls)
        cls._instance = instance

        # 初始化属性
        instance._keywords = {}
        instance._config = {}
        instance._settings = Settings()
        instance._sources = SourceConfig()
        instance._zotero = ZoteroConfig()
        instance._venue_priority = VenuePriority()
        instance._config_mtime = 0.0
        instance._last_loaded = 0.0

        # 加载配置文件
        instance._load_config()

        return instance

    def _load_config(self):
        """加载配置文件"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                logger.info(f"Loaded config from {CONFIG_FILE}")
                raw, migrated = self._merge_legacy_config_if_needed(raw)
                self._parse_config(raw)
                if migrated:
                    self.save()
                self._last_loaded = time.time()
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                self._load_defaults()
        else:
            logger.warning(f"Config file not found at {CONFIG_FILE}, using defaults")
            self._load_defaults()

    def _load_defaults(self):
        """加载默认配置"""
        raw = self._get_defaults()
        self._parse_config(raw)
        self._config_mtime = time.time()

    def _merge_legacy_config_if_needed(self, raw: Dict) -> tuple[Dict, bool]:
        """Backfill v2 profile fields from legacy local config files.

        Older installs may have a v2 ``user_profile.json`` that only contains
        dislikes, while the actual positive ranking profile still lives in
        ``keywords_config.json`` or ``user_config.json``. A local-first product
        should recover those signals automatically instead of silently ranking
        only by recency.
        """
        raw = dict(raw or {})
        keywords = dict(raw.get('keywords') or {})
        has_positive_topics = any(
            item.get('category') in {'core', 'secondary'}
            and float(item.get('weight', 0) or 0) > 0
            for item in keywords.values()
            if isinstance(item, dict)
        )
        migrated = False
        base_dir = CONFIG_FILE.parent

        legacy_keywords_path = base_dir / "keywords_config.json"
        if (not has_positive_topics or not raw.get('theory_keywords')) and legacy_keywords_path.exists():
            try:
                legacy = json.loads(legacy_keywords_path.read_text(encoding='utf-8'))
                for category_key, category in (
                    ('core_topics', 'core'),
                    ('secondary_topics', 'secondary'),
                    ('demote_topics', 'demote'),
                ):
                    for name, weight in (legacy.get(category_key) or {}).items():
                        if name not in keywords:
                            keywords[name] = {'weight': weight, 'category': category}
                            migrated = True

                dislike = legacy.get('dislike_topics') or {}
                if isinstance(dislike, list):
                    dislike = {name: -1.0 for name in dislike}
                for name, weight in dislike.items():
                    if name not in keywords:
                        keywords[name] = {'weight': weight, 'category': 'dislike'}
                        migrated = True

                if not raw.get('theory_keywords') and legacy.get('theory_keywords'):
                    raw['theory_keywords'] = legacy.get('theory_keywords') or []
                    migrated = True
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                logger.warning(f"Could not migrate legacy keywords config: {exc}")

        legacy_user_path = base_dir / "user_config.json"
        if not has_positive_topics and legacy_user_path.exists():
            try:
                legacy_user = json.loads(legacy_user_path.read_text(encoding='utf-8'))
                topics = legacy_user.get('research_focus', {}).get('topics', [])
                for topic in topics:
                    key = str(topic).strip().lower()
                    if key and key not in keywords:
                        keywords[key] = {
                            'weight': float(legacy_user.get('research_focus', {}).get('weight', 3.0) or 3.0),
                            'category': 'core',
                        }
                        migrated = True
                theory = legacy_user.get('theory_preference', {}).get('theory_keywords', [])
                if not raw.get('theory_keywords') and theory:
                    raw['theory_keywords'] = theory
                    migrated = True
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                logger.warning(f"Could not migrate legacy user config: {exc}")

        if migrated:
            raw['version'] = max(int(raw.get('version', 1) or 1), 2)
            raw['keywords'] = keywords
        return raw, migrated

    @property
    def defaults(self) -> Dict:
        """获取默认配置"""
        return {
            'version': 1,
            'keywords': {
                'conformal prediction': {'weight': 5.0, 'category': 'core'},
                'in-context learning': {'weight': 5.0, 'category': 'core'},
                'minimax': {'weight': 4.5, 'category': 'core'},
                'generalization': {'weight': 4.0, 'category': 'core'},
                'statistical inference': {'weight': 4.0, 'category': 'core'},
                'nonparametric': {'weight': 4.0, 'category': 'core'},
                'excess risk': {'weight': 4.0, 'category': 'core'},
                'uniform convergence': {'weight': 4.0, 'category': 'core'},
                'benchmark': {'weight': -1.0, 'category': 'demote'},
                'real-world': {'weight': -1.0, 'category': 'demote'},
                'federated learning': {'weight': -1.0, 'category': 'dislike'},
            },
            'theory_keywords': [
                'theorem', 'proof', 'bound', 'convergence', 'statistical',
                'bayesian', 'estimation', 'generalization', 'asymptotic', 'minimax',
                'optimal', 'rate', 'complexity', 'guarantee'
            ],
            'settings': {
                'papers_per_day': 20,
                'lookback_days': 14,
                'pdf_auto_download_score': 1.5,
                'max_papers_per_author': 22,
                'recency_bonus_days': 7,
                'recency_bonus': 0.3,
                'prefer_theory': True,
                'theory_enabled': True,
                'embedding_model': 'sentence-transformers/all-MiniLM-L6-v2'
            },
            'sources': {
                'arxiv_enabled': True,
                'journal_enabled': True,
                'scholar_enabled': False,
                'lookback_days': 14
            },
            'zotero': {
                'database_path': '',
                'auto_detect': True,
                'enabled': True
            },
            'venue_priority': {
                'statistics_journals': ['Annals of Statistics', 'JASA', 'Biometrika', 'JRSS-B'],
                'ml_journals': ['JMLR'],
                'top_conferences': ['NeurIPS', 'ICML', 'ICLR', 'COLT', 'AISTATS'],
                'theory_conferences': ['COLT', 'AISTATS'],
                'statistics_bonus': 1.0,
                'ml_journal_bonus': 0.8,
                'conference_bonus': 0.5,
                'theory_conference_bonus': 1.0
            }
        }

    def _get_defaults(self) -> Dict:
        """获取默认配置（兼容旧调用）"""
        return self.defaults

    def _parse_config(self, raw: Dict):
        """解析原始配置到结构化对象"""
        self._config = {
            'version': raw.get('version', 1),
            'theory_keywords': raw.get('theory_keywords', []),
        }

        # 解析关键词
        self._keywords = {}
        for name, kw_data in raw.get('keywords', {}).items():
                self._keywords[name] = KeywordConfig(
                    weight=kw_data.get('weight', 3.0),
                    category=kw_data.get('category', 'core')
                )

        # 解析设置
        settings_data = raw.get('settings', {})
        self._settings.papers_per_day = settings_data.get('papers_per_day', 20)
        self._settings.lookback_days = settings_data.get('lookback_days', 14)
        self._settings.pdf_auto_download_score = settings_data.get('pdf_auto_download_score', 1.5)
        self._settings.max_papers_per_author = settings_data.get('max_papers_per_author', 22)
        self._settings.recency_bonus_days = settings_data.get('recency_bonus_days', 7)
        self._settings.recency_bonus = settings_data.get('recency_bonus', 0.3)
        self._settings.prefer_theory = settings_data.get('prefer_theory', True)
        self._settings.theory_enabled = settings_data.get('theory_enabled', True)
        self._settings.embedding_model = settings_data.get('embedding_model',
            'sentence-transformers/all-MiniLM-L6-v2')

        # 解析数据源
        sources_data = raw.get('sources', {})
        self._sources.arxiv_enabled = sources_data.get('arxiv_enabled', True)
        self._sources.journal_enabled = sources_data.get('journal_enabled', True)
        self._sources.scholar_enabled = sources_data.get('scholar_enabled', False)
        self._sources.lookback_days = sources_data.get('lookback_days', 14)

        # 解析Zotero
        zotero_data = raw.get('zotero', {})
        self._zotero.database_path = zotero_data.get('database_path', '')
        self._zotero.auto_detect = zotero_data.get('auto_detect', True)
        self._zotero.enabled = zotero_data.get('enabled', True)

        # 解析期刊优先级
        venue_data = raw.get('venue_priority', {})
        self._venue_priority.statistics_journals = venue_data.get('statistics_journals',
            ['Annals of Statistics', 'JASA', 'Biometrika', 'JRSS-B'])
        self._venue_priority.ml_journals = venue_data.get('ml_journals', ['JMLR'])
        self._venue_priority.top_conferences = venue_data.get('top_conferences',
            ['NeurIPS', 'ICML', 'ICLR', 'COLT', 'AISTATS'])
        self._venue_priority.theory_conferences = venue_data.get('theory_conferences',
            ['COLT', 'AISTATS'])
        self._venue_priority.statistics_bonus = venue_data.get('statistics_bonus', 1.0)
        self._venue_priority.ml_journal_bonus = venue_data.get('ml_journal_bonus', 0.8)
        self._venue_priority.conference_bonus = venue_data.get('conference_bonus', 0.5)
        self._venue_priority.theory_conference_bonus = venue_data.get('theory_conference_bonus', 1.0)

    def _to_dict(self) -> Dict:
        """将配置转换为字典格式（用于保存）"""
        return {
            'version': self._config.get('version', 1),
            'keywords': {
                name: {'weight': kw.weight, 'category': kw.category}
                for name, kw in self._keywords.items()
            },
            'theory_keywords': self._config.get('theory_keywords', []),
            'settings': {
                'papers_per_day': self._settings.papers_per_day,
                'lookback_days': self._settings.lookback_days,
                'pdf_auto_download_score': self._settings.pdf_auto_download_score,
                'max_papers_per_author': self._settings.max_papers_per_author,
                'recency_bonus_days': self._settings.recency_bonus_days,
                'recency_bonus': self._settings.recency_bonus,
                'prefer_theory': self._settings.prefer_theory,
                'theory_enabled': self._settings.theory_enabled,
                'embedding_model': self._settings.embedding_model,
            },
            'sources': {
                'arxiv_enabled': self._sources.arxiv_enabled,
                'journal_enabled': self._sources.journal_enabled,
                'scholar_enabled': self._sources.scholar_enabled,
                'lookback_days': self._sources.lookback_days,
            },
            'zotero': {
                'database_path': self._zotero.database_path,
                'auto_detect': self._zotero.auto_detect,
                'enabled': self._zotero.enabled,
            },
            'venue_priority': {
                'statistics_journals': self._venue_priority.statistics_journals,
                'ml_journals': self._venue_priority.ml_journals,
                'top_conferences': self._venue_priority.top_conferences,
                'theory_conferences': self._venue_priority.theory_conferences,
                'statistics_bonus': self._venue_priority.statistics_bonus,
                'ml_journal_bonus': self._venue_priority.ml_journal_bonus,
                'conference_bonus': self._venue_priority.conference_bonus,
                'theory_conference_bonus': self._venue_priority.theory_conference_bonus,
            }
        }

    def save(self) -> bool:
        """保存配置到文件"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._to_dict(), f, indent=2, ensure_ascii=False)
            self._config_mtime = time.time()
            logger.info(f"Config saved to {CONFIG_FILE}")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    def reload(self) -> bool:
        """重新加载配置文件"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                self._parse_config(raw)
                self._config_mtime = time.time()
                logger.info("Config reloaded")
                return True
        except Exception as e:
            logger.error(f"Error reloading config: {e}")
            return False
        return False

    # ============ 便捷访问方法 ============

    @property
    def core_keywords(self) -> Dict[str, float]:
        """获取核心关键词（category='core'）"""
        return {
            name: kw.weight
            for name, kw in self._keywords.items()
            if kw.category == 'core'
        }

    @property
    def demote_keywords(self) -> Dict[str, float]:
        """获取降权关键词（category='demote'）"""
        return {
            name: kw.weight
            for name, kw in self._keywords.items()
            if kw.category == 'demote'
        }

    @property
    def theory_keywords(self) -> List[str]:
        """获取理论信号关键词"""
        return list(self._config.get('theory_keywords', []))

    @property
    def dislike_keywords(self) -> Dict[str, float]:
        """获取不感兴趣关键词"""
        return {
            name: kw.weight
            for name, kw in self._keywords.items()
            if kw.category == 'dislike'
        }

    @property
    def all_keywords(self) -> Dict[str, KeywordConfig]:
        """获取所有关键词"""
        return self._keywords.copy()

    def get_keyword_weight(self, keyword: str) -> float:
        """获取指定关键词的权重"""
        kw = self._keywords.get(keyword.lower())
        return kw.weight if kw else 0.0

    def set_keyword(self, keyword: str, weight: float, category: str = 'core', save: bool = True) -> None:
        """设置关键词权重

        Args:
            keyword: 关键词
            weight: 权重
            category: 类别 ('core', 'secondary', 'demote', 'dislike')
            save: 是否立即保存到磁盘 (批量更新时设为 False)
        """
        self._keywords[keyword.lower()] = KeywordConfig(weight=weight, category=category)
        if save:
            self.save()
        logger.info(f"Set keyword '{keyword}' weight={weight} category={category}")

    def remove_keyword(self, keyword: str, save: bool = True) -> bool:
        """删除关键词

        Args:
            keyword: 关键词
            save: 是否立即保存到磁盘 (批量更新时设为 False)
        """
        keyword = keyword.lower()
        if keyword in self._keywords:
            del self._keywords[keyword]
            if save:
                self.save()
            logger.info(f"Removed keyword '{keyword}'")
            return True
        return False

    def get_keywords_by_category(self, category: str) -> Dict[str, float]:
        """按类别获取关键词"""
        return {
            name: kw.weight
            for name, kw in self._keywords.items()
            if kw.category == category
        }

    def add_theory_bonus(self, paper: Dict) -> float:
        """计算论文的理论得分加成"""
        if not self._settings.prefer_theory or not self._settings.theory_enabled:
            return 0.0

        text = (paper.get('title', '') + ' ' + paper.get('abstract', '')).lower()
        bonus = 0.0

        for keyword in self._config.get('theory_keywords', []):
            if keyword.lower() in text:
                bonus += self._settings.recency_bonus * 0.2
                break

        return min(bonus, self._settings.recency_bonus)


# 全局单例
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager

    if _config_manager is None:
        _config_manager = ConfigManager()

    return _config_manager


def reload_config() -> bool:
    """重新加载全局配置"""
    global _config_manager
    if _config_manager:
        return _config_manager.reload()
    return False


# ============ 兼容旧代码的辅助函数 ============

def get_core_topics() -> Dict[str, float]:
    """获取核心主题（兼容旧代码）"""
    return get_config().core_keywords


def get_demote_topics() -> Dict[str, float]:
    """获取降权主题（兼容旧代码）"""
    return get_config().demote_keywords


def get_theory_keywords_list() -> List[str]:
    """获取理论关键词列表（兼容旧代码）"""
    return get_config()._config.get('theory_keywords', [])


def get_priority_topics() -> List[str]:
    """获取优先主题列表（兼容旧代码）"""
    return list(get_config().core_keywords.keys())


def get_dislike_topics() -> List[str]:
    """获取不感兴趣主题（兼容旧代码）"""
    return list(get_config().dislike_keywords.keys())


# 测试代码
if __name__ == '__main__':
    config = get_config()
    print("=== 配置管理器测试 ===")
    print(f"核心关键词数量: {len(config.core_keywords)}")
    print(f"降权关键词数量: {len(config.demote_keywords)}")
    print(f"每日论文数: {config._settings.papers_per_day}")
    print(f"数据源: arXiv={config._sources.arxiv_enabled}, 期刊={config._sources.journal_enabled}")
