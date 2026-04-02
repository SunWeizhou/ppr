"""
arXiv Daily Paper Recommender System v2.0
Enh with semantic similarity, caching, and multi-source integration
"""

import json
import os
import re
import ssl
import sqlite3
import hashlib
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import pickle

# 统一日志系统
from logger_config import get_logger, setup_logging
logger = get_logger(__name__)

# 统一配置管理器
from config_manager import get_config, reload_config, ConfigManager

# SSL context
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# ==================== Configuration ====================

CONFIG = {
    'zotero_db_path': '',  # Auto-detect if empty
    'output_dir': os.path.dirname(os.path.abspath(__file__)),
    'cache_dir': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache'),
    'history_dir': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'history'),
    'papers_per_day': 20,
    'arxiv_categories': ['cs.LG', 'stat.ML', 'cs.AI', 'cs.CL', 'math.ST', 'stat.TH', 'stat.ME'],
    'lookback_days': 1,
    'use_semantic_similarity': True,
    'embedding_model': '',  # Auto-detect best model
    'cache_expiry_days': 30,
}

# Update paths from output_dir
if not CONFIG['output_dir'].endswith('arxiv_recommender'):
    CONFIG['output_dir'] = os.path.dirname(os.path.abspath(__file__))
    CONFIG['cache_dir'] = os.path.join(CONFIG['output_dir'], 'cache')
    CONFIG['history_dir'] = os.path.join(CONFIG['output_dir'], 'history')

# ==================== Zotero Path Detection ====================

import platform
import glob as glob_module

def get_zotero_path() -> str:
    """Get Zotero database path with auto-detection."""
    # 1. Check user config
    config = load_user_config()
    if config.get('zotero', {}).get('database_path'):
        path = os.path.expanduser(config['zotero']['database_path'])
        if os.path.exists(path):
            return path

    # 2. Auto-detect based on OS
    system = platform.system()
    candidates = []

    if system == 'Windows':
        candidates = [
            'D:/zetero_data/zotero.sqlite',  # User's current path
            os.path.expanduser('~/Zotero/zotero.sqlite'),
            os.path.expanduser('~/AppData/Roaming/Zotero/Zotero/Profiles/*/zotero.sqlite'),
        ]
        # Also check other drives
        for drive in ['E:', 'F:', 'C:']:
            candidates.extend([
                f'{drive}/zetero_data/zotero.sqlite',
                f'{drive}/Zotero/zotero.sqlite',
            ])
    elif system == 'Darwin':  # macOS
        candidates = [
            os.path.expanduser('~/Zotero/zotero.sqlite'),
            os.path.expanduser('~/Library/Application Support/Zotero/Profiles/*/zotero.sqlite'),
        ]
    else:  # Linux
        candidates = [
            os.path.expanduser('~/Zotero/zotero.sqlite'),
            os.path.expanduser('~/.zotero/zotero.sqlite'),
        ]

    for path in candidates:
        expanded = os.path.expanduser(path)
        if '*' in expanded:
            matches = glob_module.glob(expanded)
            if matches:
                return matches[0]
        elif os.path.exists(expanded):
            return expanded

    # 3. Fallback to default
    return 'D:/zetero_data/zotero.sqlite'


# ==================== Smart Model Selection ====================

def get_best_embedding_model() -> str:
    """Auto-detect best embedding model based on hardware."""
    # Check user config first
    config = load_user_config()
    user_model = config.get('settings', {}).get('embedding_model', '')
    if user_model:
        return user_model

    # Auto-detect based on hardware
    has_gpu, vram = _detect_nvidia_gpu()
    ram_gb = _get_ram_gb()

    if has_gpu and vram >= 6:
        model = 'BAAI/bge-large-en-v1.5'
        reason = f'GPU detected ({vram}GB VRAM)'
    elif ram_gb >= 16:
        model = 'sentence-transformers/all-mpnet-base-v2'
        reason = f'High RAM ({ram_gb}GB)'
    else:
        model = 'sentence-transformers/all-MiniLM-L6-v2'
        reason = f'Standard config ({ram_gb}GB RAM)'

    logger.info(f"Auto-selected model: {model} ({reason})")
    return model


def _detect_nvidia_gpu() -> Tuple[bool, int]:
    """Detect NVIDIA GPU and VRAM."""
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            vram_mb = int(result.stdout.strip().split('\n')[0])
            return True, vram_mb // 1024
    except:
        pass
    return False, 0


def _get_ram_gb() -> int:
    """Get system RAM in GB."""
    try:
        import psutil
        return psutil.virtual_memory().total // (1024**3)
    except:
        # Fallback for Windows without psutil
        try:
            import subprocess
            result = subprocess.run(
                ['wmic', 'computersystem', 'get', 'totalphysicalmemory'],
                capture_output=True, text=True
            )
            ram_bytes = int(result.stdout.split('\n')[1].strip())
            return ram_bytes // (1024**3)
        except:
            return 8  # Default assumption


# Default priority topics (fallback if user config not found)
DEFAULT_PRIORITY_TOPICS = [
    'statistical learning theory', 'in-context learning', 'transformer theory',
    'transformer', 'prompt learning', 'prompt engineering',
    'nonparametric estimation', 'conditional density estimation',
    'conformal prediction', 'generalization theory', 'excess risk analysis',
    'large language model theory', 'LLM theory', 'attention mechanism',
    'theoretical machine learning', 'statistical inference', 'predictive inference',
    'bayesian inference', 'regression', 'generalization bound',
    'neural network theory', 'overparameterization', 'double descent', 'minimax optimality',
]

# ==================== 配置管理（使用统一配置管理器）====================

def load_user_config() -> Dict:
    """Load user configuration - 使用统一配置管理器."""
    config = get_config()
    return {
        'research_focus': {
            'topics': list(config.core_keywords.keys()),
            'weight': 3.0
        },
        'dislike_topics': {
            'topics': list(config.dislike_keywords.keys())
        },
        'settings': {
            'papers_per_day': config._settings.papers_per_day,
            'prefer_theory': config._settings.prefer_theory,
        },
        'zotero': {
            'database_path': config._zotero.database_path,
            'enabled': config._zotero.enabled,
        }
    }


def save_user_config(config: Dict) -> bool:
    """Save user configuration - 使用统一配置管理器."""
    try:
        cm = get_config()

        # 更新关键词
        if 'research_focus' in config and 'topics' in config['research_focus']:
            for topic in config['research_focus']['topics']:
                if topic not in cm.all_keywords:
                    cm.set_keyword(topic, 3.0, 'core')

        # 更新不感兴趣主题
        if 'dislike_topics' in config and 'topics' in config['dislike_topics']:
            for topic in config['dislike_topics']['topics']:
                cm.set_keyword(topic, -1.0, 'dislike')

        return True
    except Exception as e:
        logger.error(f"Error saving user config: {e}")
        return False


def get_priority_topics() -> List[str]:
    """Get priority topics from unified config."""
    return list(get_config().core_keywords.keys())


def get_dislike_topics() -> List[str]:
    """Get topics to deprioritize from unified config."""
    return list(get_config().dislike_keywords.keys())


def get_topic_weights() -> Dict[str, float]:
    """Get topic weights from unified config."""
    return get_config().core_keywords


# ==================== Keywords Configuration（使用统一配置管理器）====================

# 保留旧的配置文件路径用于迁移
KEYWORDS_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keywords_config.json')


def load_keywords_config() -> Dict:
    """Load keywords configuration - 使用统一配置管理器."""
    cm = get_config()
    return {
        'core_topics': cm.core_keywords,
        'secondary_topics': cm.get_keywords_by_category('secondary'),
        'theory_keywords': cm._config.get('theory_keywords', []),
        'demote_topics': cm.demote_keywords,
        'dislike_topics': list(cm.dislike_keywords.keys())
    }


def save_keywords_config(config: Dict) -> bool:
    """Save keywords configuration - 使用统一配置管理器."""
    try:
        cm = get_config()

        # 更新核心主题
        if 'core_topics' in config:
                for topic, weight in config['core_topics'].items():
                    cm.set_keyword(topic, weight, 'core')

        # 更新次要主题
        if 'secondary_topics' in config:
                for topic, weight in config['secondary_topics'].items():
                    cm.set_keyword(topic, weight, 'secondary')

        # 更新降权主题
        if 'demote_topics' in config:
                for topic, weight in config['demote_topics'].items():
                    cm.set_keyword(topic, weight, 'demote')

        # 更新不感兴趣主题
        if 'dislike_topics' in config:
                for topic in config['dislike_topics']:
                    cm.set_keyword(topic, -1.0, 'dislike')

        return True
    except Exception as e:
        logger.error(f"Error saving keywords config: {e}")
        return False


def get_core_topics() -> Dict[str, float]:
    """Get core topics from unified config."""
    return get_config().core_keywords


def get_secondary_topics() -> Dict[str, float]:
    """Get secondary topics from unified config."""
    return get_config().get_keywords_by_category('secondary')


def get_theory_keywords() -> List[str]:
    """Get theory keywords from unified config."""
    return get_config()._config.get('theory_keywords', [
        "theorem", "proof", "bound", "convergence", "statistical",
        "bayesian", "estimation", "generalization", "asymptotic",
        "minimax", "optimal", "rate", "complexity", "guarantee"
    ])


def get_demote_topics() -> Dict[str, float]:
    """Get demote topics from unified config."""
    return get_config().demote_keywords


def get_dislike_topics_list() -> List[str]:
    """Get dislike topics from unified config."""
    return list(get_config().dislike_keywords.keys())


# ==================== User Feedback Learning ====================

def load_user_feedback(cache_dir: str) -> Dict:
    """Load user feedback from file."""
    feedback_file = os.path.join(cache_dir, 'user_feedback.json')
    if os.path.exists(feedback_file):
        try:
            with open(feedback_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'liked': [], 'disliked': [], 'topic_adjustments': {}}


def learn_from_feedback(feedback: Dict, papers: List[Dict]) -> Dict[str, float]:
    """Learn topic weights from user feedback."""
    priority_topics = get_priority_topics()
    topic_weights = get_topic_weights()

    if not feedback.get('liked') and not feedback.get('disliked'):
        return topic_weights

    # Analyze liked papers
    liked_topics = Counter()
    disliked_topics = Counter()

    all_papers_by_id = {p['id']: p for p in papers}

    for paper_id in feedback.get('liked', []):
        if paper_id in all_papers_by_id:
            paper = all_papers_by_id[paper_id]
            text = (paper['title'] + ' ' + paper.get('abstract', '')).lower()
            for topic in priority_topics:
                if topic.lower() in text:
                    liked_topics[topic] += 1

    for paper_id in feedback.get('disliked', []):
        if paper_id in all_papers_by_id:
            paper = all_papers_by_id[paper_id]
            text = (paper['title'] + ' ' + paper.get('abstract', '')).lower()
            for topic in priority_topics:
                if topic.lower() in text:
                    disliked_topics[topic] += 1

    # Adjust weights
    for topic in priority_topics:
        liked = liked_topics.get(topic, 0)
        disliked = disliked_topics.get(topic, 0)
        if liked > disliked:
            topic_weights[topic] = min(4.0, topic_weights[topic] + 0.5 * (liked - disliked))
        elif disliked > liked:
            topic_weights[topic] = max(0.5, topic_weights[topic] - 0.5 * (disliked - liked))

    return topic_weights

TOP_INSTITUTIONS = [
    'MIT', 'Stanford', 'CMU', 'Carnegie Mellon', 'Berkeley', 'UC Berkeley',
    'Oxford', 'Cambridge', 'ETH Zurich', 'Princeton', 'Harvard',
    'Tsinghua', 'Peking University', 'Caltech', 'Google DeepMind',
    'Google Research', 'Microsoft Research', 'OpenAI', 'Anthropic',
    'Meta AI', 'FAIR', 'NYU', 'University of Toronto', 'Weizmann',
    'INRIA', 'Max Planck', 'TTIC'
]

KNOWN_AUTHORS = [
    'Peter Bartlett', 'Andreas Maurer', 'Massimiliano Pontil', 'Ben Recht',
    'Bin Yu', 'Trevor Hastie', 'Rob Tibshirani', 'Martin Wainwright',
    'Michael Jordan', 'Stuart Russell', 'Percy Liang', 'John Duchi',
    'Emmanuel Candes', 'Yoram Singer', 'Elad Hazan', 'Sham Kakade',
    'Sanjeev Arora', 'Avrim Blum', 'Nati Srebro', 'Nina Balcan',
    'Gabor Lugosi', 'Alexandre Tsybakov', 'Olivier Bousquet', 'Leon Bottou',
    'Francis Bach', 'Stephane Boucheron', 'Taiji Suzuki', 'Kenji Fukumizu',
    'Arthur Gretton', 'Bernhard Scholkopf', 'Jonas Peters', 'Dominik Janzing',
    'Jing Lei', 'Larry Wasserman', 'Aaditya Ramdas', 'Rina Barber',
    'Lihua Lei', 'Sayan Mukherjee', 'Cun-hui Zhang', 'Jason Lee',
    'Tengyu Ma', 'Yuanzhi Li', 'Zeyuan Allen-Zhu', 'Suriya Gunasekar'
]


# ==================== Semantic Similarity ====================

# Global model cache to avoid reloading
_CACHED_MODEL = None
_CACHED_MODEL_NAME = None

class SemanticSimilarity:
    """Compute semantic similarity with smart caching."""

    CACHE_FILE = None  # Set after CONFIG is loaded

    def __init__(self, model_name: str = '', cache_dir: str = None):
        global _CACHED_MODEL, _CACHED_MODEL_NAME
        self.model_name = model_name or get_best_embedding_model()
        self.cache_dir = cache_dir or CONFIG.get('cache_dir', 'cache')
        self._cache_file = os.path.join(self.cache_dir, 'zotero_embedding.pkl')

        # Reuse cached model if same model name
        if _CACHED_MODEL_NAME == self.model_name and _CACHED_MODEL is not None:
            self.model = _CACHED_MODEL
            self.zotero_embedding = None
        else:
            self.model = None
            self.zotero_embedding = None

    def _load_model(self):
        """Lazy load the model with auto device detection and global caching."""
        global _CACHED_MODEL, _CACHED_MODEL_NAME

        # Check global cache first
        if _CACHED_MODEL is not None and _CACHED_MODEL_NAME == self.model_name:
            self.model = _CACHED_MODEL
            return True

        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer

                # Always use CPU for MiniLM (fast enough, more reliable)
                device = 'cpu'

                logger.info(f"Loading embedding model: {self.model_name} (device: {device})")
                self.model = SentenceTransformer(self.model_name, device=device)

                # Cache globally
                _CACHED_MODEL = self.model
                _CACHED_MODEL_NAME = self.model_name

            except ImportError:
                logger.warning("sentence-transformers not installed. Using keyword matching.")
                return False
        return True

    def _get_fingerprint(self, papers: List[Dict], zotero_path: str) -> Dict:
        """Get quick fingerprint to detect changes."""
        return {
            'count': len(papers),
            'db_mtime': os.path.getmtime(zotero_path) if os.path.exists(zotero_path) else 0,
        }

    def compute_zotero_embedding(self, papers: List[Dict], zotero_path: str = None):
        """Compute embedding with smart cache invalidation."""
        if not self._load_model():
            return None

        zotero_path = zotero_path or get_zotero_path()
        current_fp = self._get_fingerprint(papers, zotero_path)

        # Try loading cache
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, 'rb') as f:
                    cached = pickle.load(f)
                if (cached.get('fingerprint', {}).get('count') == current_fp['count'] and
                    cached.get('fingerprint', {}).get('db_mtime') == current_fp['db_mtime']):
                    logger.debug(f"Using cached embedding ({len(papers)} papers)")
                    self.zotero_embedding = cached['embedding']
                    return self.zotero_embedding
            except Exception as e:
                logger.warning(f"Cache read error: {e}")

        # Compute new embedding
        logger.info(f"Computing embedding for {len(papers)} papers...")
        texts = [p['title'] + ' ' + (p.get('abstract', '') or '')[:500] for p in papers]
        embeddings = self.model.encode(texts, show_progress_bar=False)  # Disable for Windows compatibility
        self.zotero_embedding = embeddings.mean(axis=0)

        # Save cache
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self._cache_file, 'wb') as f:
                pickle.dump({'embedding': self.zotero_embedding, 'fingerprint': current_fp}, f)
            logger.debug("Embedding cached successfully")
        except Exception as e:
            logger.warning(f"Cache save error: {e}")

        return self.zotero_embedding

    def compute_similarity(self, paper: Dict) -> float:
        """Compute semantic similarity between paper and Zotero library."""
        if self.model is None or self.zotero_embedding is None:
            return 0.0

        text = paper['title']
        if paper.get('abstract'):
            text += ' ' + paper['abstract'][:500]

        paper_embedding = self.model.encode([text], show_progress_bar=False)[0]

        # Cosine similarity
        from numpy import dot
        from numpy.linalg import norm
        similarity = dot(self.zotero_embedding, paper_embedding) / (
            norm(self.zotero_embedding) * norm(paper_embedding)
        )
        return float(similarity)


# ==================== Paper Cache ====================

class PaperCache:
    """Cache for seen papers to avoid duplicates."""

    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, 'paper_cache.json')
        self.history_file = os.path.join(cache_dir, 'recommendation_history.json')
        self.seen_papers = {}  # paper_id -> first_seen_date
        self.recommendation_history = {}  # date -> [paper_ids]
        self._load()

    def _load(self):
        """Load cache from disk."""
        os.makedirs(self.cache_dir, exist_ok=True)

        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.seen_papers = json.load(f)
            except:
                self.seen_papers = {}

        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.recommendation_history = json.load(f)
            except:
                self.recommendation_history = {}

    def _save(self):
        """Save cache to disk."""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.seen_papers, f, ensure_ascii=False, indent=2)

        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.recommendation_history, f, ensure_ascii=False, indent=2)

    def mark_seen(self, paper_id: str):
        """Mark a paper as seen."""
        self.seen_papers[paper_id] = datetime.now().strftime('%Y-%m-%d')
        self._save()

    def is_seen(self, paper_id: str) -> bool:
        """Check if paper has been seen."""
        return paper_id in self.seen_papers

    def record_recommendation(self, date: str, paper_ids: List[str]):
        """Record daily recommendations."""
        self.recommendation_history[date] = paper_ids
        for pid in paper_ids:
            self.mark_seen(pid)
        self._save()

    def cleanup_old_entries(self, days: int = 30):
        """Remove entries older than specified days."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        self.seen_papers = {
            k: v for k, v in self.seen_papers.items()
            if (isinstance(v, str) and v >= cutoff) or isinstance(v, dict)
        }
        self._save()

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            'total_seen': len(self.seen_papers),
            'days_with_recommendations': len(self.recommendation_history)
        }


# ==================== Multi-Source Fetcher ====================

class MultiSourceFetcher:
    """Fetch papers from multiple sources."""

    def __init__(self, categories: List[str], cache: PaperCache):
        self.categories = categories
        self.cache = cache

    def fetch_all_sources(self, days: int = 1) -> List[Dict]:
        """Fetch papers from all sources."""
        all_papers = []

        # Source 1: arXiv (try combined query first, then fallback to individual)
        logger.info("Fetching from arXiv...")
        arxiv_papers = self._fetch_arxiv_combined(days)
        if not arxiv_papers:
            logger.warning("Combined query failed, trying individual categories...")
            arxiv_papers = self._fetch_arxiv(days)
        all_papers.extend(arxiv_papers)
        logger.info(f"Found {len(arxiv_papers)} papers from arXiv")

        # Source 2: Topic-focused search (主动搜索用户关心的主题)
        logger.info("Searching for priority topics...")
        topic_papers = self._fetch_by_topics(days)
        for p in topic_papers:
            if p['id'] not in [x['id'] for x in all_papers]:
                all_papers.append(p)
        logger.info(f"Found {len(topic_papers)} papers from topic search")

        # Source 3: Recent submissions (last 7 days if today is empty)
        if len(arxiv_papers) < 50:
            logger.info("Fetching from arXiv (extended range)...")
            extended_papers = self._fetch_arxiv_combined(min(days + 7, 14))
            if not extended_papers:
                extended_papers = self._fetch_arxiv(min(days + 7, 14))
            for p in extended_papers:
                if p['id'] not in [x['id'] for x in all_papers]:
                    all_papers.append(p)
            logger.info(f"Total: {len(all_papers)} papers")

        # Remove already seen papers
        new_papers = [p for p in all_papers if not self.cache.is_seen(p['id'])]
        logger.info(f"After removing seen papers: {len(new_papers)}")

        return new_papers

    def _fetch_by_topics(self, days: int) -> List[Dict]:
        """Fetch papers by searching for specific topics (主动搜索)."""
        papers = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 从用户配置获取优先主题
        config = load_user_config()
        priority_topics = config.get('research_focus', {}).get('topics', [])

        # 默认主题
        if not priority_topics:
            priority_topics = ['in-context learning', 'ICL', 'prompt learning', 'conformal prediction']

        # 对每个主题进行搜索
        for topic in priority_topics[:5]:  # 最多搜索5个主题
            try:
                # 使用标题和摘要搜索
                params = {
                    'search_query': f'all:"{topic}"',
                    'start': 0,
                    'max_results': 50,
                    'sortBy': 'submittedDate',
                    'sortOrder': 'descending'
                }

                url = f"http://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"

                req = urllib.request.Request(url, headers={'User-Agent': 'arxiv-recommender/2.4'})
                with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as response:
                    xml_data = response.read().decode('utf-8')
                    topic_papers = self._parse_arxiv_xml(xml_data)

                    for paper in topic_papers:
                        try:
                            pub_date = datetime.strptime(paper['published'][:10], '%Y-%m-%d')
                            if pub_date >= start_date:
                                paper['_topic_match'] = topic  # 标记匹配的主题
                                papers.append(paper)
                        except:
                            pass

                    if topic_papers:
                        logger.debug(f"'{topic}': {len([p for p in topic_papers if datetime.strptime(p['published'][:10], '%Y-%m-%d') >= start_date])} papers")

                # Rate limiting
                time.sleep(3)

            except Exception as e:
                logger.warning(f"Error searching '{topic}': {e}")
                continue

        # 去重
        seen = set()
        unique = []
        for p in papers:
            if p['id'] not in seen:
                seen.add(p['id'])
                unique.append(p)

        return unique

    def _fetch_arxiv_combined(self, days: int) -> List[Dict]:
        """Fetch papers using a SINGLE combined query (minimizes API calls)."""
        papers = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Combine all categories into ONE query
        cat_query = ' OR '.join([f'cat:{cat}' for cat in self.categories])
        params = {
            'search_query': f'({cat_query})',
            'start': 0,
            'max_results': 500,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }

        url = f"http://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"

        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'arxiv-recommender/2.3'
                })
                with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as response:
                    xml_data = response.read().decode('utf-8')
                    all_papers = self._parse_arxiv_xml(xml_data)

                    for paper in all_papers:
                        try:
                            pub_date = datetime.strptime(paper['published'][:10], '%Y-%m-%d')
                            if pub_date >= start_date:
                                papers.append(paper)
                        except:
                            papers.append(paper)

                    logger.debug(f"Combined query: {len(papers)} papers in date range")
                    return papers

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait_time = (attempt + 1) * 60
                    logger.warning(f"Rate limited (429), waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"HTTP error: {e.code}")
                    break
            except Exception as e:
                logger.error(f"Fetch error: {e}")
                if attempt < 2:
                    time.sleep(30)

        return papers

    def _fetch_arxiv(self, days: int) -> List[Dict]:
        """Fetch papers from arXiv API with retry and rate limiting."""
        papers = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        def fetch_with_retry(url: str, max_retries: int = 3) -> Optional[str]:
            """Fetch URL with exponential backoff on rate limit errors."""
            for attempt in range(max_retries):
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'arxiv-recommender/2.3'})
                    with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as response:
                        return response.read().decode('utf-8')
                except urllib.error.HTTPError as e:
                    if e.code == 429:  # Rate limited
                        wait_time = (attempt + 1) * 30  # 30, 60, 90 seconds
                        logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                    else:
                        raise
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(10)
            return None

        for i, category in enumerate(self.categories):
            params = {
                'search_query': f'cat:{category}',
                'start': 0,
                'max_results': 150,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }

            url = f"http://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"

            try:
                xml_data = fetch_with_retry(url)
                if xml_data:
                    category_papers = self._parse_arxiv_xml(xml_data)

                    for paper in category_papers:
                        try:
                            pub_date = datetime.strptime(paper['published'][:10], '%Y-%m-%d')
                            if pub_date >= start_date:
                                papers.append(paper)
                        except:
                            papers.append(paper)
                    logger.debug(f"{category}: {len(category_papers)} papers")
                else:
                    logger.warning(f"{category}: Failed after retries")

            except Exception as e:
                logger.error(f"Error fetching {category}: {e}")

            # Rate limiting: wait between requests to avoid 429 errors
            # arXiv recommends 3+ seconds between requests
            if i < len(self.categories) - 1:
                time.sleep(5)

        # Remove duplicates
        seen = set()
        unique = []
        for p in papers:
            if p['id'] not in seen:
                seen.add(p['id'])
                unique.append(p)

        return unique

    def _parse_arxiv_xml(self, xml_data: str) -> List[Dict]:
        """Parse arXiv API XML response."""
        papers = []
        try:
            root = ET.fromstring(xml_data)
            ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

            for entry in root.findall('atom:entry', ns):
                paper = {}

                title_elem = entry.find('atom:title', ns)
                paper['title'] = title_elem.text.strip() if title_elem is not None else ''

                authors = []
                for author in entry.findall('atom:author', ns):
                    name_elem = author.find('atom:name', ns)
                    if name_elem is not None:
                        authors.append(name_elem.text)
                paper['authors'] = authors

                abstract_elem = entry.find('atom:summary', ns)
                paper['abstract'] = abstract_elem.text.strip() if abstract_elem is not None else ''

                published_elem = entry.find('atom:published', ns)
                paper['published'] = published_elem.text if published_elem is not None else ''

                link_elem = entry.find('atom:id', ns)
                paper['id'] = link_elem.text.split('/abs/')[-1] if link_elem is not None else ''
                paper['link'] = link_elem.text if link_elem is not None else ''
                paper['source'] = 'arXiv'

                categories = []
                for cat in entry.findall('atom:category', ns):
                    term = cat.get('term')
                    if term:
                        categories.append(term)
                paper['categories'] = categories

                comment_elem = entry.find('arxiv:comment', ns)
                paper['comment'] = comment_elem.text if comment_elem is not None else ''

                papers.append(paper)
        except Exception as e:
            logger.error(f"XML parsing error: {e}")

        return papers


# ==================== Enhanced Scorer ====================

class EnhancedScorer:
    """Enhanced paper scorer with smart keyword matching."""

    def __init__(self, semantic: 'SemanticSimilarity', use_semantic: bool = True, topic_weights: Dict[str, float] = None):
        self.semantic = semantic
        self.use_semantic = use_semantic
        self.topic_weights = topic_weights or {}
        # Load dynamic keywords from config
        self._load_keywords()

    def _load_keywords(self):
        """Load keywords from unified config manager."""
        cm = get_config()
        self.CORE_TOPICS = cm.core_keywords
        self.SECONDARY_TOPICS = cm.get_keywords_by_category('secondary')
        self.THEORY_KEYWORDS = cm._config.get('theory_keywords', [])
        self.DEMOTE_TOPICS = cm.demote_keywords
        self.DISLIKE_TOPICS = list(cm.dislike_keywords.keys())
        # Keep SYNONYMS as class attribute (not configurable for now)
        if not hasattr(self, 'SYNONYMS'):
            self.SYNONYMS = {
                'bound': ['guarantee', 'limit', 'upper bound', 'lower bound'],
                'convergence': ['converge', 'convergent'],
                'inference': ['estimation', 'inference'],
                'regression': ['regressor', 'regress'],
            }

    def compute_score(self, paper: Dict) -> Tuple[float, Dict]:
        """Compute overall score."""
        relevance = self._compute_relevance(paper)
        author = self._compute_author_influence(paper)
        depth = self._compute_technical_depth(paper)
        semantic_sim = self._compute_semantic_score(paper)

        # 关键词匹配为主，语义匹配为辅
        if self.use_semantic and semantic_sim > 0:
            total = relevance * 0.50 + author * 0.10 + depth * 0.10 + semantic_sim * 0.30
        else:
            total = relevance * 0.70 + author * 0.15 + depth * 0.15

        details = {
            'relevance': relevance,
            'author': author,
            'depth': depth,
            'semantic': semantic_sim,
            'breakdown': self._get_breakdown(paper, semantic_sim)
        }

        return total, details

    def _count_keyword(self, text: str, keyword: str) -> int:
        """Count keyword occurrences with flexible matching.

        Handles:
        - Multi-word keywords like "conformal prediction"
        - Hyphenated keywords like "in-context learning"
        - Case insensitive matching
        """
        keyword_lower = keyword.lower()
        text_lower = text.lower()

        # 对于多词关键词（包含空格或连字符），使用子字符串匹配
        if ' ' in keyword_lower or '-' in keyword_lower:
            # 直接子字符串匹配
            return text_lower.count(keyword_lower)
        else:
            # 单词使用词边界匹配
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            return len(re.findall(pattern, text_lower))

    def _compute_relevance(self, paper: Dict) -> float:
        """Compute topic relevance with smart keyword matching."""
        title = paper.get('title', '').lower()
        abstract = paper.get('abstract', '').lower()
        score = 0.0
        matched_topics = []

        # 1. 核心主题匹配（标题3倍权重 + 词频加权）
        for topic, weight in self.CORE_TOPICS.items():
            title_count = self._count_keyword(title, topic)
            abstract_count = self._count_keyword(abstract, topic)

            if title_count > 0 or abstract_count > 0:
                # 标题权重3倍，摘要权重1倍，词频上限3次
                topic_score = weight * (min(title_count, 3) * 3.0 + min(abstract_count, 3) * 1.0) / 4.0
                score += topic_score
                matched_topics.append(topic)

        # 2. 次要主题匹配（标题2倍权重）
        for topic, weight in self.SECONDARY_TOPICS.items():
            title_count = self._count_keyword(title, topic)
            abstract_count = self._count_keyword(abstract, topic)

            if title_count > 0 or abstract_count > 0:
                topic_score = weight * (min(title_count, 2) * 2.0 + min(abstract_count, 2) * 1.0) / 3.0
                score += topic_score

        # 3. 同义词扩展
        for base_word, synonyms in self.SYNONYMS.items():
            for syn in synonyms:
                if self._count_keyword(title, syn) > 0:
                    score += 0.5  # 同义词在标题中匹配

        # 4. 降权主题（惩罚）
        for topic, penalty in self.DEMOTE_TOPICS.items():
            if self._count_keyword(title + ' ' + abstract, topic) > 0:
                # 如果有核心主题同时出现，减轻惩罚
                if matched_topics:
                    score += penalty * 0.3
                else:
                    score += penalty

        # 5. 用户配置的主题权重（兼容旧配置）
        for topic, weight in self.topic_weights.items():
            if topic.lower() not in self.CORE_TOPICS and topic.lower() not in self.SECONDARY_TOPICS:
                if self._count_keyword(title, topic) > 0:
                    score += weight * 0.5

        # 6. 理论关键词加分（从用户配置）
        theory_keywords = ['theorem', 'proof', 'bound', 'convergence', 'statistical',
                          'bayesian', 'estimation', 'generalization']
        for kw in theory_keywords:
            if self._count_keyword(title, kw) > 0:
                score += 0.4

        # 7. dislike topics 惩罚 (使用词边界匹配，与其他主题一致)
        for topic in get_dislike_topics():
            if self._count_keyword(title + ' ' + abstract, topic) > 0:
                if not matched_topics:  # 没有核心主题时才惩罚
                    score -= 1.0

        # 8. 主动搜索匹配加分（最高优先级）
        if paper.get('_topic_match'):
            # 通过主题搜索找到的论文，给予额外加分
            score += 2.0

        return min(max(score, 0), 10)

    def _compute_author_influence(self, paper: Dict) -> float:
        """Compute author influence."""
        score = 0.0
        authors_text = ' '.join(paper.get('authors', [])).lower()
        all_text = (paper.get('abstract', '') + ' ' + (paper.get('comment') or '')).lower()

        for inst in TOP_INSTITUTIONS:
            pattern = r'\b' + re.escape(inst.lower()) + r'\b'
            if re.search(pattern, all_text):
                score += 1.5
                break

        for author in KNOWN_AUTHORS:
            if author.lower() in authors_text:
                score += 2.0
                break

        venues = ['neurips', 'icml', 'iclr', 'colt', 'jmlr', 'aistats']
        for venue in venues:
            if venue in all_text:
                score += 1.5
                break

        # 关注学者加分（最高优先级）
        try:
            my_scholars_path = os.path.join(CONFIG['output_dir'], 'my_scholars.json')
            if os.path.exists(my_scholars_path):
                with open(my_scholars_path, 'r', encoding='utf-8') as f:
                    my_scholars = json.load(f)
                for scholar in my_scholars.get('scholars', []):
                    scholar_name = scholar.get('name', '').lower()
                    # 匹配姓氏或全名
                    if scholar_name in authors_text or any(
                        part in authors_text for part in scholar_name.split() if len(part) > 2
                    ):
                        score += 3.0  # 关注学者的论文给予高分
                        break
        except Exception as e:
            logger.debug(f"Error loading my_scholars: {e}")

        return min(score, 5)

    def _compute_technical_depth(self, paper: Dict) -> float:
        """Compute technical depth."""
        text = (paper['title'] + ' ' + paper.get('abstract', '')).lower()
        score = 0.0

        indicators = [
            ('theorem', 1.0), ('proof', 1.0), ('bound', 0.8),
            ('convergence', 0.8), ('minimax', 1.0), ('asymptotic', 0.7),
            ('rademacher', 1.0), ('pac-bayes', 1.0), ('excess risk', 1.2),
            ('sample complexity', 1.0), ('statistical guarantee', 1.0)
        ]

        for indicator, weight in indicators:
            if indicator in text:
                score += weight

        if 'math.ST' in paper.get('categories', []):
            score += 1.5

        return min(score, 5)

    def _compute_semantic_score(self, paper: Dict) -> float:
        """Compute semantic similarity score (0-10 scale)."""
        if self.use_semantic and self.semantic is not None:
            sim = self.semantic.compute_similarity(paper)
            return sim * 10  # Scale to 0-10
        return 0.0

    def _get_breakdown(self, paper: Dict, semantic_sim: float) -> List[Dict]:
        """Get structured breakdown with icons and score impacts."""
        reasons = []
        title = paper.get('title', '')
        abstract = paper.get('abstract', '')
        title_lower = title.lower()
        abstract_lower = abstract.lower()

        # 1. 核心主题匹配
        for topic, weight in self.CORE_TOPICS.items():
            title_count = self._count_keyword(title_lower, topic)
            abstract_count = self._count_keyword(abstract_lower, topic)
            if title_count > 0:
                reasons.append({
                    'type': 'core_topic',
                    'icon': '🎯',
                    'text': f"命中核心主题: {topic}",
                    'location': '标题',
                    'score_impact': weight * 0.8
                })
                break
            elif abstract_count > 0:
                reasons.append({
                    'type': 'core_topic',
                    'icon': '🎯',
                    'text': f"命中核心主题: {topic}",
                    'location': '摘要',
                    'score_impact': weight * 0.3
                })
                break

        # 2. 次要主题匹配
        if not any(r['type'] == 'core_topic' for r in reasons):
            for topic, weight in self.SECONDARY_TOPICS.items():
                if self._count_keyword(title_lower + ' ' + abstract_lower, topic) > 0:
                    reasons.append({
                        'type': 'secondary_topic',
                        'icon': '📌',
                        'text': f"相关主题: {topic}",
                        'location': '',
                        'score_impact': weight * 0.2
                    })
                    break

        # 3. 语义相似度
        if semantic_sim > 0.5:
            reasons.append({
                'type': 'semantic',
                'icon': '🔗',
                'text': f"与您的 Zotero 库语义相近 ({semantic_sim:.1%})",
                'location': '',
                'score_impact': semantic_sim * 0.3
            })

        # 4. 知名作者
        authors_text = ' '.join(paper.get('authors', [])).lower()
        for author in KNOWN_AUTHORS:
            if author.lower() in authors_text:
                reasons.append({
                    'type': 'author',
                    'icon': '👤',
                    'text': f"知名作者: {author}",
                    'location': '',
                    'score_impact': 2.0
                })
                break

        # 5. 顶级机构 (使用单词边界匹配避免误报)
        all_text = title_lower + ' ' + abstract_lower + ' ' + (paper.get('comment') or '').lower()
        for inst in TOP_INSTITUTIONS:
            # Use word boundary to avoid false positives (e.g., "MIT" in "limited")
            pattern = r'\b' + re.escape(inst.lower()) + r'\b'
            if re.search(pattern, all_text):
                reasons.append({
                    'type': 'institution',
                    'icon': '🏛️',
                    'text': f"来自 {inst}",
                    'location': '',
                    'score_impact': 1.5
                })
                break

        # 6. 新论文
        published = paper.get('published', '')
        if published:
            try:
                pub_date = datetime.strptime(published[:10], '%Y-%m-%d')
                days_old = (datetime.now() - pub_date).days
                if days_old <= 7:
                    reasons.append({
                        'type': 'recency',
                        'icon': '🆕',
                        'text': f"近{days_old}天新论文",
                        'location': '',
                        'score_impact': 0.3
                    })
            except:
                pass

        # 7. 理论深度
        theory_keywords = ['theorem', 'proof', 'bound', 'convergence', 'minimax', 'optimal rate']
        theory_matches = [kw for kw in theory_keywords if kw in title_lower or kw in abstract_lower]
        if len(theory_matches) >= 2:
            reasons.append({
                'type': 'theory',
                'icon': '📐',
                'text': f"包含理论贡献: {', '.join(theory_matches[:2])}",
                'location': '',
                'score_impact': 0.5
            })

        return reasons[:4]  # 最多显示4条理由

    def _get_breakdown_text(self, paper: Dict, semantic_sim: float) -> str:
        """Get text-only breakdown for backwards compatibility."""
        reasons = self._get_breakdown(paper, semantic_sim)
        return '; '.join([r['text'] for r in reasons]) if reasons else '匹配您的研究兴趣'


# ==================== Output Generators ====================

class HTMLGenerator:
    """Generate enhanced HTML page with keyword management."""

    def generate(self, papers: List[Dict], themes: List[str], date: str, stats: Dict) -> str:
        # Load current keywords config
        keywords_config = load_keywords_config()
        core_topics = keywords_config.get('core_topics', {})
        secondary_topics = keywords_config.get('secondary_topics', {})
        theory_keywords = keywords_config.get('theory_keywords', [])
        demote_topics = keywords_config.get('demote_topics', {})
        dislike_topics = keywords_config.get('dislike_topics', [])

        # Extract today's matched keywords from papers (only show top 10)
        today_keywords = self._extract_today_keywords(papers, core_topics, secondary_topics, theory_keywords)[:10]
        today_keywords_html = ''.join([f'<span class="today-keyword-tag">{kw}</span>' for kw in today_keywords])

        # Format keywords for display
        core_topics_html = self._generate_keyword_tags(core_topics, 'core')
        secondary_topics_html = self._generate_keyword_tags(secondary_topics, 'secondary')
        theory_keywords_html = self._generate_keyword_tags({k: 1.0 for k in theory_keywords}, 'theory')
        demote_topics_html = self._generate_keyword_tags(demote_topics, 'demote')
        dislike_topics_html = self._generate_keyword_tags({k: 1.0 for k in dislike_topics}, 'dislike')

        # JSON for JavaScript
        keywords_config_json = json.dumps(keywords_config, ensure_ascii=False)

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>arXiv Daily Digest - {date}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh; color: #e0e0e0; padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{
            text-align: center; padding: 40px 20px;
            background: rgba(255,255,255,0.03); border-radius: 24px;
            margin-bottom: 30px; border: 1px solid rgba(255,255,255,0.08);
        }}
        .header h1 {{
            font-size: 2.8em;
            background: linear-gradient(135deg, #00d4ff 0%, #7c3aed 50%, #f472b6 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 15px;
        }}
        .date {{ font-size: 1.3em; color: #888; margin-bottom: 20px; }}
        .themes {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin: 20px 0; }}
        .theme-tag {{
            background: linear-gradient(135deg, rgba(124,58,237,0.3), rgba(0,212,255,0.3));
            padding: 8px 18px; border-radius: 20px; font-size: 0.9em; color: #fff;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .stats {{ display: flex; justify-content: center; gap: 50px; margin-top: 30px; padding-top: 25px; border-top: 1px solid rgba(255,255,255,0.1); }}
        .stat {{ text-align: center; }}
        .stat-number {{ font-size: 2.2em; font-weight: bold; color: #00d4ff; }}
        .stat-label {{ font-size: 0.85em; color: #666; margin-top: 5px; }}
        .papers-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 20px; }}
        .paper-card {{
            background: rgba(255,255,255,0.03); border-radius: 16px; padding: 25px;
            border: 1px solid rgba(255,255,255,0.06);
            transition: all 0.3s ease; position: relative; overflow: hidden;
        }}
        .paper-card::before {{
            content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
            background: linear-gradient(90deg, #00d4ff, #7c3aed); opacity: 0; transition: opacity 0.3s;
        }}
        .paper-card:hover {{ transform: translateY(-5px); border-color: rgba(0,212,255,0.3); }}
        .paper-card:hover::before {{ opacity: 1; }}
        .paper-title {{ font-size: 1.1em; font-weight: 600; color: #fff; margin-bottom: 12px; line-height: 1.5; }}
        .paper-title a {{ color: #fff; text-decoration: none; }}
        .paper-title a:hover {{ color: #00d4ff; }}
        .paper-authors {{ font-size: 0.85em; color: #888; margin-bottom: 15px; }}
        .paper-summary {{ font-size: 0.9em; color: #aaa; line-height: 1.7; margin-bottom: 15px; }}
        .paper-meta {{
            display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 15px;
        }}
        .meta-tag {{
            background: rgba(0,212,255,0.15); padding: 4px 10px; border-radius: 12px;
            font-size: 0.75em; color: #00d4ff;
        }}
        .paper-relevance {{
            background: rgba(124,58,237,0.15); padding: 12px; border-radius: 10px;
            margin-bottom: 15px; border-left: 3px solid #7c3aed;
        }}
        .paper-relevance-title {{ font-size: 0.8em; color: #7c3aed; font-weight: 600; margin-bottom: 8px; }}
        .paper-relevance-text {{ font-size: 0.85em; color: #ccc; }}
        .paper-relevance-items {{ display: flex; flex-direction: column; gap: 6px; }}
        .relevance-item {{
            display: flex; align-items: center; gap: 8px; font-size: 0.85em;
            padding: 4px 0;
        }}
        .relevance-icon {{ font-size: 1.1em; min-width: 24px; text-align: center; }}
        .relevance-text {{ color: #ddd; flex: 1; }}
        .relevance-location {{
            font-size: 0.8em; color: #888; background: rgba(255,255,255,0.1);
            padding: 2px 6px; border-radius: 4px;
        }}
        .relevance-score-impact {{
            font-size: 0.75em; color: #22c55e; font-weight: 600;
            background: rgba(34,197,94,0.15); padding: 2px 6px; border-radius: 4px;
        }}
        .paper-footer {{
            display: flex; justify-content: space-between; align-items: center;
            padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.08);
        }}
        .score-badge {{
            background: linear-gradient(135deg, #7c3aed, #00d4ff);
            padding: 5px 14px; border-radius: 15px; font-size: 0.85em; font-weight: bold;
        }}
        .paper-link {{ color: #00d4ff; text-decoration: none; font-size: 0.9em; }}
        .paper-link:hover {{ text-decoration: underline; }}
        .semantic-score {{
            font-size: 0.8em; color: #888; margin-left: 10px;
        }}
        .footer {{ text-align: center; padding: 40px; color: #555; font-size: 0.9em; }}

        /* Navigation Tabs */
        .nav-tabs {{
            display: flex; justify-content: center; gap: 12px;
            margin-bottom: 25px; flex-wrap: wrap;
        }}
        .nav-tab {{
            padding: 10px 20px; background: rgba(255,255,255,0.05);
            border-radius: 10px; color: #888; text-decoration: none;
            transition: all 0.2s; border: 1px solid rgba(255,255,255,0.1);
            font-size: 0.9em;
        }}
        .nav-tab:hover {{ background: rgba(255,255,255,0.1); color: #fff; }}
        .nav-tab.active {{ background: rgba(124,58,237,0.3); color: #fff; border-color: rgba(124,58,237,0.5); }}

        /* Keywords Management Section */
        .keywords-section {{
            background: rgba(255,255,255,0.03); border-radius: 16px; padding: 25px;
            margin-bottom: 30px; border: 1px solid rgba(255,255,255,0.08);
        }}
        .keywords-header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 20px; cursor: pointer;
        }}
        .keywords-header h2 {{ font-size: 1.3em; color: #00d4ff; }}
        .keywords-toggle {{ font-size: 1.5em; transition: transform 0.3s; }}
        .keywords-content {{ display: none; }}
        .keywords-content.active {{ display: block; }}
        .keyword-category {{
            margin-bottom: 20px; padding: 15px; background: rgba(0,0,0,0.2);
            border-radius: 12px;
        }}
        .keyword-category-title {{
            font-size: 0.9em; color: #7c3aed; margin-bottom: 10px; font-weight: 600;
        }}
        .keyword-tags {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }}
        .keyword-tag {{
            background: rgba(124,58,237,0.3); padding: 6px 12px; border-radius: 16px;
            font-size: 0.8em; color: #fff; display: flex; align-items: center; gap: 6px;
        }}
        .keyword-tag.secondary {{ background: rgba(0,212,255,0.3); }}
        .keyword-tag.theory {{ background: rgba(34,197,94,0.3); }}
        .keyword-tag.demote {{ background: rgba(239,68,68,0.3); }}
        .keyword-tag.dislike {{ background: rgba(107,114,128,0.3); }}
        .keyword-tag .remove-btn {{
            cursor: pointer; opacity: 0.6; font-size: 1.1em;
        }}
        .keyword-tag .remove-btn:hover {{ opacity: 1; }}
        .keyword-add-form {{
            display: flex; gap: 8px; margin-top: 10px;
        }}
        .keyword-add-form input {{
            flex: 1; padding: 8px 12px; border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1); background: rgba(0,0,0,0.3);
            color: #fff; font-size: 0.85em;
        }}
        .keyword-add-form button {{
            padding: 8px 16px; border-radius: 8px;
            border: none; background: #7c3aed; color: #fff; cursor: pointer;
        }}
        .keyword-add-form button:hover {{ background: #6d28d9; }}
        .save-keywords-btn {{
            margin-top: 20px; padding: 12px 24px; border-radius: 12px;
            border: none; background: linear-gradient(135deg, #7c3aed, #00d4ff);
            color: #fff; font-size: 1em; cursor: pointer; font-weight: 600;
        }}
        .save-keywords-btn:hover {{ opacity: 0.9; }}
        .save-status {{ margin-left: 15px; font-size: 0.9em; }}

        /* Today's Keywords Section */
        .today-keywords-section {{
            background: rgba(34, 197, 94, 0.1); border-radius: 16px; padding: 20px;
            margin-bottom: 25px; border: 1px solid rgba(34, 197, 94, 0.3);
        }}
        .today-keywords-title {{
            font-size: 1.1em; color: #22c55e; margin-bottom: 15px; font-weight: 600;
        }}
        .today-keywords-tags {{
            display: flex; flex-wrap: wrap; gap: 8px;
        }}
        .today-keyword-tag {{
            background: linear-gradient(135deg, rgba(34,197,94,0.3), rgba(0,212,255,0.2));
            padding: 6px 14px; border-radius: 16px; font-size: 0.85em; color: #fff;
            border: 1px solid rgba(34,197,94,0.3);
        }}

        @media (max-width: 768px) {{
            .papers-grid {{ grid-template-columns: 1fr; }}
            .stats {{ flex-direction: column; gap: 20px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>arXiv Daily Digest</h1>
            <div class="date">{date}</div>
            <div class="themes">
                {''.join(f'<span class="theme-tag">{t}</span>' for t in themes)}
            </div>
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{len(papers)}</div>
                    <div class="stat-label">Papers Today</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{stats.get('total_seen', 0)}</div>
                    <div class="stat-label">Papers Seen</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{stats.get('days_with_recommendations', 0)}</div>
                    <div class="stat-label">Days Active</div>
                </div>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <div class="nav-tabs">
            <a href="/" class="nav-tab active">📅 今日推荐</a>
            <a href="/search.html" class="nav-tab">🔍 关键词搜索</a>
            <a href="/journal.html" class="nav-tab">📚 顶刊追踪</a>
            <a href="/scholars.html" class="nav-tab">🎓 学者追踪</a>
            <a href="/liked.html" class="nav-tab">❤️ 我喜欢的</a>
            <a href="/api/refresh?force=1" class="nav-tab" onclick="return confirm('确定要刷新今日推荐吗？')">🔄 刷新</a>
        </div>

        <!-- Today's Matched Keywords -->
        <div class="today-keywords-section">
            <div class="today-keywords-title">📌 今日匹配关键词 (Top {len(today_keywords)})</div>
            <div class="today-keywords-tags">
                {today_keywords_html if today_keywords_html else '<span style="color:#888">暂无匹配关键词</span>'}
            </div>
        </div>

        <!-- Keywords Management Section -->
        <div class="keywords-section">
            <div class="keywords-header" onclick="toggleKeywords()">
                <h2>🏷️ 关键词管理</h2>
                <span class="keywords-toggle" id="keywords-toggle">▼</span>
            </div>
            <div class="keywords-content" id="keywords-content">
                <div class="keyword-category">
                    <div class="keyword-category-title">🔥 核心关键词 (Core Topics)</div>
                    <div class="keyword-tags" id="core-topics-tags">
                        {core_topics_html}
                    </div>
                    <div class="keyword-add-form">
                        <input type="text" id="new-core-topic" placeholder="添加核心关键词...">
                        <button onclick="addKeyword('core')">添加</button>
                    </div>
                </div>

                <div class="keyword-category">
                    <div class="keyword-category-title">📚 次要关键词 (Secondary Topics)</div>
                    <div class="keyword-tags" id="secondary-topics-tags">
                        {secondary_topics_html}
                    </div>
                    <div class="keyword-add-form">
                        <input type="text" id="new-secondary-topic" placeholder="添加次要关键词...">
                        <button onclick="addKeyword('secondary')">添加</button>
                    </div>
                </div>

                <div class="keyword-category">
                    <div class="keyword-category-title">🧠 理论关键词 (Theory Keywords)</div>
                    <div class="keyword-tags" id="theory-keywords-tags">
                        {theory_keywords_html}
                    </div>
                    <div class="keyword-add-form">
                        <input type="text" id="new-theory-keyword" placeholder="添加理论关键词...">
                        <button onclick="addKeyword('theory')">添加</button>
                    </div>
                </div>

                <div class="keyword-category">
                    <div class="keyword-category-title">⬇️ 降权关键词 (Demote Topics)</div>
                    <div class="keyword-tags" id="demote-topics-tags">
                        {demote_topics_html}
                    </div>
                    <div class="keyword-add-form">
                        <input type="text" id="new-demote-topic" placeholder="添加降权关键词...">
                        <button onclick="addKeyword('demote')">添加</button>
                    </div>
                </div>

                <div class="keyword-category">
                    <div class="keyword-category-title">❌ 不喜欢关键词 (Dislike Topics)</div>
                    <div class="keyword-tags" id="dislike-topics-tags">
                        {dislike_topics_html}
                    </div>
                    <div class="keyword-add-form">
                        <input type="text" id="new-dislike-topic" placeholder="添加不喜欢关键词...">
                        <button onclick="addKeyword('dislike')">添加</button>
                    </div>
                </div>

                <button class="save-keywords-btn" onclick="saveKeywords()">
                    💾 保存关键词并重新生成推荐
                </button>
                <span class="save-status" id="save-status"></span>
            </div>
        </div>

        <div class="papers-grid">
{self._generate_paper_cards(papers)}
        </div>
        <div class="footer">
            <p>Generated by arXiv Daily Recommender v2.0 | Semantic Similarity + Multi-Source</p>
            <p>Prioritizing: statistical learning theory, in-context learning, transformer theory, conformal prediction</p>
        </div>
    </div>

    <script>
        // Keywords data
        let keywordsConfig = {keywords_config_json};

        function toggleKeywords() {{
            const content = document.getElementById('keywords-content');
            const toggle = document.getElementById('keywords-toggle');
            content.classList.toggle('active');
            toggle.textContent = content.classList.contains('active') ? '▲' : '▼';
        }}

        function addKeyword(type) {{
            let inputId, configKey;
            switch(type) {{
                case 'core': inputId = 'new-core-topic'; configKey = 'core_topics'; break;
                case 'secondary': inputId = 'new-secondary-topic'; configKey = 'secondary_topics'; break;
                case 'theory': inputId = 'new-theory-keyword'; configKey = 'theory_keywords'; break;
                case 'demote': inputId = 'new-demote-topic'; configKey = 'demote_topics'; break;
                case 'dislike': inputId = 'new-dislike-topic'; configKey = 'dislike_topics'; break;
            }}
            const input = document.getElementById(inputId);
            const value = input.value.trim();
            if (!value) return;

            // Add to config
            if (type === 'theory' || type === 'dislike') {{
                if (!keywordsConfig[configKey].includes(value)) {{
                    keywordsConfig[configKey].push(value);
                }}
            }} else {{
                keywordsConfig[configKey][value] = type === 'demote' ? -1.0 : 3.0;
            }}

            // Refresh display
            refreshKeywordDisplay(type);
            input.value = '';
        }}

        function removeKeyword(type, keyword) {{
            let configKey;
            switch(type) {{
                case 'core': configKey = 'core_topics'; break;
                case 'secondary': configKey = 'secondary_topics'; break;
                case 'theory': configKey = 'theory_keywords'; break;
                case 'demote': configKey = 'demote_topics'; break;
                case 'dislike': configKey = 'dislike_topics'; break;
            }}
            if (type === 'theory' || type === 'dislike') {{
                keywordsConfig[configKey] = keywordsConfig[configKey].filter(k => k !== keyword);
            }} else {{
                delete keywordsConfig[configKey][keyword];
            }}
            refreshKeywordDisplay(type);
        }}

        function refreshKeywordDisplay(type) {{
            let tagsId, configKey, tagClass;
            switch(type) {{
                case 'core': tagsId = 'core-topics-tags'; configKey = 'core_topics'; tagClass = 'core'; break;
                case 'secondary': tagsId = 'secondary-topics-tags'; configKey = 'secondary_topics'; tagClass = 'secondary'; break;
                case 'theory': tagsId = 'theory-keywords-tags'; configKey = 'theory_keywords'; tagClass = 'theory'; break;
                case 'demote': tagsId = 'demote-topics-tags'; configKey = 'demote_topics'; tagClass = 'demote'; break;
                case 'dislike': tagsId = 'dislike-topics-tags'; configKey = 'dislike_topics'; tagClass = 'dislike'; break;
            }}
            const container = document.getElementById(tagsId);
            let html = '';
            const data = keywordsConfig[configKey];
            if (Array.isArray(data)) {{
                data.forEach(k => {{
                    html += `<span class="keyword-tag ${{tagClass}}">${{k}}<span class="remove-btn" onclick="removeKeyword('${{type}}', '${{k}}')">×</span></span>`;
                }});
            }} else {{
                Object.keys(data).forEach(k => {{
                    html += `<span class="keyword-tag ${{tagClass}}">${{k}}<span class="remove-btn" onclick="removeKeyword('${{type}}', '${{k}}')">×</span></span>`;
                }});
            }}
            container.innerHTML = html;
        }}

        function saveKeywords() {{
            const status = document.getElementById('save-status');
            status.textContent = '保存中...';
            status.style.color = '#fbbf24';

            fetch('/api/keywords', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(keywordsConfig)
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.success) {{
                    status.textContent = '✓ 保存成功！正在重新生成推荐...';
                    status.style.color = '#34d399';
                    setTimeout(() => location.reload(), 1500);
                }} else {{
                    status.textContent = '✗ 保存失败: ' + data.error;
                    status.style.color = '#ef4444';
                }}
            }})
            .catch(e => {{
                status.textContent = '✗ 保存失败: ' + e;
                status.style.color = '#ef4444';
            }});
        }}
    </script>
</body>
</html>'''

    def _generate_keyword_tags(self, keywords: Dict[str, float], tag_type: str) -> str:
        """Generate HTML for keyword tags."""
        html = ''
        for keyword, weight in keywords.items():
            html += f'''<span class="keyword-tag {tag_type}">{keyword}<span class="remove-btn" onclick="removeKeyword('{tag_type}', '{keyword}')">×</span></span>'''
        return html

    def _extract_today_keywords(self, papers: List[Dict], core_topics: Dict, secondary_topics: Dict, theory_keywords: List[str]) -> List[str]:
        """Extract keywords that matched in today's papers."""
        matched = set()
        all_keywords = list(core_topics.keys()) + list(secondary_topics.keys()) + theory_keywords

        for paper in papers[:20]:  # Check top 20 papers
            text = (paper.get('title', '') + ' ' + paper.get('abstract', ''))
            for kw in all_keywords:
                if self._count_keyword(text, kw) > 0:
                    matched.add(kw)

        return sorted(matched)

    def _count_keyword(self, text: str, keyword: str) -> int:
        """Count keyword occurrences with flexible matching.

        Handles:
        - Multi-word keywords like "conformal prediction"
        - Hyphenated keywords like "in-context learning"
        - Case insensitive matching
        """
        keyword_lower = keyword.lower()
        text_lower = text.lower()

        # 对于多词关键词（包含空格或连字符），使用子字符串匹配
        if ' ' in keyword_lower or '-' in keyword_lower:
            # 直接子字符串匹配
            return text_lower.count(keyword_lower)
        else:
            # 单词使用词边界匹配
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            return len(re.findall(pattern, text_lower))

    def _generate_relevance_html(self, paper: Dict) -> str:
        """Generate HTML for structured relevance reasons with icons."""
        breakdown = paper.get('relevance_breakdown', [])
        if not breakdown:
            return f'<div class="relevance-item"><span class="relevance-icon">💡</span><span class="relevance-text">{paper.get("relevance_reason", "Matches your research interests")}</span></div>'

        html_items = []
        for reason in breakdown[:4]:  # Max 4 reasons
            icon = reason.get('icon', '📌')
            text = reason.get('text', '')
            score_impact = reason.get('score_impact', 0)
            location = reason.get('location', '')

            location_badge = f'<span class="relevance-location">{location}</span>' if location else ''
            score_badge = f'<span class="relevance-score-impact">+{score_impact:.1f}</span>' if score_impact > 0 else ''

            html_items.append(f'''
                <div class="relevance-item">
                    <span class="relevance-icon">{icon}</span>
                    <span class="relevance-text">{text}</span>
                    {location_badge}
                    {score_badge}
                </div>''')

        return ''.join(html_items)

    def _generate_paper_cards(self, papers: List[Dict]) -> str:
        # arXiv category mapping
        category_names = {
            'stat.ML': 'Machine Learning',
            'stat.TH': 'Statistics Theory',
            'stat.ME': 'Methodology',
            'stat.CO': 'Computation',
            'cs.LG': 'ML (cs)',
            'cs.AI': 'AI',
            'cs.CL': 'NLP',
            'cs.CV': 'Computer Vision',
            'cs.NE': 'Neural Computing',
            'cs.IT': 'Information Theory',
            'cs.LO': 'Logic',
            'math.ST': 'Statistics (math)',
            'math.PR': 'Probability',
            'math.OC': 'Optimization',
            'math.NA': 'Numerical Analysis',
            'econ.EM': 'Econometrics',
            'q-bio.QM': 'Quantitative Bio',
            'physics.data-an': 'Data Analysis',
        }

        cards = ''
        for paper in papers:
            authors = ', '.join(paper['authors'][:3])
            if len(paper['authors']) > 3:
                authors += f" et al. ({len(paper['authors'])} authors)"

            categories = paper.get('categories', [])[:3]
            cat_tags = ''.join(
                f'<span class="meta-tag" title="{c}">{category_names.get(c, c)}</span>'
                for c in categories
            )

            semantic_info = ''
            details = paper.get('score_details', {})
            if details.get('semantic', 0) > 0:
                semantic_info = f'<span class="semantic-score">Semantic: {details["semantic"]:.2f}</span>'

            # Full abstract for expand
            full_abstract = paper.get('abstract', 'No abstract available.')
            short_summary = paper.get('summary', 'No summary available.')

            # Generate structured relevance reasons with icons
            relevance_html = self._generate_relevance_html(paper)

            cards += f'''
            <div class="paper-card" data-paper-id="{paper['id']}">
                <div class="paper-title">
                    <a href="{paper['link']}" target="_blank">{paper['title']}</a>
                </div>
                <div class="paper-authors">{authors}</div>
                <div class="paper-meta">{cat_tags}</div>
                <div class="paper-summary">{short_summary}</div>
                <div id="abstract-{paper['id']}" class="full-abstract">{full_abstract}</div>
                <div class="paper-relevance">
                    <div class="paper-relevance-title">Why Recommended</div>
                    <div class="paper-relevance-items">{relevance_html}</div>
                </div>
                <div class="feedback-btns">
                    <button class="fb-btn like" onclick="sendFeedback('{paper['id']}', 'like')">👍 喜欢</button>
                    <button class="fb-btn dislike" onclick="sendFeedback('{paper['id']}', 'dislike')">👎 不感兴趣</button>
                    <button class="fb-btn abstract" id="btn-{paper['id']}" onclick="toggleAbstract('{paper['id']}')">展开摘要</button>
                    <button class="fb-btn pdf" onclick="downloadPdf('{paper['id']}')">📄 PDF</button>
                </div>
                <div class="paper-footer">
                    <div>
                        <span class="score-badge">Score: {paper.get('score', 0):.1f}</span>
                        {semantic_info}
                    </div>
                    <a href="{paper['link']}" class="paper-link" target="_blank">arXiv -></a>
                </div>
            </div>
'''
        return cards


class MarkdownGenerator:
    """Generate Markdown archive."""

    def generate(self, papers: List[Dict], themes: List[str], date: str) -> str:
        md = f'''# arXiv Daily Digest

**Date:** {date}

**Research Themes:** {', '.join(themes)}

**Papers Recommended:** {len(papers)}

---

'''
        for i, paper in enumerate(papers, 1):
            authors = ', '.join(paper['authors'][:5])
            if len(paper['authors']) > 5:
                authors += " et al."

            md += f'''## {i}. {paper['title']}

**Authors:** {authors}

**arXiv:** [{paper['id']}]({paper['link']})

**Summary:** {paper.get('summary', 'No summary available.')}

**Relevance:** {paper.get('relevance_reason', 'Matches your research interests')}

**Score:** {paper.get('score', 0):.1f}

---

'''
        return md


# ==================== Main Pipeline ====================

def generate_summary(abstract: str, max_sentences: int = 3) -> str:
    """Generate concise summary."""
    if not abstract:
        return "No abstract available."
    sentences = re.split(r'(?<=[.!?])\s+', abstract)
    summary = '. '.join(sentences[:max_sentences])
    if len(summary) > 350:
        summary = summary[:350] + '...'
    return summary


def download_pdfs(papers: List[Dict], output_dir: str, min_score: float = 2.5):
    """Download PDFs for high-scoring papers."""
    pdf_dir = os.path.join(output_dir, 'cache', 'pdfs')
    os.makedirs(pdf_dir, exist_ok=True)

    downloaded = []
    for paper in papers:
        if paper.get('score', 0) >= min_score:
            paper_id = paper['id']
            pdf_path = os.path.join(pdf_dir, f'{paper_id}.pdf')

            if not os.path.exists(pdf_path):
                pdf_url = f'https://arxiv.org/pdf/{paper_id}.pdf'
                try:
                    logger.debug(f"Downloading PDF: {paper_id}...")
                    req = urllib.request.Request(pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as response:
                        with open(pdf_path, 'wb') as f:
                            f.write(response.read())
                    downloaded.append(paper_id)
                except Exception as e:
                    logger.warning(f"Failed to download {paper_id}: {e}")

    if downloaded:
        logger.info(f"Downloaded {len(downloaded)} PDFs to {pdf_dir}")
    return downloaded


# ==================== Daily Recommendation Cache ====================

def load_daily_recommendation(cache_dir: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """Load today's cached recommendation if exists."""
    cache_file = os.path.join(cache_dir, 'daily_recommendation.json')
    today = datetime.now().strftime('%Y-%m-%d')

    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('date') == today:
                    return data.get('papers', []), data.get('themes', [])
        except:
            pass
    return None, None


def save_daily_recommendation(cache_dir: str, papers: List[Dict], themes: List[str]):
    """Save today's recommendation to cache."""
    cache_file = os.path.join(cache_dir, 'daily_recommendation.json')
    today = datetime.now().strftime('%Y-%m-%d')

    # Convert papers to serializable format (remove non-serializable fields)
    serializable_papers = []
    for p in papers:
        paper_copy = {k: v for k, v in p.items() if k != 'score_details' or isinstance(v, dict)}
        if 'score_details' in p:
            paper_copy['score_details'] = p['score_details']
        serializable_papers.append(paper_copy)

    data = {
        'date': today,
        'papers': serializable_papers,
        'themes': themes,
        'generated_at': datetime.now().isoformat()
    }

    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def run_pipeline(force_refresh: bool = False) -> List[Dict]:
    """Run the complete enhanced pipeline.

    Args:
        force_refresh: If True, regenerate recommendations even if today's exist.
    """
    logger.info("=" * 60)
    logger.info("arXiv Daily Paper Recommender v2.2")
    logger.info("=" * 60)

    # Initialize cache
    cache = PaperCache(CONFIG['cache_dir'])

    # Check if today's recommendation already exists
    today = datetime.now().strftime('%Y-%m-%d')
    if not force_refresh:
        cached_papers, cached_themes = load_daily_recommendation(CONFIG['cache_dir'])
        if cached_papers:
            logger.info(f"Today's recommendation already exists ({today})")
            logger.info(f"Papers: {len(cached_papers)}, Themes: {len(cached_themes) if cached_themes else 0}")
            logger.info("Use force_refresh=True to regenerate.")

            # Still update the HTML output for web server
            os.makedirs(CONFIG['output_dir'], exist_ok=True)
            os.makedirs(CONFIG['history_dir'], exist_ok=True)

            html_gen = HTMLGenerator()
            html = html_gen.generate(cached_papers, cached_themes or [], today, cache.get_stats())
            with open(os.path.join(CONFIG['output_dir'], 'index.html'), 'w', encoding='utf-8') as f:
                f.write(html)

            logger.info(f"HTML updated: {CONFIG['output_dir']}/index.html")
            logger.info("Done! Open http://localhost:5555 for interactive view")

            return cached_papers

    cache.cleanup_old_entries(CONFIG['cache_expiry_days'])
    logger.info(f"Cache: {cache.get_stats()}")

    pipeline_start = time.time()

    # Load user feedback and learn from it
    feedback = load_user_feedback(CONFIG['cache_dir'])
    if feedback.get('liked') or feedback.get('disliked'):
        logger.info(f"User feedback: {len(feedback.get('liked', []))} liked, {len(feedback.get('disliked', []))} disliked")

    # Load Zotero papers with auto-detection
    t0 = time.time()
    zotero_path = get_zotero_path()
    zotero_papers = []

    # Check if Zotero is enabled in config
    user_cfg = load_user_config()
    use_zotero = user_cfg.get('zotero', {}).get('enabled', True)

    if use_zotero and os.path.exists(zotero_path):
        try:
            conn = sqlite3.connect(zotero_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT i.itemID, it.typeName,
                       MAX(CASE WHEN id.fieldID = 1 THEN idv.value END) as title,
                       MAX(CASE WHEN id.fieldID = 2 THEN idv.value END) as abstract
                FROM items i
                JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                JOIN itemData id ON i.itemID = id.itemID
                JOIN itemDataValues idv ON id.valueID = idv.valueID
                WHERE i.itemTypeID IN (11, 22, 31)
                GROUP BY i.itemID HAVING title IS NOT NULL
            ''')
            zotero_papers = [{'id': r[0], 'title': r[2], 'abstract': r[3] or ''} for r in cursor.fetchall()]
            conn.close()
            logger.info(f"Loaded {len(zotero_papers)} papers from Zotero ({time.time()-t0:.1f}s)")
        except Exception as e:
            logger.error(f"Zotero load error: {e}")
    elif not use_zotero:
        logger.info("Zotero disabled in config - running in keyword-only mode")
    else:
        logger.info(f"Zotero not found at {zotero_path}")
        logger.info("  Running in keyword-only mode")
        logger.info("  Tip: Set zotero.database_path in user_config.json")

    # Extract themes
    t0 = time.time()
    themes = []
    if zotero_papers:
        all_text = ' '.join([p['title'] + ' ' + p['abstract'] for p in zotero_papers]).lower()
        theme_scores = {}
        for topic in get_priority_topics():
            count = len(re.findall(r'\b' + re.escape(topic.lower()) + r'\b', all_text))
            if count > 0:
                theme_scores[topic] = count
        themes = [t[0] for t in sorted(theme_scores.items(), key=lambda x: -x[1])[:10]]
        logger.debug(f"Research themes: {themes} ({time.time()-t0:.1f}s)")

    # Initialize semantic similarity (with caching)
    t0 = time.time()
    semantic = SemanticSimilarity(CONFIG['embedding_model'], CONFIG['cache_dir'])
    if CONFIG['use_semantic_similarity'] and zotero_papers:
        logger.info("Computing semantic embeddings...")
        semantic.compute_zotero_embedding(zotero_papers, zotero_path)
        logger.info(f"Semantic init done ({time.time()-t0:.1f}s)")
    elif not zotero_papers:
        logger.info("Running in keyword-only mode (no Zotero library found)")
        logger.info("  Recommendations will be based on keyword matching only")
        semantic = None  # Disable semantic similarity

    # Fetch papers from multiple sources
    t0 = time.time()
    fetcher = MultiSourceFetcher(CONFIG['arxiv_categories'], cache)
    papers = fetcher.fetch_all_sources(CONFIG['lookback_days'])
    logger.info(f"Fetched {len(papers)} papers from arXiv ({time.time()-t0:.1f}s)")

    if not papers:
        logger.warning("No new papers found!")
        return []

    # Learn topic weights from feedback
    t0 = time.time()
    topic_weights = learn_from_feedback(feedback, papers)
    logger.debug(f"Learned weights from feedback ({time.time()-t0:.1f}s)")

    # Score papers with learned weights
    # Disable semantic if no Zotero papers
    t0 = time.time()
    use_semantic = CONFIG['use_semantic_similarity'] and semantic is not None
    scorer = EnhancedScorer(semantic, use_semantic, topic_weights)
    for paper in papers:
        score, details = scorer.compute_score(paper)
        paper['score'] = score
        paper['score_details'] = details
        paper['summary'] = generate_summary(paper.get('abstract', ''))

        breakdown = details.get('breakdown', [])
        if breakdown:
            paper['relevance_reason'] = '; '.join([r['text'] for r in breakdown])
            paper['relevance_breakdown'] = breakdown  # Structured data for HTML
        else:
            paper['relevance_reason'] = 'Matches your research interests'
            paper['relevance_breakdown'] = []
    logger.info(f"Scored {len(papers)} papers ({time.time()-t0:.1f}s)")

    # Sort and select top papers
    papers.sort(key=lambda x: -x['score'])
    top_papers = papers[:CONFIG['papers_per_day']]

    logger.debug(f"Top scores: {[round(p['score'], 1) for p in top_papers[:5]]}")

    # Download PDFs for high-scoring papers
    logger.info("Downloading PDFs for top papers...")
    download_pdfs(top_papers, CONFIG['output_dir'], min_score=2.5)

    # Record recommendations
    date_str = datetime.now().strftime('%Y-%m-%d')
    cache.record_recommendation(date_str, [p['id'] for p in top_papers])

    # Generate output
    os.makedirs(CONFIG['output_dir'], exist_ok=True)
    os.makedirs(CONFIG['history_dir'], exist_ok=True)

    html_gen = HTMLGenerator()
    html = html_gen.generate(top_papers, themes, date_str, cache.get_stats())

    md_gen = MarkdownGenerator()
    md = md_gen.generate(top_papers, themes, date_str)

    with open(os.path.join(CONFIG['output_dir'], 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    logger.info(f"HTML saved to: {CONFIG['output_dir']}/index.html")

    with open(os.path.join(CONFIG['output_dir'], 'daily_arxiv_digest.md'), 'w', encoding='utf-8') as f:
        f.write(md)
    logger.info(f"Markdown saved to: {CONFIG['output_dir']}/daily_arxiv_digest.md")

    # Save history
    history_path = os.path.join(CONFIG['history_dir'], f'digest_{date_str}.md')
    with open(history_path, 'w', encoding='utf-8') as f:
        f.write(md)
    logger.info(f"History saved to: {history_path}")

    # Save daily recommendation cache (so we don't regenerate on same day)
    save_daily_recommendation(CONFIG['cache_dir'], top_papers, themes)
    logger.info(f"Daily recommendation cached for {date_str}")

    logger.info("=" * 60)
    logger.info(f"Pipeline complete! Total time: {time.time()-pipeline_start:.1f}s")
    logger.info("=" * 60)

    # Print summary
    logger.info("=" * 60)
    logger.info("Today's Top Recommendations:")
    logger.info("=" * 60)
    for i, p in enumerate(top_papers[:5], 1):
        logger.info(f"{i}. {p['title'][:70]}...")
        logger.info(f"   Score: {p['score']:.1f} | {p['link']}")

    logger.info("=" * 60)
    logger.info("Done! Open http://localhost:5555 for interactive view")
    logger.info("=" * 60)

    return top_papers


# ==================== Custom Keywords Search ====================

def search_by_keywords(keywords: List[str], max_results: int = 20, days_back: int = 365) -> List[Dict]:
    """Search arXiv papers by custom keywords.

    Args:
        keywords: List of keywords to search for
        max_results: Maximum number of papers to return
        days_back: How many days back to search (default 365 days = 1 year)

    Returns:
        List of matching papers sorted by relevance score
    """
    logger.info("=" * 60)
    logger.info(f"Searching arXiv for: {', '.join(keywords)}")
    logger.info("=" * 60)

    # Build arXiv query from keywords
    # Use AND/OR logic for better matching
    query_parts = []
    for kw in keywords[:5]:  # Limit to 5 keywords for API
        # Search in title and abstract
        query_parts.append(f'(ti:"{kw}"+OR+abs:"{kw}")')

    search_query = '+OR+'.join(query_parts)

    # Fetch papers from arXiv
    papers = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    params = {
        'search_query': search_query,
        'start': 0,
        'max_results': min(max_results * 3, 100),  # Get more to filter
        'sortBy': 'relevance',
        'sortOrder': 'descending'
    }

    url = f"http://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"
    logger.debug(f"Query URL: {url}")

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as response:
            xml_data = response.read().decode('utf-8')
            logger.debug(f"Received {len(xml_data)} bytes from arXiv")

            # Parse XML
            root = ET.fromstring(xml_data)
            ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

            entries = root.findall('atom:entry', ns)
            logger.debug(f"Found {len(entries)} entries in XML")

            for entry in entries:
                paper = {}

                title_elem = entry.find('atom:title', ns)
                paper['title'] = title_elem.text.strip() if title_elem is not None else ''

                authors = []
                for author in entry.findall('atom:author', ns):
                    name_elem = author.find('atom:name', ns)
                    if name_elem is not None:
                        authors.append(name_elem.text)
                paper['authors'] = authors

                abstract_elem = entry.find('atom:summary', ns)
                paper['abstract'] = abstract_elem.text.strip() if abstract_elem is not None else ''

                published_elem = entry.find('atom:published', ns)
                paper['published'] = published_elem.text if published_elem is not None else ''

                link_elem = entry.find('atom:id', ns)
                paper['id'] = link_elem.text.split('/abs/')[-1] if link_elem is not None else ''
                paper['link'] = link_elem.text if link_elem is not None else ''
                paper['source'] = 'arXiv'

                categories = []
                for cat in entry.findall('atom:category', ns):
                    term = cat.get('term')
                    if term:
                        categories.append(term)
                paper['categories'] = categories

                comment_elem = entry.find('arxiv:comment', ns)
                paper['comment'] = comment_elem.text if comment_elem is not None else ''

                # Filter by date
                try:
                    pub_date = datetime.strptime(paper['published'][:10], '%Y-%m-%d')
                    if pub_date >= start_date:
                        papers.append(paper)
                except:
                    papers.append(paper)

    except Exception as e:
        logger.error(f"Error fetching from arXiv: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return []

    logger.info(f"Found {len(papers)} papers from arXiv")

    # Score papers based on keyword matches
    def compute_keyword_score(paper: Dict) -> Tuple[float, Dict]:
        """Compute score based on keyword matching."""
        text = (paper['title'] + ' ' + paper.get('abstract', ''))
        text_lower = text.lower()
        score = 0.0
        matched_keywords = []

        for kw in keywords:
            kw_lower = kw.lower()
            # Use word boundary matching (consistent with main scorer)
            pattern = r'\b' + re.escape(kw_lower) + r'\b'
            if re.search(pattern, text_lower):
                # Higher score for title match
                if re.search(pattern, paper['title'].lower()):
                    score += 3.0
                    matched_keywords.append(f"Title: {kw}")
                else:
                    score += 1.5
                    matched_keywords.append(f"Abstract: {kw}")
            # Check for word-level match (for multi-word keywords)
            else:
                words = kw_lower.split()
                if all(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in words):
                    score += 1.0
                    matched_keywords.append(f"Related: {kw}")

        # Bonus for known authors
        authors_text = ' '.join(paper.get('authors', [])).lower()
        for author in KNOWN_AUTHORS:
            if author.lower() in authors_text:
                score += 1.0
                matched_keywords.append(f"Author: {author}")
                break

        # Bonus for top institutions
        all_text = (paper.get('abstract', '') + ' ' + (paper.get('comment') or '')).lower()
        for inst in TOP_INSTITUTIONS:
            if inst.lower() in all_text:
                score += 0.5
                matched_keywords.append(f"Institution: {inst}")
                break

        return score, {'matched_keywords': matched_keywords}

    # Score all papers
    for paper in papers:
        score, details = compute_keyword_score(paper)
        paper['score'] = score
        paper['matched_keywords'] = details['matched_keywords']
        paper['summary'] = generate_summary(paper.get('abstract', ''))
        paper['relevance_reason'] = '; '.join(details['matched_keywords'][:3]) if details['matched_keywords'] else 'Keyword match'

    # Sort by score and filter
    papers.sort(key=lambda x: -x['score'])
    results = papers[:max_results]

    logger.info(f"Top {len(results)} papers after scoring")
    return results


def generate_search_html(papers: List[Dict], keywords: List[str]) -> str:
    """Generate HTML page for keyword search results."""
    date = datetime.now().strftime('%Y-%m-%d')

    papers_html = ''
    for paper in papers:
        authors = ', '.join(paper['authors'][:3])
        if len(paper['authors']) > 3:
            authors += f" et al. ({len(paper['authors'])} authors)"

        categories = paper.get('categories', [])[:3]
        cat_tags = ''.join(f'<span class="meta-tag">{c}</span>' for c in categories)

        papers_html += f'''
        <div class="paper-card">
            <div class="paper-title">
                <a href="{paper['link']}" target="_blank">{paper['title']}</a>
            </div>
            <div class="paper-authors">{authors}</div>
            <div class="paper-meta">{cat_tags}</div>
            <div class="paper-summary">{paper.get('summary', '')}</div>
            <div class="paper-relevance">
                <div class="paper-relevance-title">Matched Keywords</div>
                <div class="paper-relevance-text">{paper.get('relevance_reason', 'Keyword match')}</div>
            </div>
            <div class="paper-footer">
                <span class="score-badge">Score: {paper.get('score', 0):.1f}</span>
                <a href="{paper['link']}" class="paper-link" target="_blank">arXiv →</a>
            </div>
        </div>
'''

    keywords_html = ' '.join([f'<span class="keyword-tag">{kw}</span>' for kw in keywords])

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>arXiv Keyword Search - {', '.join(keywords)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh; color: #e0e0e0; padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            text-align: center; padding: 30px 20px;
            background: rgba(255,255,255,0.03); border-radius: 20px;
            margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.08);
        }}
        .header h1 {{
            font-size: 2.2em;
            background: linear-gradient(135deg, #00d4ff 0%, #7c3aed 50%, #f472b6 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 15px;
        }}
        .search-box {{
            display: flex; gap: 10px; justify-content: center; margin: 20px 0;
            flex-wrap: wrap;
        }}
        .search-input {{
            width: 400px; max-width: 100%;
            padding: 14px 20px; font-size: 1.1em;
            background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
            border-radius: 12px; color: #fff; outline: none;
        }}
        .search-input::placeholder {{ color: #888; }}
        .search-input:focus {{ border-color: #00d4ff; }}
        .search-btn {{
            padding: 14px 30px; font-size: 1.1em;
            background: linear-gradient(135deg, #7c3aed, #00d4ff);
            border: none; border-radius: 12px; color: #fff; cursor: pointer;
            transition: all 0.2s;
        }}
        .search-btn:hover {{ transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0,212,255,0.3); }}
        .keywords-section {{
            background: rgba(255,255,255,0.03); border-radius: 16px;
            padding: 20px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.08);
            text-align: center;
        }}
        .keyword-tag {{
            display: inline-block;
            background: linear-gradient(135deg, rgba(124,58,237,0.4), rgba(0,212,255,0.4));
            padding: 8px 18px; border-radius: 20px; color: #fff; margin: 5px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .stats {{ font-size: 0.95em; color: #888; margin-top: 15px; }}
        .papers-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 20px;
        }}
        .paper-card {{
            background: rgba(255,255,255,0.03); border-radius: 16px; padding: 22px;
            border: 1px solid rgba(255,255,255,0.06);
            transition: all 0.3s ease;
        }}
        .paper-card:hover {{ transform: translateY(-3px); border-color: rgba(0,212,255,0.3); }}
        .paper-title {{ font-size: 1.05em; font-weight: 600; color: #fff; margin-bottom: 10px; line-height: 1.4; }}
        .paper-title a {{ color: #fff; text-decoration: none; }}
        .paper-title a:hover {{ color: #00d4ff; }}
        .paper-authors {{ font-size: 0.85em; color: #888; margin-bottom: 12px; }}
        .paper-meta {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }}
        .meta-tag {{
            background: rgba(0,212,255,0.15); padding: 4px 10px; border-radius: 12px;
            font-size: 0.75em; color: #00d4ff;
        }}
        .paper-summary {{ font-size: 0.9em; color: #aaa; line-height: 1.6; margin-bottom: 12px; }}
        .paper-relevance {{
            background: rgba(124,58,237,0.12); padding: 10px 12px; border-radius: 8px;
            margin-bottom: 12px; border-left: 3px solid #7c3aed;
        }}
        .paper-relevance-title {{ font-size: 0.75em; color: #7c3aed; font-weight: 600; margin-bottom: 6px; }}
        .paper-relevance-text {{ font-size: 0.85em; color: #ccc; }}
        .paper-relevance-items {{ display: flex; flex-direction: column; gap: 5px; }}
        .relevance-item {{
            display: flex; align-items: center; gap: 6px; font-size: 0.85em;
        }}
        .relevance-icon {{ font-size: 1em; min-width: 20px; }}
        .relevance-text {{ color: #ddd; flex: 1; }}
        .relevance-location {{
            font-size: 0.75em; color: #888; background: rgba(255,255,255,0.1);
            padding: 1px 5px; border-radius: 3px;
        }}
        .relevance-score-impact {{
            font-size: 0.7em; color: #22c55e; font-weight: 600;
            background: rgba(34,197,94,0.15); padding: 1px 5px; border-radius: 3px;
        }}
        .paper-footer {{
            display: flex; justify-content: space-between; align-items: center;
            padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.08);
        }}
        .score-badge {{
            background: linear-gradient(135deg, #7c3aed, #00d4ff);
            padding: 4px 12px; border-radius: 12px; font-size: 0.8em; font-weight: bold;
        }}
        .paper-link {{ color: #00d4ff; text-decoration: none; font-size: 0.9em; }}
        .paper-link:hover {{ text-decoration: underline; }}
        .nav-tabs {{
            display: flex; justify-content: center; gap: 15px;
            margin-bottom: 25px; flex-wrap: wrap;
        }}
        .nav-tab {{
            padding: 10px 20px; background: rgba(255,255,255,0.05);
            border-radius: 10px; color: #888; text-decoration: none;
            transition: all 0.2s; border: 1px solid rgba(255,255,255,0.1);
        }}
        .nav-tab:hover {{ background: rgba(255,255,255,0.1); color: #fff; }}
        .nav-tab.active {{ background: rgba(124,58,237,0.3); color: #fff; border-color: rgba(124,58,237,0.5); }}
        .footer {{ text-align: center; padding: 30px; color: #555; font-size: 0.85em; margin-top: 30px; }}
        .no-results {{ text-align: center; padding: 60px; color: #888; }}
        @media (max-width: 768px) {{
            .papers-grid {{ grid-template-columns: 1fr; }}
            .search-input {{ width: 100%; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 关键词论文搜索</h1>
            <div class="search-box">
                <input type="text" class="search-input" id="keywordInput"
                       placeholder="输入关键词，用逗号或空格分隔..."
                       value="{', '.join(keywords)}">
                <button class="search-btn" onclick="doSearch()">搜索</button>
            </div>
        </div>

        <div class="nav-tabs">
            <a href="/" class="nav-tab">📅 今日推荐</a>
            <a href="/search" class="nav-tab active">🔍 关键词搜索</a>
            <a href="/journal" class="nav-tab">📚 顶刊追踪</a>
            <a href="/liked" class="nav-tab">❤️ 我喜欢的</a>
        </div>

        <div class="keywords-section">
            <div class="keyword-tag" style="background:rgba(124,58,237,0.5)">搜索关键词</div>
            <div>{keywords_html}</div>
            <div class="stats">找到 {len(papers)} 篇相关论文 · 搜索时间: {date}</div>
        </div>

        {'<div class="papers-grid">' + papers_html + '</div>' if papers else '<div class="no-results">暂无搜索结果，请尝试其他关键词</div>'}

        <div class="footer">
            <p>arXiv Keyword Search | 自由关键词推荐</p>
        </div>
    </div>

    <script>
    function doSearch() {{
        const input = document.getElementById('keywordInput').value.trim();
        if (input) {{
            const keywords = input.split(/[,，\\s]+/).filter(k => k.length > 0);
            if (keywords.length > 0) {{
                window.location.href = '/search/' + encodeURIComponent(keywords.join(','));
            }}
        }}
    }}
    document.getElementById('keywordInput').addEventListener('keypress', function(e) {{
        if (e.key === 'Enter') doSearch();
    }});
    </script>
</body>
</html>'''


if __name__ == '__main__':
    run_pipeline()


# ==================== API Server for Keywords ====================

def run_server(port: int = 5555):
    """Run HTTP server with API endpoints for keyword management."""
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    import urllib.parse

    class APIHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=CONFIG['output_dir'], **kwargs)

        def do_GET(self):
            """Handle GET requests."""
            if self.path == '/' or self.path == '/index.html':
                # Serve main page
                self.path = '/index.html'
                super().do_GET()
            elif self.path.startswith('/api/keywords'):
                # Return current keywords config
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                config = load_keywords_config()
                self.wfile.write(json.dumps(config).encode())
            else:
                super().do_GET()

        def do_POST(self):
            """Handle POST requests."""
            if self.path == '/api/keywords':
                # Save keywords config
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)

                try:
                    new_config = json.loads(post_data.decode('utf-8'))

                    # Validate and save
                    if save_keywords_config(new_config):
                        # Regenerate recommendations with new keywords
                        logger.info("Keywords updated, regenerating recommendations...")
                        run_pipeline(force_refresh=True)

                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'success': True}).encode())
                    else:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'success': False, 'error': 'Failed to save'}).encode())
                except Exception as e:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            # Suppress default logging
            pass

    server = HTTPServer(('0.0.0.0', port), APIHandler)
    logger.info("=" * 60)
    logger.info(f"Server running at http://localhost:{port}")
    logger.info("=" * 60)
    logger.info("Features:")
    logger.info("  - View today's recommendations")
    logger.info("  - Add/remove keywords in the UI")
    logger.info("  - Save keywords and auto-regenerate recommendations")
    logger.info("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped.")
