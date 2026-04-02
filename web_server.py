"""
arXiv Recommender Web Server v2.0
Features: History browsing, Daily keywords, Better UI
"""

import os
# Fix OpenMP library conflict on Windows
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import json
import re
import threading
import urllib.parse
import subprocess
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

# 统一日志系统
from logger_config import get_logger
logger = get_logger(__name__)

# ============ Git自动备份函数 ============
def git_backup_user_data(message=None):
    """自动备份用户数据到Git"""
    if message is None:
        message = f"[Auto Backup] User data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    try:
        # 添加用户数据文件
        user_data_files = [
            'cache/user_feedback.json',
            'cache/favorite_papers.json',
            'my_scholars.json',
            'user_profile.json',
        ]

        for file_path in user_data_files:
            full_path = os.path.join(BASE_DIR, file_path)
            if os.path.exists(full_path):
                subprocess.run(['git', 'add', file_path], cwd=BASE_DIR, capture_output=True)

        # 检查是否有更改需要提交
        result = subprocess.run(
            ['git', 'diff', '--cached', '--quiet'],
            cwd=BASE_DIR,
            capture_output=True
        )

        if result.returncode != 0:
            # 有更改，执行提交
            subprocess.run(['git', 'commit', '-m', message], cwd=BASE_DIR, capture_output=True)
            logger.info(f"Git backup completed: {message}")
    except Exception as e:
        logger.debug(f"Git backup skipped: {e}")

app = Flask(__name__)
CORS(app)

BASE_DIR = 'D:/arxiv_recommender'
HISTORY_DIR = os.path.join(BASE_DIR, 'history')
FEEDBACK_FILE = os.path.join(BASE_DIR, 'cache', 'user_feedback.json')
CACHE_FILE = os.path.join(BASE_DIR, 'cache', 'paper_cache.json')
FAVORITES_FILE = os.path.join(BASE_DIR, 'cache', 'favorite_papers.json')
INDEX_HTML = os.path.join(BASE_DIR, 'index.html')
KEYWORDS_CONFIG_FILE = os.path.join(BASE_DIR, 'keywords_config.json')

# ============ 公共 CSS 样式 ============
COMMON_CSS = '''
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    min-height: 100vh; color: #e0e0e0; padding: 20px;
}
.container { max-width: 1200px; margin: 0 auto; }
.header { text-align: center; padding: 30px 20px; background: rgba(255,255,255,0.03); border-radius: 20px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.08); }
.header h1 { font-size: 2.5em; background: linear-gradient(135deg, #00d4ff, #7c3aed, #f472b6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }
.nav-tabs { display: flex; justify-content: center; gap: 8px; margin: 20px 0; flex-wrap: wrap; }
.nav-tab { padding: 10px 18px; background: rgba(255,255,255,0.05); border-radius: 10px; color: #fff; text-decoration: none; transition: all 0.2s; border: 1px solid rgba(255,255,255,0.1); }
.nav-tab:hover { background: rgba(124,58,237,0.3); transform: translateY(-2px); }
.nav-tab.active { background: linear-gradient(135deg, rgba(124,58,237,0.4), rgba(0,212,255,0.3)); border-color: rgba(0,212,255,0.5); }
.nav-tab.search { border-left: 3px solid #3b82f6; }
.nav-tab.scholars { border-left: 3px solid #10b981; }
.nav-tab.journal { border-left: 3px solid #f59e0b; }
.nav-tab.liked { border-left: 3px solid #ef4444; }
.nav-tab.stats { border-left: 3px solid #8b5cf6; }
.nav-tab.settings { border-left: 3px solid #6b7280; }
.paper-card { background: rgba(255,255,255,0.03); border-radius: 16px; padding: 25px; border: 1px solid rgba(255,255,255,0.06); margin-bottom: 20px; transition: all 0.3s; }
.paper-card:hover { transform: translateY(-3px); border-color: rgba(0,212,255,0.3); }
.paper-title { font-size: 1.1em; font-weight: 600; color: #fff; margin-bottom: 12px; line-height: 1.5; }
.paper-title a { color: #fff; text-decoration: none; }
.paper-title a:hover { color: #00d4ff; }
.paper-authors { font-size: 0.85em; color: #888; margin-bottom: 15px; }
.paper-summary { font-size: 0.9em; color: #aaa; line-height: 1.7; margin-bottom: 15px; }
.paper-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 15px; }
.meta-tag { background: rgba(0,212,255,0.15); padding: 4px 10px; border-radius: 12px; font-size: 0.75em; color: #00d4ff; }
.score-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: bold; }
.score-high { background: linear-gradient(135deg, rgba(16,185,129,0.3), rgba(0,212,255,0.2)); color: #10b981; }
.score-mid { background: rgba(245,158,11,0.2); color: #f59e0b; }
.btn { padding: 10px 20px; border-radius: 10px; color: #fff; text-decoration: none; transition: all 0.2s; border: none; cursor: pointer; }
.btn-primary { background: linear-gradient(135deg, #7c3aed, #00d4ff); }
.btn-secondary { background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); }
'''

def get_nav_tabs(active='', liked_count=0, is_today=False):
    """生成导航栏 HTML"""
    tabs = [
        ('/', '📅 今日推荐', ''),
        ('/search', '🔍 搜索', 'search'),
        ('/scholars', '🎓 学者追踪', 'scholars'),
        ('/journal', '📚 顶刊追踪', 'journal'),
        ('/liked', f'❤️ 喜欢 ({liked_count})', 'liked'),
        ('/stats', '📊 统计', 'stats'),
        ('/settings', '⚙️ 设置', 'settings'),
    ]
    html = '<div class="nav-tabs">'
    for href, text, cls in tabs:
        active_cls = 'active' if active == cls or (active == 'index' and cls == '') else ''
        html += f'<a href="{href}" class="nav-tab {cls} {active_cls}">{text}</a>'
    if is_today:
        html += '<a href="/api/refresh?force=1" class="nav-tab refresh" onclick="return confirm(\'确定刷新?\')">🔄</a>'
    html += '</div>'
    return html


# ============ 安全文件加载辅助函数 ============

def safe_load_json(filepath: str, default=None):
    """安全加载 JSON 文件，避免 TOCTOU 问题.

    直接尝试打开文件而不是先检查存在性，使用异常处理来处理文件不存在的情况。
    """
    if default is None:
        default = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Error loading {filepath}: {e}")
        return default


# ============ 历史文件解析缓存 ============

_history_cache = {}  # {date: (papers, keywords, timestamp)}
_HISTORY_CACHE_TTL = 300  # 5 minutes

def parse_markdown_digest_cached(filepath: str, use_cache: bool = True):
    """带缓存的 markdown 解析，避免重复解析同一文件."""
    import time

    # 从文件路径提取日期
    date_match = re.search(r'digest_(\d{4}-\d{2}-\d{2})', filepath)
    cache_key = date_match.group(1) if date_match else filepath

    current_time = time.time()

    # 检查缓存
    if use_cache and cache_key in _history_cache:
        cached_papers, cached_keywords, cached_time = _history_cache[cache_key]
        # 检查文件是否被修改
        try:
            file_mtime = os.path.getmtime(filepath)
            if cached_time >= file_mtime and (current_time - cached_time) < _HISTORY_CACHE_TTL:
                logger.debug(f"Using cached digest for {cache_key}")
                return cached_papers, cached_keywords
        except OSError:
            pass

    # 解析文件
    papers, keywords = parse_markdown_digest(filepath)

    # 更新缓存
    if use_cache and papers:
        _history_cache[cache_key] = (papers, keywords, current_time)

    return papers, keywords


def load_feedback():
    return safe_load_json(FEEDBACK_FILE, {'liked': [], 'disliked': []})


def save_feedback(feedback):
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)
    with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(feedback, f, ensure_ascii=False, indent=2)
    # 自动备份到Git
    git_backup_user_data(f"[Feedback] {len(feedback.get('liked', []))} liked, {len(feedback.get('disliked', []))} disliked")


def load_favorites():
    """Load favorite papers with full info."""
    return safe_load_json(FAVORITES_FILE, {})


def save_favorites(favorites):
    """Save favorite papers to file."""
    os.makedirs(os.path.dirname(FAVORITES_FILE), exist_ok=True)
    with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)
    # 自动备份到Git
    git_backup_user_data(f"[Favorites] {len(favorites)} papers saved")


# ============ 我的学者管理 ============
MY_SCHOLARS_FILE = os.path.join(BASE_DIR, 'my_scholars.json')

def load_my_scholars():
    """Load user's custom scholars list."""
    return safe_load_json(MY_SCHOLARS_FILE, {'scholars': []})

def save_my_scholars(scholars_data):
    """Save user's custom scholars list."""
    with open(MY_SCHOLARS_FILE, 'w', encoding='utf-8') as f:
        json.dump(scholars_data, f, ensure_ascii=False, indent=2)
    # 自动备份到Git
    git_backup_user_data(f"[Scholars] {len(scholars_data.get('scholars', []))} scholars tracked")

def add_my_scholar(name, affiliation='', focus='', arxiv_query='', google_scholar='', website=''):
    """Add a scholar to user's list."""
    data = load_my_scholars()
    # 检查是否已存在
    for s in data['scholars']:
        if s['name'].lower() == name.lower():
            return False, "学者已存在"

    scholar = {
        'name': name,
        'affiliation': affiliation,
        'focus': focus,
        'google_scholar': google_scholar,
        'website': website,
        'arxiv': arxiv_query or f'https://arxiv.org/search/?searchtype=author&query={urllib.parse.quote(name)}',
        'added_at': datetime.now().isoformat()
    }
    data['scholars'].append(scholar)
    save_my_scholars(data)
    return True, scholar

def remove_my_scholar(name):
    """Remove a scholar from user's list."""
    data = load_my_scholars()
    original_len = len(data['scholars'])
    data['scholars'] = [s for s in data['scholars'] if s['name'].lower() != name.lower()]
    if len(data['scholars']) == original_len:
        return False, "学者不存在"
    save_my_scholars(data)
    return True, "已删除"


def fetch_scholar_papers_from_arxiv(scholar_name: str, max_results: int = 5) -> list:
    """从 arXiv 获取指定学者的最新论文."""
    import urllib.request
    import ssl
    import xml.etree.ElementTree as ET

    # 创建 SSL 上下文
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # 构建查询
    query = urllib.parse.quote(f'au:"{scholar_name}"')
    url = f'http://export.arxiv.org/api/query?search_query={query}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending'

    papers = []
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'arXiv-Recommender/1.0'
        })
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            xml_content = response.read().decode('utf-8')

        # 解析 XML
        root = ET.fromstring(xml_content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        for entry in root.findall('atom:entry', ns):
            title_elem = entry.find('atom:title', ns)
            summary_elem = entry.find('atom:summary', ns)
            link_elem = entry.find('atom:id', ns)
            published_elem = entry.find('atom:published', ns)

            authors = []
            for author in entry.findall('atom:author', ns):
                name_elem = author.find('atom:name', ns)
                if name_elem is not None:
                    authors.append(name_elem.text)

            # 提取 arXiv ID
            link = link_elem.text if link_elem is not None else ''
            arxiv_id = link.split('/')[-1] if link else ''

            paper = {
                'title': title_elem.text.strip() if title_elem is not None else 'No Title',
                'authors': authors,
                'abstract': summary_elem.text.strip()[:300] + '...' if summary_elem is not None and len(summary_elem.text) > 300 else (summary_elem.text.strip() if summary_elem else ''),
                'link': link,
                'arxiv_id': arxiv_id,
                'published': published_elem.text[:10] if published_elem is not None else '',
                'scholar': scholar_name
            }
            papers.append(paper)

    except Exception as e:
        logger.error(f"Error fetching papers for {scholar_name}: {e}")

    return papers


def get_all_my_scholar_papers(max_per_scholar: int = 3) -> dict:
    """获取所有关注学者的最新论文."""
    data = load_my_scholars()
    results = {}

    for scholar in data.get('scholars', []):
        name = scholar['name']
        papers = fetch_scholar_papers_from_arxiv(name, max_per_scholar)
        if papers:
            results[name] = {
                'scholar_info': scholar,
                'papers': papers
            }

    return results


def parse_google_scholar_url(url: str) -> dict:
    """从 Google Scholar URL 解析学者信息.

    支持格式:
    - https://scholar.google.com/citations?user=XXXXX
    - https://scholar.google.com/citations?hl=en&user=XXXXX
    """
    import urllib.request
    import ssl
    import re
    from html import unescape

    # 提取 user ID
    match = re.search(r'user=([a-zA-Z0-9_-]+)', url)
    if not match:
        return {'success': False, 'error': '无法从链接中提取学者ID'}

    user_id = match.group(1)
    scholar_url = f'https://scholar.google.com/citations?user={user_id}&hl=en'

    # 创建 SSL 上下文
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(scholar_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        })
        with urllib.request.urlopen(req, timeout=20, context=ssl_context) as response:
            html = response.read().decode('utf-8')

        # 解析姓名
        name_match = re.search(r'<div id="gsc_prf_in[^>]*>([^<]+)</div>', html)
        name = unescape(name_match.group(1).strip()) if name_match else ''

        # 解析机构/学校 (第一个 gsc_prf_il)
        aff_match = re.search(r'<div class="gsc_prf_il[^>]*>([^<]+)</div>', html)
        affiliation = unescape(aff_match.group(1).strip()) if aff_match else ''

        # 解析研究领域标签 (第二个 gsc_prf_il 通常包含研究领域)
        focus_matches = re.findall(r'<div class="gsc_prf_il[^>]*>(.*?)</div>', html, re.DOTALL)
        focus = ''
        if len(focus_matches) > 1:
            # 提取领域标签
            focus_html = focus_matches[1]
            focus_tags = re.findall(r'<a[^>]*class="gsc_prf_inta"[^>]*>([^<]+)</a>', focus_html)
            if focus_tags:
                focus = ', '.join([unescape(t.strip()) for t in focus_tags[:5]])

        # 尝试解析邮箱（如果有）
        email_match = re.search(r'at\s+([a-zA-Z0-9.-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', html)
        email = email_match.group(1) if email_match else ''

        # 解析个人网站链接
        website_match = re.search(r'<a[^>]*class="gsc_prf_ila"[^>]*href="([^"]+)"[^>]*>', html)
        website = website_match.group(1) if website_match else ''

        # 统计信息
        citations_match = re.search(r'<td class="gsc_rsb_std">(\d+)</td>', html)
        citations = int(citations_match.group(1)) if citations_match else 0

        hindex_match = re.search(r'<td class="gsc_rsb_std">(\d+)</td>\s*<td class="gsc_rsb_std">\d+</td>', html)
        h_index = int(hindex_match.group(1)) if hindex_match else 0

        if not name:
            return {'success': False, 'error': '无法解析学者姓名'}

        return {
            'success': True,
            'name': name,
            'affiliation': affiliation,
            'focus': focus,
            'email': email,
            'website': website,
            'google_scholar': scholar_url,
            'arxiv': f'https://arxiv.org/search/?searchtype=author&query={urllib.parse.quote(name)}',
            'citations': citations,
            'h_index': h_index
        }

    except urllib.error.URLError as e:
        return {'success': False, 'error': f'网络错误: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': f'解析失败: {str(e)}'}


def load_keywords_config():
    """Load keywords configuration - 使用统一配置管理器."""
    try:
        from config_manager import get_config
        cm = get_config()
        return {
            'core_topics': cm.core_keywords,
            'secondary_topics': cm.get_keywords_by_category('secondary'),
            'theory_keywords': cm._config.get('theory_keywords', []),
            'demote_topics': cm.demote_keywords,
            'dislike_topics': list(cm.dislike_keywords.keys())
        }
    except Exception as e:
        logger.error(f"Error loading keywords config: {e}")
        return {
            'core_topics': {},
            'secondary_topics': {},
            'theory_keywords': [],
            'demote_topics': {},
            'dislike_topics': []
        }


def save_keywords_config(config):
    """Save keywords configuration - 使用统一配置管理器.

    使用批量更新模式，只在最后保存一次到磁盘，避免每次修改都触发文件写入。
    """
    try:
        from config_manager import get_config
        cm = get_config()

        # 先清空所有现有关键词，再重新设置（确保删除操作生效）
        # 获取所有现有关键词
        existing_keywords = list(cm._keywords.keys())

        # 批量更新核心主题 (save=False 避免每次都写磁盘)
        if 'core_topics' in config:
            for topic, weight in config['core_topics'].items():
                cm.set_keyword(topic, weight, 'core', save=False)

        # 批量更新次要主题
        if 'secondary_topics' in config:
            for topic, weight in config['secondary_topics'].items():
                cm.set_keyword(topic, weight, 'secondary', save=False)

        # 批量更新降权主题
        if 'demote_topics' in config:
            for topic, weight in config['demote_topics'].items():
                cm.set_keyword(topic, weight, 'demote', save=False)

        # 批量更新不感兴趣主题
        if 'dislike_topics' in config:
            dislike_list = config['dislike_topics']
            if isinstance(dislike_list, dict):
                for topic, weight in dislike_list.items():
                    cm.set_keyword(topic, weight, 'dislike', save=False)
            elif isinstance(dislike_list, list):
                for topic in dislike_list:
                    cm.set_keyword(topic, -1.0, 'dislike', save=False)

        # 删除不在新配置中的关键词
        new_topics = set()
        if 'core_topics' in config:
            new_topics.update(config['core_topics'].keys())
        if 'secondary_topics' in config:
            new_topics.update(config['secondary_topics'].keys())
        if 'demote_topics' in config:
            new_topics.update(config['demote_topics'].keys())
        if 'dislike_topics' in config:
            dislike = config['dislike_topics']
            if isinstance(dislike, dict):
                new_topics.update(dislike.keys())
            elif isinstance(dislike, list):
                new_topics.update(dislike)

        for kw in existing_keywords:
            if kw not in new_topics:
                cm.remove_keyword(kw, save=False)
                logger.info(f"Removed keyword: {kw}")

        # 最后只保存一次
        cm.save()
        logger.info("Keywords config saved via unified config manager")
    except Exception as e:
        logger.error(f"Error saving keywords config: {e}")


def _count_keyword(text: str, keyword: str) -> int:
    """Count keyword occurrences with word boundary (consistent with recommender)."""
    import re
    pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
    return len(re.findall(pattern, text.lower()))


def extract_today_keywords(papers, keywords_config):
    """Extract keywords that matched in today's papers."""
    matched = []
    core_topics = keywords_config.get('core_topics', {})
    secondary_topics = keywords_config.get('secondary_topics', {})
    theory_keywords = keywords_config.get('theory_keywords', [])

    all_keywords = list(core_topics.keys()) + list(secondary_topics.keys()) + theory_keywords

    for paper in papers[:20]:  # Check top 20 papers
        text = (paper.get('title', '') + ' ' + paper.get('summary', '') + ' ' + paper.get('abstract', ''))
        for kw in all_keywords:
            if _count_keyword(text, kw) > 0 and kw not in matched:
                matched.append(kw)

    return matched[:10]  # Return top 10


def add_to_favorites(paper_id, paper_info):
    """Add a paper to favorites with full info."""
    favorites = load_favorites()
    favorites[paper_id] = {
        'id': paper_id,
        'title': paper_info.get('title', ''),
        'authors': paper_info.get('authors', ''),
        'abstract': paper_info.get('abstract', ''),
        'summary': paper_info.get('summary', ''),
        'link': paper_info.get('link', f'https://arxiv.org/abs/{paper_id}'),
        'score': paper_info.get('score', 0),
        'relevance': paper_info.get('relevance', ''),
        'categories': paper_info.get('categories', []),
        'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'date_published': paper_info.get('date', '')
    }
    save_favorites(favorites)
    return favorites[paper_id]


def remove_from_favorites(paper_id):
    """Remove a paper from favorites."""
    favorites = load_favorites()
    if paper_id in favorites:
        del favorites[paper_id]
        save_favorites(favorites)


def get_available_dates():
    """Get list of available dates from history."""
    dates = []
    if os.path.exists(HISTORY_DIR):
        for f in os.listdir(HISTORY_DIR):
            if f.startswith('digest_') and f.endswith('.md'):
                date = f.replace('digest_', '').replace('.md', '')
                dates.append(date)
    return sorted(dates, reverse=True)


def parse_markdown_digest(filepath):
    """Parse markdown digest to extract papers."""
    papers = []
    keywords = []

    print(f"[DEBUG] parse_markdown_digest called with: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract themes/keywords from the header
    themes_match = re.search(r'\*\*Research Themes:\*\* (.+)', content)
    if themes_match:
        keywords = [k.strip() for k in themes_match.group(1).split(',')]

    # Try to load daily metadata for better keywords
    date_match = re.search(r'digest_(\d{4}-\d{2}-\d{2})', filepath)
    date_str = date_match.group(1) if date_match else None
    print(f"[DEBUG] date_str extracted: {date_str}")

    if date_str:
        metadata_path = os.path.join(BASE_DIR, 'cache', 'daily_metadata.json')
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    if metadata.get('date') == date_str and metadata.get('keywords'):
                        keywords = [k['word'] for k in metadata['keywords']]
            except:
                pass

    # Try to load structured breakdown from daily_recommendation.json
    breakdown_map = {}
    if date_str:
        rec_path = os.path.join(BASE_DIR, 'cache', 'daily_recommendation.json')
        logger.info(f"Looking for breakdown at: {rec_path}")
        logger.info(f"File exists: {os.path.exists(rec_path)}")
        if os.path.exists(rec_path):
            try:
                with open(rec_path, 'r', encoding='utf-8') as f:
                    rec_data = json.load(f)
                    logger.info(f"JSON date: {rec_data.get('date')}, looking for: {date_str}")
                    if rec_data.get('date') == date_str:
                        for p in rec_data.get('papers', []):
                            pid = p.get('id')
                            if pid:
                                breakdown_map[pid] = {
                                    'breakdown': p.get('score_details', {}).get('breakdown', []),
                                    'relevance_reason': p.get('relevance_reason', '')
                                }
                        logger.info(f"Loaded breakdown_map with {len(breakdown_map)} entries")
            except Exception as e:
                logger.error(f"Error loading breakdown: {e}")

    # Split into paper sections
    sections = re.split(r'## \d+\.', content)[1:]  # Skip header

    for section in sections:
        lines = section.strip().split('\n')
        if not lines:
            continue

        paper = {}
        paper['title'] = lines[0].strip()

        for line in lines[1:]:
            if line.startswith('**Authors:**'):
                paper['authors'] = line.replace('**Authors:**', '').strip()
            elif line.startswith('**arXiv:**') or line.startswith('**arXiv Link:**'):
                match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', line)
                if match:
                    paper['id'] = match.group(1)
                    paper['link'] = match.group(2)
            elif line.startswith('**Summary:**'):
                paper['summary'] = line.replace('**Summary:**', '').strip()[:200] + '...'
            elif line.startswith('**Relevance:**'):
                paper['relevance'] = line.replace('**Relevance:**', '').strip()
            elif line.startswith('**Citations:**'):
                try:
                    paper['citations'] = int(line.replace('**Citations:**', '').strip())
                except:
                    paper['citations'] = 0
            elif line.startswith('**Score:**'):
                try:
                    paper['score'] = float(line.replace('**Score:**', '').strip())
                except:
                    paper['score'] = 0

        if paper.get('id'):
            # Merge structured breakdown if available
            pid = paper['id']
            if pid in breakdown_map:
                paper['relevance_breakdown'] = breakdown_map[pid]['breakdown']
                if breakdown_map[pid]['relevance_reason']:
                    paper['relevance'] = breakdown_map[pid]['relevance_reason']
                logger.info(f"Merged breakdown for {pid}: {paper['relevance_breakdown']}")
            else:
                logger.info(f"No breakdown found for {pid}, breakdown_map has {len(breakdown_map)} entries")
            papers.append(paper)

    return papers, keywords


def generate_relevance_html(paper):
    """Generate HTML for structured relevance reasons with icons."""
    breakdown = paper.get('relevance_breakdown', [])
    logger.info(f"[HTML GEN] Paper {paper.get('id')} has relevance_breakdown: {breakdown}")
    if not breakdown:
        text = paper.get('relevance', '匹配您的研究兴趣')
        logger.info(f"[HTML GEN] No breakdown, using fallback text: {text}")
        return f'<div class="paper-relevance-text">{text}</div>'

    html_items = []
    for reason in breakdown[:4]:  # Max 4 reasons
        # Handle both old string format and new dict format
        if isinstance(reason, str):
            # Old format: "[Core] generalization" or "Top: MIT"
            if reason.startswith('[Core]'):
                icon = '🎯'
                text = f"命中核心主题: {reason.replace('[Core]', '').strip()}"
            elif reason.startswith('[Secondary]'):
                icon = '📌'
                text = f"相关主题: {reason.replace('[Secondary]', '').strip()}"
            else:
                icon = '📌'
                text = reason
            location_badge = ''
            score_badge = ''
        else:
            # New format: dict with icon, text, location, score_impact
            icon = reason.get('icon', '📌')
            text = reason.get('text', '')
            location = reason.get('location', '')
            score_impact = reason.get('score_impact', 0)

            location_badge = f'<span class="relevance-location">{location}</span>' if location else ''
            score_badge = f'<span class="relevance-score-impact">+{score_impact:.1f}</span>' if score_impact > 0 else ''

        html_items.append(f'''
            <div class="relevance-item">
                <span class="relevance-icon">{icon}</span>
                <span class="relevance-text">{text}</span>
                {location_badge}
                {score_badge}
            </div>''')

    return f'<div class="paper-relevance-items">{"".join(html_items)}</div>'


# ============ 后台生成任务管理 ============
_generation_status = {
    'running': False,
    'started_at': None,
    'error': None
}

def _run_pipeline_background():
    """在后台线程中运行 pipeline"""
    global _generation_status
    try:
        import sys
        sys.path.insert(0, BASE_DIR)
        from arxiv_recommender_v5 import run_pipeline
        run_pipeline(force_refresh=False)
        _generation_status['running'] = False
        logger.info("Background pipeline completed successfully")
    except Exception as e:
        _generation_status['running'] = False
        _generation_status['error'] = str(e)
        logger.error(f"Background pipeline error: {e}")


def _start_background_generation():
    """启动后台生成任务"""
    global _generation_status

    if _generation_status['running']:
        return  # 已经在运行

    _generation_status = {
        'running': True,
        'started_at': datetime.now().isoformat(),
        'error': None
    }

    thread = threading.Thread(target=_run_pipeline_background, daemon=True)
    thread.start()
    logger.info("Started background pipeline generation")


def _render_generating_page():
    """渲染"正在生成"的等待页面"""
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>正在生成推荐...</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh; color: #e0e0e0; display: flex; align-items: center;
            justify-content: center; text-align: center;
        }
        .container { padding: 40px; }
        h1 {
            font-size: 2em;
            background: linear-gradient(135deg, #00d4ff, #7c3aed);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 20px;
        }
        .spinner {
            width: 60px; height: 60px; margin: 30px auto;
            border: 4px solid rgba(255,255,255,0.1);
            border-top-color: #00d4ff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .status { color: #888; font-size: 0.95em; margin-top: 20px; }
        .progress-dots::after {
            content: '';
            animation: dots 1.5s steps(4, end) infinite;
        }
        @keyframes dots {
            0%, 20% { content: ''; }
            40% { content: '.'; }
            60% { content: '..'; }
            80%, 100% { content: '...'; }
        }
        .steps { margin-top: 30px; text-align: left; display: inline-block; }
        .step { color: #666; font-size: 0.85em; margin: 8px 0; }
        .step.active { color: #00d4ff; }
        .step.done { color: #10b981; }
    </style>
    <script>
        let elapsed = 0;
        const steps = ['获取 arXiv 论文', '计算推荐分数', '生成摘要', '保存结果'];
        let currentStep = 0;

        function updateStatus() {
            elapsed += 5;
            document.getElementById('elapsed').textContent = elapsed + ' 秒';

            // 更新步骤显示 (每 15 秒切换一个步骤)
            const newStep = Math.min(Math.floor(elapsed / 15), steps.length - 1);
            if (newStep !== currentStep) {
                currentStep = newStep;
                const stepEls = document.querySelectorAll('.step');
                stepEls.forEach((el, i) => {
                    el.className = 'step ' + (i < currentStep ? 'done' : (i === currentStep ? 'active' : ''));
                });
            }

            // 检查是否完成
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    if (data.has_recommendation && data.date === new Date().toISOString().slice(0, 10)) {
                        window.location.reload();
                    }
                })
                .catch(() => {});
        }

        setInterval(updateStatus, 5000);
        // 初始更新
        setTimeout(updateStatus, 1000);
    </script>
</head>
<body>
    <div class="container">
        <h1>🚀 正在生成今日推荐</h1>
        <div class="spinner"></div>
        <p class="status">预计需要 30-60 秒<span class="progress-dots"></span></p>
        <p class="status">已等待: <span id="elapsed">0</span> 秒</p>
        <div class="steps">
            <div class="step active">📥 获取 arXiv 论文</div>
            <div class="step">⚡ 计算推荐分数</div>
            <div class="step">📝 生成摘要</div>
            <div class="step">💾 保存结果</div>
        </div>
    </div>
</body>
</html>'''


def generate_page(date=None, auto_generate=True):
    """Generate HTML page for a specific date.

    Args:
        date: The date to display. If None, uses the latest available date.
        auto_generate: If True and today has no data, start background generation.
    """
    dates = get_available_dates()
    today = datetime.now().strftime('%Y-%m-%d')

    if not date:
        date = dates[0] if dates else today

    filepath = os.path.join(HISTORY_DIR, f'digest_{date}.md')

    # If today's file doesn't exist and auto_generate is enabled, start background generation
    if not os.path.exists(filepath) and auto_generate and date == today:
        logger.info(f"No recommendation found for today ({today}), starting background generation...")
        _start_background_generation()
        return _render_generating_page()

    if not os.path.exists(filepath):
        return f'''<html><body style="font-family:sans-serif;padding:40px;background:#1a1a2e;color:#fff;">
            <h1>📅 {date} 暂无推荐数据</h1>
            <p><a href="/" style="color:#00d4ff">返回今日推荐</a></p>
            </body></html>'''

    papers, keywords = parse_markdown_digest_cached(filepath)
    logger.debug(f"generate_page called, parsing: {filepath}")
    feedback = load_feedback()

    # Generate date navigation
    prev_date = next_date = None
    if date in dates:
        idx = dates.index(date)
        if idx + 1 < len(dates):
            prev_date = dates[idx + 1]
        if idx > 0:
            next_date = dates[idx - 1]

    return render_html(date, papers, keywords, dates, prev_date, next_date, feedback)


def render_html(date, papers, keywords, dates, prev_date, next_date, feedback):
    """Render the full HTML page."""

    # Load keywords config and extract today's matched keywords
    keywords_config = load_keywords_config()
    today_matched_keywords = extract_today_keywords(papers, keywords_config)

    # Keywords cloud - show today's matched keywords (top 10)
    if today_matched_keywords:
        keywords_html = ''.join([
            f'<span class="keyword-tag today-match" style="font-size:{1 + 0.05*i}em">{kw}</span>'
            for i, kw in enumerate(today_matched_keywords)
        ])
    else:
        # Fallback to themes from digest
        keywords_html = ''.join([
            f'<span class="keyword-tag" style="font-size:{1 + 0.1*i}em">{kw}</span>'
            for i, kw in enumerate(keywords[:10])
        ])

    # Paper cards
    papers_html = ''
    for paper in papers:
        is_liked = paper.get('id') in feedback.get('liked', [])
        is_disliked = paper.get('id') in feedback.get('disliked', [])

        card_style = ''
        if is_liked:
            card_style = 'border-left: 4px solid #10b981;'
        elif is_disliked:
            card_style = 'opacity: 0.5; border-left: 4px solid #ef4444;'

        # Generate structured relevance HTML
        relevance_html = generate_relevance_html(paper)
        logger.info(f"[DEBUG] Paper {paper.get('id')} relevance_html preview: {relevance_html[:100]}")

        papers_html += f'''
        <div class="paper-card" data-paper-id="{paper.get('id', '')}" data-title="{paper.get('title', '').replace('"', '&quot;')}" data-summary="{paper.get('summary', '').replace('"', '&quot;')[:300]}" data-authors="{paper.get('authors', '').replace('"', '&quot;')}" data-score="{paper.get('score', 0)}" data-relevance="{paper.get('relevance', '').replace('"', '&quot;')}" style="{card_style}">
            <div class="paper-title">
                <a href="{paper.get('link', '#')}" target="_blank">{paper.get('title', 'Unknown')}</a>
            </div>
            <div class="paper-authors">{paper.get('authors', '')}</div>
            <div class="paper-summary">{paper.get('summary', '')}</div>
            <div class="paper-relevance">
                <div class="paper-relevance-title">推荐理由</div>
                {relevance_html}
            </div>
            <div class="feedback-btns">
                <button class="fb-btn like {'active' if is_liked else ''}" onclick="sendFeedback(this, 'like')">👍 喜欢</button>
                <button class="fb-btn dislike {'active' if is_disliked else ''}" onclick="sendFeedback(this, 'dislike')">👎 不感兴趣</button>
                <button class="fb-btn follow" onclick="followAuthor(this)">⭐ 关注作者</button>
                <button class="fb-btn pdf" onclick="downloadPdf('{paper.get('id', '')}')">📄 PDF</button>
                <a href="{paper.get('link', '#')}" class="fb-btn arxiv" target="_blank">arXiv →</a>
            </div>
            <div class="paper-footer">
                <span class="score-badge">Score: {paper.get('score', 0):.1f}</span>
                {f'<span class="citation-badge">📊 Citations: {paper.get("citations", 0)}</span>' if paper.get('citations', 0) > 0 else ''}
            </div>
        </div>
'''

    # Date navigation
    nav_html = '<div class="date-nav">'
    if prev_date:
        nav_html += f'<a href="/date/{prev_date}" class="nav-btn">← {prev_date}</a>'
    nav_html += f'<span class="current-date">{date}</span>'
    if next_date:
        nav_html += f'<a href="/date/{next_date}" class="nav-btn">{next_date} →</a>'
    nav_html += '</div>'

    # Date picker - Beautiful timeline style
    date_cards = []
    for i, d in enumerate(dates[:14]):  # Show last 14 days
        is_selected = d == date
        # Parse date for display
        try:
            dt = datetime.strptime(d, '%Y-%m-%d')
            day_display = dt.strftime('%d')
            month_display = dt.strftime('%b')
            weekday = dt.strftime('%a')
        except:
            day_display = d[-2:]
            month_display = d[5:7]
            weekday = ''

        if is_selected:
            date_cards.append(f'''
            <div class="date-card active" onclick="location.href='/date/{d}'">
                <div class="date-month">{month_display}</div>
                <div class="date-day">{day_display}</div>
                <div class="date-weekday">{weekday}</div>
                <div class="date-pulse"></div>
            </div>''')
        else:
            date_cards.append(f'''
            <div class="date-card" onclick="location.href='/date/{d}'">
                <div class="date-month">{month_display}</div>
                <div class="date-day">{day_display}</div>
                <div class="date-weekday">{weekday}</div>
            </div>''')

    date_timeline_html = f'''
    <div class="date-timeline-container">
        <button class="timeline-nav-btn left" onclick="scrollTimeline(-200)" aria-label="Previous">‹</button>
        <div class="date-timeline" id="dateTimeline">
            {''.join(date_cards)}
        </div>
        <button class="timeline-nav-btn right" onclick="scrollTimeline(200)" aria-label="Next">›</button>
    </div>'''

    # Stats
    liked_count = len(feedback.get('liked', []))
    disliked_count = len(feedback.get('disliked', []))

    # Check if viewing today's recommendations
    today = datetime.now().strftime('%Y-%m-%d')
    is_today = (date == today)

    # Navigation tabs
    nav_tabs_html = f'''
    <div class="nav-tabs">
        <a href="/" class="nav-tab active">📅 今日推荐</a>
        <a href="/search" class="nav-tab search">🔍 搜索</a>
        <a href="/scholars" class="nav-tab scholars">🎓 学者追踪</a>
        <a href="/journal" class="nav-tab journal">📚 顶刊追踪</a>
        <a href="/liked" class="nav-tab liked">❤️ 喜欢 ({liked_count})</a>
        <a href="/stats" class="nav-tab stats">📊 统计</a>
        <a href="/settings" class="nav-tab settings">⚙️ 设置</a>
        {'<a href="/api/refresh?force=1" class="nav-tab refresh" onclick="return confirm(\'确定要刷新今日推荐吗？\')">🔄</a>' if is_today else ''}
    </div>
'''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
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
        .container {{ max-width: 1200px; margin: 0 auto; }}

        /* Header */
        .header {{
            text-align: center; padding: 30px 20px;
            background: rgba(255,255,255,0.03); border-radius: 20px;
            margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.08);
        }}
        .header h1 {{
            font-size: 2.5em;
            background: linear-gradient(135deg, #00d4ff 0%, #7c3aed 50%, #f472b6 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        .subtitle {{ color: #888; font-size: 1.1em; margin-bottom: 20px; }}

        /* Date Navigation */
        .date-nav {{
            display: flex; justify-content: center; align-items: center;
            gap: 20px; margin-bottom: 25px; flex-wrap: wrap;
        }}
        .nav-btn {{
            padding: 10px 20px; background: rgba(124,58,237,0.3);
            border-radius: 10px; color: #fff; text-decoration: none;
            transition: all 0.2s; border: 1px solid rgba(124,58,237,0.5);
        }}
        .nav-btn:hover {{ background: rgba(124,58,237,0.5); transform: translateY(-2px); }}
        .current-date {{
            font-size: 1.5em; font-weight: bold; color: #00d4ff;
            padding: 10px 25px; background: rgba(0,212,255,0.1);
            border-radius: 12px; border: 1px solid rgba(0,212,255,0.3);
        }}
        .date-select {{
            padding: 8px 15px; background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2); border-radius: 8px;
            color: #fff; font-size: 1em; cursor: pointer;
        }}

        /* Beautiful Date Timeline */
        .date-timeline-container {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin: 25px auto;
            max-width: 100%;
            position: relative;
        }}
        .date-timeline {{
            display: flex;
            gap: 12px;
            overflow-x: auto;
            padding: 10px 5px;
            scroll-behavior: smooth;
            scrollbar-width: none;
            -ms-overflow-style: none;
        }}
        .date-timeline::-webkit-scrollbar {{ display: none; }}
        .timeline-nav-btn {{
            width: 36px;
            height: 36px;
            border-radius: 50%;
            border: 1px solid rgba(255,255,255,0.2);
            background: rgba(255,255,255,0.05);
            color: #888;
            font-size: 1.4em;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }}
        .timeline-nav-btn:hover {{
            background: rgba(124,58,237,0.3);
            border-color: rgba(124,58,237,0.5);
            color: #fff;
        }}
        .date-card {{
            min-width: 70px;
            padding: 12px 8px;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 14px;
            text-align: center;
            cursor: pointer;
            transition: all 0.25s ease;
            position: relative;
            overflow: hidden;
        }}
        .date-card:hover {{
            background: rgba(124,58,237,0.15);
            border-color: rgba(124,58,237,0.4);
            transform: translateY(-3px);
        }}
        .date-card.active {{
            background: linear-gradient(135deg, rgba(124,58,237,0.4), rgba(0,212,255,0.3));
            border-color: rgba(0,212,255,0.5);
            box-shadow: 0 4px 20px rgba(0,212,255,0.2);
        }}
        .date-card .date-month {{
            font-size: 0.7em;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .date-card .date-day {{
            font-size: 1.4em;
            font-weight: 700;
            color: #fff;
            margin: 4px 0;
        }}
        .date-card .date-weekday {{
            font-size: 0.65em;
            color: #666;
        }}
        .date-card.active .date-month {{
            color: #00d4ff;
        }}
        .date-card.active .date-day {{
            color: #fff;
            text-shadow: 0 0 20px rgba(0,212,255,0.5);
        }}
        .date-card.active .date-weekday {{
            color: #a78bfa;
        }}
        .date-pulse {{
            position: absolute;
            top: 50%;
            left: 50%;
            width: 100%;
            height: 100%;
            background: radial-gradient(circle, rgba(0,212,255,0.1) 0%, transparent 70%);
            transform: translate(-50%, -50%);
            animation: pulse 2s ease-in-out infinite;
            pointer-events: none;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 0.5; transform: translate(-50%, -50%) scale(1); }}
            50% {{ opacity: 1; transform: translate(-50%, -50%) scale(1.1); }}
        }}

        /* Navigation Tabs */
        .nav-tabs {{
            display: flex; justify-content: center; gap: 15px;
            margin-bottom: 25px; flex-wrap: wrap;
        }}
        .nav-tab {{
            padding: 12px 24px; background: rgba(255,255,255,0.05);
            border-radius: 12px; color: #888; text-decoration: none;
            transition: all 0.2s; border: 1px solid rgba(255,255,255,0.1);
        }}
        .nav-tab:hover {{ background: rgba(255,255,255,0.1); color: #fff; }}
        .nav-tab.active {{ background: rgba(124,58,237,0.3); color: #fff; border-color: rgba(124,58,237,0.5); }}
        .nav-tab.liked {{ border-left: 3px solid #10b981; }}
        .nav-tab.disliked {{ border-left: 3px solid #ef4444; }}
        .nav-tab.search {{ border-left: 3px solid #00d4ff; background: rgba(0,212,255,0.1); }}
        .nav-tab.search:hover {{ background: rgba(0,212,255,0.2); }}
        .nav-tab.scholars {{ border-left: 3px solid #10b981; background: rgba(16,185,129,0.1); }}
        .nav-tab.scholars:hover {{ background: rgba(16,185,129,0.2); }}
        .nav-tab.journal {{ border-left: 3px solid #f59e0b; background: rgba(245,158,11,0.1); }}
        .nav-tab.journal:hover {{ background: rgba(245,158,11,0.2); }}
        .nav-tab.stats {{ border-left: 3px solid #3b82f6; background: rgba(59,130,246,0.1); }}
        .nav-tab.stats:hover {{ background: rgba(59,130,246,0.2); }}
        .nav-tab.settings {{ border-left: 3px solid #a855f7; background: rgba(168,85,247,0.1); }}
        .nav-tab.settings:hover {{ background: rgba(168,85,247,0.2); }}
        .nav-tab.refresh {{ border-left: 3px solid #6b7280; background: rgba(107,114,128,0.1); }}
        .nav-tab.refresh:hover {{ background: rgba(107,114,128,0.2); }}

        /* Keywords */
        .keywords-section {{
            background: rgba(255,255,255,0.03); border-radius: 16px;
            padding: 20px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.08);
        }}
        .keywords-title {{
            font-size: 0.9em; color: #7c3aed; margin-bottom: 15px;
            text-transform: uppercase; letter-spacing: 1px;
        }}
        .keywords-cloud {{ display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }}
        .keyword-tag {{
            background: linear-gradient(135deg, rgba(124,58,237,0.3), rgba(0,212,255,0.3));
            padding: 8px 18px; border-radius: 20px; color: #fff;
            border: 1px solid rgba(255,255,255,0.1); transition: all 0.2s;
        }}
        .keyword-tag:hover {{ transform: scale(1.05); }}
        .keyword-tag.today-match {{
            background: linear-gradient(135deg, rgba(16,185,129,0.4), rgba(0,212,255,0.4));
            border-color: rgba(16,185,129,0.5);
        }}
        .keywords-manage-section {{
            margin-top: 15px; text-align: center;
        }}
        .manage-keywords-btn {{
            display: inline-block; padding: 8px 16px; font-size: 0.85em;
            background: rgba(107,114,128,0.2); color: #a78bfa;
            border-radius: 10px; text-decoration: none;
            border: 1px solid rgba(107,114,128,0.3);
            transition: all 0.2s;
        }}
        .manage-keywords-btn:hover {{
            background: rgba(107,114,128,0.3); transform: translateY(-2px);
        }}

        /* Stats */
        .stats-bar {{
            display: flex; justify-content: center; gap: 30px;
            padding: 15px; margin-bottom: 20px;
            background: rgba(255,255,255,0.02); border-radius: 12px;
        }}
        .stat-item {{ text-align: center; }}
        .stat-num {{ font-size: 1.8em; font-weight: bold; color: #00d4ff; }}
        .stat-label {{ font-size: 0.8em; color: #888; }}

        /* Papers Grid */
        .papers-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 20px;
        }}
        .paper-card {{
            background: rgba(255,255,255,0.03); border-radius: 16px; padding: 22px;
            border: 1px solid rgba(255,255,255,0.06);
            transition: all 0.3s ease; position: relative;
        }}
        .paper-card:hover {{ transform: translateY(-3px); border-color: rgba(0,212,255,0.3); }}
        .paper-title {{ font-size: 1.05em; font-weight: 600; color: #fff; margin-bottom: 10px; line-height: 1.4; }}
        .paper-title a {{ color: #fff; text-decoration: none; }}
        .paper-title a:hover {{ color: #00d4ff; }}
        .paper-authors {{ font-size: 0.85em; color: #888; margin-bottom: 12px; }}
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
            padding: 2px 0;
        }}
        .relevance-icon {{ font-size: 1em; min-width: 20px; text-align: center; }}
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
        .citation-badge {{
            background: rgba(59,130,246,0.3);
            padding: 4px 12px; border-radius: 12px; font-size: 0.8em;
            border: 1px solid #3b82f6;
        }}

        /* Feedback Buttons */
        .feedback-btns {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }}
        .fb-btn {{
            padding: 6px 14px; border-radius: 6px; border: none; cursor: pointer;
            font-size: 0.85em; transition: all 0.2s; text-decoration: none;
            display: inline-block;
        }}
        .fb-btn.like {{ background: rgba(16,185,129,0.2); color: #10b981; border: 1px solid #10b981; }}
        .fb-btn.like:hover, .fb-btn.like.active {{ background: rgba(16,185,129,0.5); }}
        .fb-btn.dislike {{ background: rgba(239,68,68,0.2); color: #ef4444; border: 1px solid #ef4444; }}
        .fb-btn.dislike:hover, .fb-btn.dislike.active {{ background: rgba(239,68,68,0.5); }}
        .fb-btn.pdf {{ background: rgba(59,130,246,0.2); color: #3b82f6; border: 1px solid #3b82f6; }}
        .fb-btn.pdf:hover {{ background: rgba(59,130,246,0.5); }}
        .fb-btn.arxiv {{ background: rgba(168,85,247,0.2); color: #a855f7; border: 1px solid #a855f7; }}
        .fb-btn.arxiv:hover {{ background: rgba(168,85,247,0.5); }}
        .fb-btn.follow {{ background: rgba(251,191,36,0.2); color: #fbbf24; border: 1px solid #fbbf24; }}
        .fb-btn.follow:hover {{ background: rgba(251,191,36,0.5); }}

        /* Footer */
        .footer {{
            text-align: center; padding: 30px; color: #555; font-size: 0.85em;
            margin-top: 30px;
        }}

        /* Toast */
        .toast {{
            position: fixed; bottom: 20px; right: 20px;
            background: #333; color: #fff; padding: 12px 24px;
            border-radius: 8px; z-index: 9999; animation: fadeIn 0.3s;
        }}
        @keyframes fadeIn {{ from {{opacity:0;transform:translateY(10px)}} to {{opacity:1;transform:translateY(0)}} }}

        @media (max-width: 768px) {{
            .papers-grid {{ grid-template-columns: 1fr; }}
            .stats-bar {{ flex-direction: column; gap: 10px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📚 arXiv Daily Digest</h1>
            <div class="subtitle">智能论文推荐 · 基于您的研究兴趣</div>
        </div>

        {nav_tabs_html}

        {nav_html}

        {date_timeline_html}

        <div class="keywords-section">
            <div class="keywords-title">📌 今日匹配关键词 (Top {len(today_matched_keywords)})</div>
            <div class="keywords-cloud">{keywords_html if keywords_html else '<span style="color:#888">暂无匹配关键词</span>'}</div>
            <div class="keywords-manage-section">
                <a href="/settings#keywords" class="manage-keywords-btn">⚙️ 管理关键词</a>
            </div>
        </div>

        <div class="stats-bar">
            <div class="stat-item">
                <div class="stat-num">{len(papers)}</div>
                <div class="stat-label">今日推荐</div>
            </div>
            <div class="stat-item">
                <div class="stat-num" style="color:#10b981">{liked_count}</div>
                <div class="stat-label">已喜欢</div>
            </div>
            <div class="stat-item">
                <div class="stat-num" style="color:#ef4444">{disliked_count}</div>
                <div class="stat-label">不感兴趣</div>
            </div>
        </div>

        <div class="papers-grid">
            {papers_html}
        </div>

        <div class="footer">
            <p>arXiv Daily Recommender v3.0 | 用户反馈学习 + 多源整合</p>
            <p>优先推荐: 统计四大期刊、三大会、JMLR</p>
        </div>
    </div>

    <script>
    function sendFeedback(btn, action) {{
        console.log('sendFeedback called:', action);
        const card = btn.closest('.paper-card');
        const paperId = card ? card.dataset.paperId : '';
        const title = card ? card.dataset.title : '';
        const summary = card ? card.dataset.summary : '';
        const authors = card ? card.dataset.authors : '';
        const score = card ? parseFloat(card.dataset.score) || 0 : 0;
        const relevance = card ? card.dataset.relevance : '';
        console.log('paperId:', paperId);

        fetch('/api/feedback', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                paper_id: paperId,
                action: action,
                title: title,
                abstract: summary,
                authors: authors,
                score: score,
                relevance: relevance
            }})
        }})
        .then(r => r.json())
        .then(data => {{
            console.log('response:', data);
            if (data.success) {{
                if (card) {{
                    // Reset styles
                    card.style.opacity = '1';
                    card.style.borderLeft = 'none';

                    // Remove active from all buttons in this card
                    card.querySelectorAll('.fb-btn.like, .fb-btn.dislike').forEach(b => b.classList.remove('active'));

                    if (action === 'like') {{
                        card.style.borderLeft = '4px solid #10b981';
                        card.querySelector('.fb-btn.like').classList.add('active');
                    }} else if (action === 'dislike') {{
                        card.style.opacity = '0.5';
                        card.style.borderLeft = '4px solid #ef4444';
                        card.querySelector('.fb-btn.dislike').classList.add('active');
                    }}
                }}
                showToast(action === 'like' ? '✓ 已标记为喜欢' : '✓ 已标记为不感兴趣');
                // Update stats
                setTimeout(() => location.reload(), 500);
            }} else {{
                showToast('✗ 操作失败');
            }}
        }})
        .catch(err => {{
            console.error('Error:', err);
            showToast('✗ 网络错误: ' + err.message);
        }});
    }}

    function showToast(message) {{
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2000);
    }}

    function followAuthor(btn) {{
        const card = btn.closest('.paper-card');
        if (!card) return;

        const authorsStr = card.dataset.authors || '';
        const title = card.dataset.title || '';

        // 解析作者 - 取第一作者
        const authors = authorsStr.split(',').map(a => a.trim()).filter(a => a);
        if (authors.length === 0) {{
            showToast('✗ 无法获取作者信息');
            return;
        }}

        // 如果有多个作者，显示选择对话框
        if (authors.length > 1) {{
            const authorList = authors.map((a, i) => `${{i + 1}}. ${{a}}`).join('\\n');
            const choice = prompt('选择要关注的作者:\\n' + authorList + '\\n\\n输入序号 (1-' + authors.length + ')，或输入 0 关注全部:');
            if (!choice) return;

            const num = parseInt(choice);
            if (num === 0) {{
                // 关注全部作者
                addScholars(authors, title);
            }} else if (num >= 1 && num <= authors.length) {{
                // 关注选中的作者
                addScholars([authors[num - 1]], title);
            }} else {{
                showToast('✗ 无效的选择');
            }}
        }} else {{
            // 只有一个作者，直接添加
            addScholars(authors, title);
        }}
    }}

    async function addScholars(authors, paperTitle) {{
        let added = 0;
        for (const name of authors) {{
            try {{
                const res = await fetch('/api/scholars/add', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        name: name,
                        focus: paperTitle.substring(0, 50) + '...'
                    }})
                }});
                const data = await res.json();
                if (data.success) added++;
            }} catch (e) {{
                console.error('Error adding scholar:', e);
            }}
        }}
        if (added > 0) {{
            showToast(`✓ 已添加 ${{added}} 位学者到关注列表`);
        }} else {{
            showToast('✗ 学者可能已在关注列表中');
        }}
    }}

    function downloadPdf(paperId) {{
        window.open('/api/pdf/' + paperId, '_blank');
    }}

    function scrollTimeline(amount) {{
        const timeline = document.getElementById('dateTimeline');
        if (timeline) {{
            timeline.scrollBy({{ left: amount, behavior: 'smooth' }});
        }}
    }}

    // Auto-scroll to active date card
    document.addEventListener('DOMContentLoaded', function() {{
        const activeCard = document.querySelector('.date-card.active');
        if (activeCard) {{
            activeCard.scrollIntoView({{ behavior: 'smooth', inline: 'center', block: 'nearest' }});
        }}
    }});
    </script>
</body>
</html>'''


@app.route('/')
def index():
    return generate_page()


# Scholar Database - Important researchers in ML Theory & Statistics
SCHOLARS = {
    'icl_transformer': {
        'name': 'ICL 与 Transformer 理论核心',
        'icon': '🤖',
        'color': '#00d4ff',
        'description': '解析 ICL 样本复杂度、隐式优化和贝叶斯推断的最前沿学者',
        'scholars': [
            {
                'name': 'Yue M. Lu',
                'affiliation': 'Harvard',
                'focus': 'ICL 统计力学视角',
                'description': '利用非线性统计物理工具分析线性注意力的渐进学习曲线',
                'google_scholar': 'https://scholar.google.com/citations?user=wc0FCZUAAAAJ',
                'website': 'https://yuelu-website.webflow.io/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Lu%2C+Yue+M'
            },
            {
                'name': 'Tengyu Ma',
                'affiliation': 'Stanford',
                'focus': '特征学习与复杂度',
                'description': '证明了 Transformer 在处理低秩结构任务时的统计收敛率',
                'google_scholar': 'https://scholar.google.com/citations?user=i38QlUwAAAAJ',
                'website': 'https://ai.stanford.edu/~tengyuma/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Ma%2C+Tengyu'
            },
            {
                'name': 'Song Mei',
                'affiliation': 'UC Berkeley',
                'focus': '平均场与风险演化',
                'description': '分析自回归模型在预训练与推理阶段的风险界限',
                'google_scholar': 'https://scholar.google.com/citations?user=MhDyxdYAAAAJ',
                'website': 'https://www.stat.berkeley.edu/~songmei/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Mei%2C+Song'
            },
            {
                'name': 'Jason D. Lee',
                'affiliation': 'Princeton',
                'focus': '隐式梯度下降',
                'description': '探讨 Transformer 前向传播作为优化算法的数学本质',
                'google_scholar': 'https://scholar.google.com/citations?user=GR_DsT0AAAAJ',
                'website': 'https://jasondlee.com/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Lee%2C+Jason+D'
            },
            {
                'name': 'Johannes von Oswald',
                'affiliation': 'ETH Zurich',
                'focus': '权重推断',
                'description': '提出了 Transformer 内部执行隐式梯度更新的奠基性观点',
                'google_scholar': 'https://scholar.google.com/citations?user=-K0FZcUAAAAJ',
                'website': 'https://mlcb.robots.ox.ac.uk/people/johannes-von-oswald/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Oswald%2C+Johannes+von'
            },
            {
                'name': 'Sanjeev Arora',
                'affiliation': 'Princeton',
                'focus': '表示学习与隐变量',
                'description': '研究预训练如何通过统计关联捕获上下文推断能力',
                'google_scholar': 'https://scholar.google.com/citations?user=RUP4S68AAAAJ',
                'website': 'https://www.cs.princeton.edu/~arora/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Arora%2C+Sanjeev'
            },
            {
                'name': 'Yihong Wu',
                'affiliation': 'Yale',
                'focus': '信息论界限',
                'description': '给出了 ICL 任务在最小二乘意义下的样本复杂度下界',
                'google_scholar': 'https://scholar.google.com/citations?user=HQRnt54AAAAJ',
                'website': 'https://stats.yale.edu/people/faculty/yihong-wu',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Wu%2C+Yihong'
            },
            {
                'name': 'Boaz Barak',
                'affiliation': 'Harvard',
                'focus': '相变与顿悟 (Grokking)',
                'description': '研究深度学习中从记忆到泛化的统计相变',
                'google_scholar': 'https://scholar.google.com/citations?user=I0fbJ6cAAAAJ',
                'website': 'https://boazbarak.org/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Barak%2C+Boaz'
            },
            {
                'name': 'Simon Du',
                'affiliation': 'Univ. of Washington',
                'focus': '过参数化分析',
                'description': '分析大规模 Transformer 在插值机制下的泛化表现',
                'google_scholar': 'https://scholar.google.com/citations?user=OttawxUAAAAJ',
                'website': 'https://simonshaoleidu.com/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Du%2C+Simon+S'
            },
            {
                'name': 'Christopher Ré',
                'affiliation': 'Stanford',
                'focus': '架构统计特性',
                'description': '对比线性循环结构（如 Mamba）与 Transformer 的 ICL 等价性',
                'google_scholar': 'https://scholar.google.com/citations?user=DnnCWN0AAAAJ',
                'website': 'https://cs.stanford.edu/people/chrismre/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=R%C3%A9%2C+Christopher'
            }
        ]
    },
    'generalization': {
        'name': '泛化理论与统计复杂性',
        'icon': '📐',
        'color': '#10b981',
        'description': '研究过参数化模型在"良性过拟合"状态下的稳定性与风险界限',
        'scholars': [
            {
                'name': 'Peter Bartlett',
                'affiliation': 'UC Berkeley',
                'focus': '良性过拟合、Rademacher 复杂度',
                'description': '核心人物，研究神经网络 Lipschitz 稳定性',
                'google_scholar': 'https://scholar.google.com/citations?user=yQNhFGUAAAAJ',
                'website': 'https://www.stat.berkeley.edu/~bartlett/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Bartlett%2C+Peter+L'
            },
            {
                'name': 'Mikhail Belkin',
                'affiliation': 'UCSD',
                'focus': '双下降理论',
                'description': '彻底改变了统计学对偏置-方差权衡的认知',
                'google_scholar': 'https://scholar.google.com/citations?user=Iwd9DdkAAAAJ',
                'website': 'https://mbelkin.ucsd.edu/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Belkin%2C+Mikhail'
            },
            {
                'name': 'Sasha Rakhlin',
                'affiliation': 'MIT',
                'focus': '在线学习与稳定性',
                'description': '发展了序列预测与非参数统计的统一证明框架',
                'google_scholar': 'https://scholar.google.com/citations?user=fds2VpgAAAAJ',
                'website': 'https://www.mit.edu/~rakhlin/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Rakhlin%2C+Alexander'
            },
            {
                'name': 'Matus Telgarsky',
                'affiliation': 'NYU',
                'focus': '深度学习边界',
                'description': '专注于神经网络在无穷深/宽限制下的复杂度分析',
                'google_scholar': 'https://scholar.google.com/citations?user=Fc-5yRIAAAAJ',
                'website': 'https://mjt.cs.illinois.edu/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Telgarsky%2C+Matus'
            },
            {
                'name': 'Francis Bach',
                'affiliation': 'INRIA/ENS',
                'focus': '核方法与非凸优化',
                'description': '从再生核希尔伯特空间视角审视深度学习稳定性',
                'google_scholar': 'https://scholar.google.com/citations?user=6PJWcFEAAAAJ',
                'website': 'https://www.di.ens.fr/~fbach/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Bach%2C+Francis'
            },
            {
                'name': 'Lenka Zdeborová',
                'affiliation': 'EPFL',
                'focus': '统计物理交叉',
                'description': '研究计算困难度与统计可学习性之间的相变',
                'google_scholar': 'https://scholar.google.com/citations?user=gkCjy_UAAAAJ',
                'website': 'https://ipht.cea.fr/en/personnel/zdeborova/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Zdeborov%C3%A1%2C+Lenka'
            },
            {
                'name': 'Vitaly Feldman',
                'affiliation': 'Apple/Google',
                'focus': '统计查询 (SQ) 模型',
                'description': '研究隐私保护下的学习界限',
                'google_scholar': 'https://scholar.google.com/citations?user=GqZBmfgAAAAJ',
                'website': 'https://vitaly.feldman.research/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Feldman%2C+Vitaly'
            },
            {
                'name': 'Sivan Sabato',
                'affiliation': 'Ben-Gurion Univ.',
                'focus': '主动学习理论',
                'description': '研究交互式数据获取的统计效率',
                'google_scholar': 'https://scholar.google.com/citations?user=4jTn-qIAAAAJ',
                'website': 'https://www.cs.bgu.ac.il/~sabatos/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Sabato%2C+Sivan'
            },
            {
                'name': 'Masaaki Imaizumi',
                'affiliation': 'Univ. of Tokyo',
                'focus': '非参数视角',
                'description': '从统计推断角度解析深度神经网络的层级结构',
                'google_scholar': 'https://scholar.google.com/citations?user=ZwDzTTwAAAAJ',
                'website': 'https://www.ms.u-tokyo.ac.jp/en/people/imaizumi.html',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Imaizumi%2C+Masaaki'
            },
            {
                'name': 'Gérard Ben Arous',
                'affiliation': 'NYU',
                'focus': '随机景观 (Landscapes)',
                'description': '研究非凸损失函数的拓扑复杂性',
                'google_scholar': 'https://scholar.google.com/citations?user=ZQhFI_EAAAAJ',
                'website': 'https://math.nyu.edu/people/profiles/BENAROUS_Gerard.html',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Ben+Arous%2C+G%C3%A9rard'
            }
        ]
    },
    'high_dim_stats': {
        'name': '高维统计与现代推断',
        'icon': '📊',
        'color': '#8b5cf6',
        'description': '为大规模模型提供严谨的统计工具，如符合预测、变量选择和鲁棒性',
        'scholars': [
            {
                'name': 'Emmanuel Candès',
                'affiliation': 'Stanford',
                'focus': '符合预测 (Conformal Prediction)',
                'description': '为 LLM 输出提供严谨的统计置信区间',
                'google_scholar': 'https://scholar.google.com/citations?user=BrLyrxEAAAAJ',
                'website': 'https://statistics.stanford.edu/people/emmanuel-candes',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Cand%C3%A8s%2C+Emmanuel+J'
            },
            {
                'name': 'Martin J. Wainwright',
                'affiliation': 'MIT',
                'focus': '高维统计圣经作者',
                'description': '非渐进统计分析与信息论界限',
                'google_scholar': 'https://scholar.google.com/citations?user=p1DZVX8AAAAJ',
                'website': 'https://www.stat.berkeley.edu/~wainwrig/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Wainwright%2C+Martin+J'
            },
            {
                'name': 'John Duchi',
                'affiliation': 'Stanford',
                'focus': '鲁棒性与隐私',
                'description': '优化与统计融合的领军人物',
                'google_scholar': 'https://scholar.google.com/citations?user=i5srt20AAAAJ',
                'website': 'https://web.stanford.edu/~jduchi/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Duchi%2C+John+C'
            },
            {
                'name': 'Rina Foygel Barber',
                'affiliation': 'UChicago',
                'focus': '虚假发现率 (FDR)',
                'description': '研究高维模型中的选择性推断',
                'google_scholar': 'https://scholar.google.com/citations?user=k5HsbdcAAAAJ',
                'website': 'https://stat.uchicago.edu/people/profile/rina-foygel-barber/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Barber%2C+Rina+Foygel'
            },
            {
                'name': 'Tony Cai (蔡天文)',
                'affiliation': 'Wharton',
                'focus': '适应性估计',
                'description': '高维推断与大规模数据测试的权威',
                'google_scholar': 'https://scholar.google.com/citations?user=v1MTZmIAAAAJ',
                'website': 'https://statistics.wharton.upenn.edu/profile/tcai/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Cai%2C+T+Tony'
            },
            {
                'name': 'Harrison Zhou (周)',
                'affiliation': 'Yale',
                'focus': '贝叶斯非参数',
                'description': '统计收敛率与后验分布的渐进性质',
                'google_scholar': 'https://scholar.google.com/citations?user=lTCxlGYAAAAJ',
                'website': 'https://statistics.yale.edu/people/harrison-zhou',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Zhou%2C+Harrison'
            },
            {
                'name': 'Jianqing Fan (范剑青)',
                'affiliation': 'Princeton',
                'focus': '变量选择',
                'description': '超高维数据分析与 SIS 筛选',
                'google_scholar': 'https://scholar.google.com/citations?user=TaF4L4EAAAAJ',
                'website': 'https://orfe.princeton.edu/people/jianqing-fan',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Fan%2C+Jianqing'
            },
            {
                'name': 'Robert Tibshirani',
                'affiliation': 'Stanford',
                'focus': 'LASSO 创始人',
                'description': '稀疏统计与收缩估计的代表',
                'google_scholar': 'https://scholar.google.com/citations?user=ZpG_cJwAAAAJ',
                'website': 'https://statistics.stanford.edu/people/robert-tibshirani',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Tibshirani%2C+Robert'
            },
            {
                'name': 'Trevor Hastie',
                'affiliation': 'Stanford',
                'focus': 'ESL 作者',
                'description': '定义了现代统计学习的教学架构',
                'google_scholar': 'https://scholar.google.com/citations?user=WSmKJqoAAAAJ',
                'website': 'https://statistics.stanford.edu/people/trevor-hastie',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Hastie%2C+Trevor'
            },
            {
                'name': 'Ryan Tibshirani',
                'affiliation': 'UC Berkeley',
                'focus': '凸优化与平滑',
                'description': '研究统计估计器的计算边界',
                'google_scholar': 'https://scholar.google.com/citations?user=cQ1P1qoAAAAJ',
                'website': 'https://www.stat.berkeley.edu/~ryantibs/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Tibshirani%2C+Ryan'
            }
        ]
    },
    'foundational_stats': {
        'name': '经典统计学、经验过程与稳定性',
        'icon': '📚',
        'color': '#f59e0b',
        'description': '研究统计推断的稳定性、一致性以及样本效率的根基',
        'scholars': [
            {
                'name': 'Larry Wasserman',
                'affiliation': 'CMU',
                'focus': '非参数推断',
                'description': '专注于不依赖分布假设的稳健推断',
                'google_scholar': 'https://scholar.google.com/citations?user=XcD1ffwAAAAJ',
                'website': 'https://www.stat.cmu.edu/~larry/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Wasserman%2C+Larry'
            },
            {
                'name': 'Bin Yu (郁彬)',
                'affiliation': 'UC Berkeley',
                'focus': 'PCS 框架',
                'description': '强调统计结论的可预测性与稳定性',
                'google_scholar': 'https://scholar.google.com/citations?user=KDDbvXsAAAAJ',
                'website': 'https://statistics.berkeley.edu/people/bin-yu',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Yu%2C+Bin'
            },
            {
                'name': 'Peter Bühlmann',
                'affiliation': 'ETH Zurich',
                'focus': '因果推断',
                'description': '研究高维环境下的干预效果与稳定性',
                'google_scholar': 'https://scholar.google.com/citations?user=3r-fWJwAAAAJ',
                'website': 'https://stat.ethz.ch/people/buhlmann',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=B%C3%BChlmann%2C+Peter'
            },
            {
                'name': 'Michael I. Jordan',
                'affiliation': 'UC Berkeley',
                'focus': '变分推断',
                'description': '统计与机器学习交叉领域的奠基人',
                'google_scholar': 'https://scholar.google.com/citations?user=yxUduqMAAAAJ',
                'website': 'https://people.eecs.berkeley.edu/~jordan/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Jordan%2C+Michael+I'
            },
            {
                'name': 'David Donoho',
                'affiliation': 'Stanford',
                'focus': '稀疏性与多尺度',
                'description': '高维统计计算的先驱',
                'google_scholar': 'https://scholar.google.com/citations?user=ubaxhUIAAAAJ',
                'website': 'https://statistics.stanford.edu/people/david-donoho',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Donoho%2C+David+L'
            },
            {
                'name': 'Aad van der Vaart',
                'affiliation': 'TU Delft',
                'focus': '经验过程',
                'description': '研究随机过程收敛性的核心数学理论',
                'google_scholar': 'https://scholar.google.com/citations?user=SkH-ZyIAAAAJ',
                'website': 'https://awstg.nl/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=van+der+Vaart%2C+Aad'
            },
            {
                'name': 'Sara van de Geer',
                'affiliation': 'ETH Zurich',
                'focus': 'L1 正则化',
                'description': '高维经验过程与稀疏性证明的权威',
                'google_scholar': 'https://scholar.google.com/citations?user=KNiO4pwAAAAJ',
                'website': 'https://stat.ethz.ch/people/vandegeer',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=van+de+Geer%2C+Sara'
            },
            {
                'name': 'Art B. Owen',
                'affiliation': 'Stanford',
                'focus': '经验似然',
                'description': '非参数统计中的重要工具',
                'google_scholar': 'https://scholar.google.com/citations?user=MowD-YYAAAAJ',
                'website': 'https://statistics.stanford.edu/people/art-owen',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Owen%2C+Art+B'
            },
            {
                'name': 'Subhashis Ghosal',
                'affiliation': 'NC State',
                'focus': '贝叶斯收敛',
                'description': '贝叶斯非参数统计的理论高度',
                'google_scholar': 'https://scholar.google.com/citations?user=u2tifuYAAAAJ',
                'website': 'https://stat.sciences.ncsu.edu/people/ghosal/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Ghosal%2C+Subhashis'
            },
            {
                'name': 'Enno Mammen',
                'affiliation': 'Heidelberg',
                'focus': '半参数模型',
                'description': '平滑技术与函数估计的数学理论',
                'google_scholar': 'https://scholar.google.com/citations?user=X6DfPHIAAAAJ',
                'website': 'https://www.mathi.uni-heidelberg.de/~mammen/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Mammen%2C+Enno'
            }
        ]
    },
    'probability_tools': {
        'name': '概率工具、鲁棒性与可靠性',
        'icon': '🎲',
        'color': '#ef4444',
        'description': '提供随机矩阵、集中不等式等"硬核"理论工具，并关注分布偏移',
        'scholars': [
            {
                'name': 'Roman Vershynin',
                'affiliation': 'UCI',
                'focus': '高维概率',
                'description': '其著作是推导泛化界限的必备手册',
                'google_scholar': 'https://scholar.google.com/citations?user=xXGM4gcAAAAJ',
                'website': 'https://www.math.uci.edu/~rvershyn/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Vershynin%2C+Roman'
            },
            {
                'name': 'Joel Tropp',
                'affiliation': 'Caltech',
                'focus': '随机矩阵',
                'description': '矩阵集中不等式及其在计算中的应用',
                'google_scholar': 'https://scholar.google.com/citations?user=i4_3daEAAAAJ',
                'website': 'https://tropp.caltech.edu/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Tropp%2C+Joel+A'
            },
            {
                'name': 'Aleksander Madry',
                'affiliation': 'MIT',
                'focus': '对抗鲁棒性',
                'description': '研究统计推断在极端干扰下的表现',
                'google_scholar': 'https://scholar.google.com/citations?user=SupjsEUAAAAJ',
                'website': 'https://people.csail.mit.edu/madry/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Madry%2C+Aleksander'
            },
            {
                'name': 'Jacob Steinhardt',
                'affiliation': 'UC Berkeley',
                'focus': '分布偏移',
                'description': '研究模型在测试分布变化时的稳定性界限',
                'google_scholar': 'https://scholar.google.com/citations?user=LKv32bgAAAAJ',
                'website': 'https://jsteinhardt.stat.berkeley.edu/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Steinhardt%2C+Jacob'
            },
            {
                'name': 'Sourav Chatterjee',
                'affiliation': 'Stanford',
                'focus': '高维相变',
                'description': '研究复杂统计系统中的极限分布',
                'google_scholar': 'https://scholar.google.com/citations?user=F6QiwyMAAAAJ',
                'website': 'https://statistics.stanford.edu/people/sourav-chatterjee',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Chatterjee%2C+Sourav'
            },
            {
                'name': 'Lester Mackey',
                'affiliation': 'Microsoft Research',
                'focus': 'Stein 方法',
                'description': '用于评估概率测度之间的统计距离',
                'google_scholar': 'https://scholar.google.com/citations?user=erv7TP0AAAAJ',
                'website': 'https://www.microsoft.com/en-us/research/people/lemackey/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Mackey%2C+Lester'
            },
            {
                'name': 'Pradeep Ravikumar',
                'affiliation': 'CMU',
                'focus': '图模型',
                'description': '高维鲁棒统计与概率图理论',
                'google_scholar': 'https://scholar.google.com/citations?user=Q4DTPw4AAAAJ',
                'website': 'https://www.cs.cmu.edu/~pradeepr/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Ravikumar%2C+Pradeep'
            },
            {
                'name': 'Aditi Raghunathan',
                'affiliation': 'Stanford',
                'focus': '稳健性优化',
                'description': '研究 ICL 在虚假相关下的失效',
                'google_scholar': 'https://scholar.google.com/citations?user=Ch9iRwQAAAAJ',
                'website': 'https://cs.stanford.edu/~adaragh/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Raghunathan%2C+Aditi'
            },
            {
                'name': 'Pascal Massart',
                'affiliation': 'Paris-Saclay',
                'focus': '模型选择',
                'description': '集中不等式理论的领袖',
                'google_scholar': 'https://scholar.google.com/citations?user=KqD0ysMAAAAJ',
                'website': 'https://www.math.u-psud.fr/~massart/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Massart%2C+Pascal'
            },
            {
                'name': 'Amit Singer',
                'affiliation': 'Princeton',
                'focus': '高维数据组织',
                'description': '大规模数据统计计算的数学框架',
                'google_scholar': 'https://scholar.google.com/citations?user=BNJ1QUAAAAAJ',
                'website': 'https://math.princeton.edu/people/amit-singer',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Singer%2C+Amit'
            }
        ]
    }
}


@app.route('/scholars')
def scholars_page():
    """Show scholars tracking page."""
    return generate_scholars_page()


@app.route('/scholars/<category>')
def scholars_category(category):
    """Show specific scholar category."""
    return generate_scholars_page(category)


@app.route('/api/scholars/add', methods=['POST'])
def api_add_scholar():
    """Add a scholar to user's list."""
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': '请输入学者姓名'})

    success, result = add_my_scholar(
        name=name,
        affiliation=data.get('affiliation', ''),
        focus=data.get('focus', ''),
        arxiv_query=data.get('arxiv_query', ''),
        google_scholar=data.get('google_scholar', ''),
        website=data.get('website', '')
    )
    return jsonify({'success': success, 'result': result if success else str(result)})


@app.route('/api/scholars/parse_gscholar', methods=['POST'])
def api_parse_gscholar():
    """Parse Google Scholar URL and return scholar info."""
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'success': False, 'error': '请输入 Google Scholar 链接'})

    result = parse_google_scholar_url(url)
    return jsonify(result)


@app.route('/api/scholars/remove', methods=['POST'])
def api_remove_scholar():
    """Remove a scholar from user's list."""
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': '请输入学者姓名'})

    success, message = remove_my_scholar(name)
    return jsonify({'success': success, 'message': message})


def generate_scholars_page(selected_category=None):
    """Generate scholars tracking page."""
    # Generate category tabs
    tabs_html = ''
    for cat_key, cat_data in SCHOLARS.items():
        active = 'active' if cat_key == selected_category else ''
        tabs_html += f'''
        <a href="/scholars/{cat_key}" class="category-tab {active}" style="--tab-color: {cat_data['color']}">
            <span class="tab-icon">{cat_data['icon']}</span>
            <span class="tab-name">{cat_data['name']}</span>
        </a>'''

    # Generate "我的学者" section
    my_scholars_data = load_my_scholars()
    my_scholars_html = ''
    for scholar in my_scholars_data.get('scholars', []):
        links_html = ''
        if scholar.get('google_scholar'):
            links_html += f'<a href="{scholar["google_scholar"]}" class="link-btn scholar" target="_blank">🎓 Google Scholar</a>'
        if scholar.get('website'):
            links_html += f'<a href="{scholar["website"]}" class="link-btn website" target="_blank">🌐 官网</a>'
        if scholar.get('arxiv'):
            links_html += f'<a href="{scholar["arxiv"]}" class="link-btn arxiv" target="_blank">📄 arXiv</a>'

        my_scholars_html += f'''
        <div class="scholar-card my-scholar">
            <div class="scholar-header">
                <span class="scholar-name">{scholar['name']}</span>
                <span class="scholar-affiliation">{scholar.get('affiliation', '')}</span>
            </div>
            <div class="scholar-focus">🎯 {scholar.get('focus', '')}</div>
            <div class="scholar-links">{links_html}</div>
            <button class="remove-btn" onclick="removeScholar('{scholar['name']}')">✕ 移除</button>
        </div>'''

    if not my_scholars_data.get('scholars'):
        my_scholars_html = '<div class="empty-hint">还没有添加关注的学者，使用下方表单添加</div>'

    # Add scholar form
    add_form_html = f'''
    <div class="add-scholar-section">
        <h3 class="add-title">➕ 添加新学者</h3>

        <!-- 智能添加 - Google Scholar URL -->
        <div class="quick-add-section">
            <div class="quick-add-title">🎯 快速添加（推荐）</div>
            <div class="quick-add-hint">粘贴 Google Scholar 主页链接，自动解析学者信息</div>
            <div class="quick-add-input-group">
                <input type="text" id="gsUrlInput" placeholder="https://scholar.google.com/citations?user=XXXXX">
                <button type="button" class="parse-btn" onclick="parseGoogleScholar()">🔗 解析</button>
            </div>
        </div>

        <div class="or-divider"><span>或手动填写</span></div>

        <form id="addScholarForm" class="add-form">
            <div class="form-row">
                <div class="form-group">
                    <label>姓名 *</label>
                    <input type="text" id="scholarName" placeholder="如: Yunwen Lei" required>
                </div>
                <div class="form-group">
                    <label>机构</label>
                    <input type="text" id="scholarAffiliation" placeholder="如: University of Hong Kong">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>研究方向</label>
                    <input type="text" id="scholarFocus" placeholder="如: Learning Theory, Generalization">
                </div>
                <div class="form-group">
                    <label>邮箱</label>
                    <input type="text" id="scholarEmail" placeholder="如: yunwen@hku.hk">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Google Scholar</label>
                    <input type="text" id="scholarGS" placeholder="Google Scholar 主页链接">
                </div>
                <div class="form-group">
                    <label>个人主页</label>
                    <input type="text" id="scholarWebsite" placeholder="学者个人网站">
                </div>
            </div>
            <button type="submit" class="submit-btn">添加学者</button>
        </form>
    </div>'''

    # Generate content for preset categories
    content_html = ''
    categories_to_show = [selected_category] if selected_category else list(SCHOLARS.keys())

    for cat_key in categories_to_show:
        if cat_key not in SCHOLARS:
            continue
        cat = SCHOLARS[cat_key]

        scholars_html = ''
        for scholar in cat['scholars']:
            links_html = ''
            if scholar.get('google_scholar'):
                links_html += f'<a href="{scholar["google_scholar"]}" class="link-btn scholar" target="_blank">🎓 Google Scholar</a>'
            if scholar.get('website'):
                links_html += f'<a href="{scholar["website"]}" class="link-btn website" target="_blank">🌐 官网</a>'
            if scholar.get('arxiv'):
                links_html += f'<a href="{scholar["arxiv"]}" class="link-btn arxiv" target="_blank">📄 arXiv</a>'

            scholars_html += f'''
            <div class="scholar-card">
                <div class="scholar-header">
                    <span class="scholar-name">{scholar['name']}</span>
                    <span class="scholar-affiliation">{scholar['affiliation']}</span>
                </div>
                <div class="scholar-focus">🎯 {scholar['focus']}</div>
                <div class="scholar-desc">{scholar['description']}</div>
                <div class="scholar-links">{links_html}</div>
            </div>'''

        content_html += f'''
        <div class="category-section">
            <div class="category-header">
                <span class="category-icon">{cat['icon']}</span>
                <h2 class="category-title">{cat['name']}</h2>
            </div>
            <p class="category-desc">{cat['description']}</p>
            <div class="scholars-grid">
                {scholars_html}
            </div>
        </div>'''

    # My scholars section HTML
    my_scholars_section = f'''
    <div class="category-section my-scholars-section">
        <div class="category-header">
            <span class="category-icon">⭐</span>
            <h2 class="category-title">我关注的学者</h2>
        </div>
        <p class="category-desc">你关注的学者，可以快速追踪他们在 arXiv 上的最新论文</p>
        <div class="scholars-grid">
            {my_scholars_html}
        </div>
        {add_form_html}
    </div>'''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>学者追踪 - ML Theory & Statistics</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh; color: #e0e0e0; padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}

        .header {{
            text-align: center; padding: 25px 20px;
            background: rgba(255,255,255,0.03); border-radius: 20px;
            margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.08);
        }}
        .header h1 {{
            font-size: 2em;
            background: linear-gradient(135deg, #00d4ff 0%, #7c3aed 50%, #f472b6 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        .subtitle {{ color: #888; font-size: 0.95em; }}
        .nav-links {{ margin-top: 15px; display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; }}
        .nav-link {{ color: #00d4ff; text-decoration: none; font-size: 0.9em; }}
        .nav-link:hover {{ text-decoration: underline; }}

        /* Category Tabs */
        .category-tabs {{
            display: flex; justify-content: center; gap: 10px;
            margin-bottom: 25px; flex-wrap: wrap;
        }}
        .category-tab {{
            display: flex; align-items: center; gap: 6px;
            padding: 12px 18px; background: rgba(255,255,255,0.05);
            border-radius: 12px; color: #888; text-decoration: none;
            transition: all 0.2s; border: 2px solid transparent;
            font-size: 0.85em;
        }}
        .category-tab:hover {{
            background: rgba(255,255,255,0.1); color: #fff;
            border-color: var(--tab-color);
        }}
        .category-tab.active {{
            background: color-mix(in srgb, var(--tab-color) 20%, transparent);
            border-color: var(--tab-color); color: #fff;
        }}
        .tab-icon {{ font-size: 1.3em; }}
        .tab-name {{ font-weight: 600; }}

        /* Category Section */
        .category-section {{
            margin-bottom: 35px;
            background: rgba(255,255,255,0.02);
            border-radius: 16px; padding: 25px;
            border: 1px solid rgba(255,255,255,0.06);
        }}
        .category-header {{
            display: flex; align-items: center; gap: 12px;
            margin-bottom: 10px;
        }}
        .category-icon {{ font-size: 1.8em; }}
        .category-title {{
            font-size: 1.4em; color: #fff;
        }}
        .category-desc {{
            color: #888; font-size: 0.9em; margin-bottom: 20px;
            padding-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.08);
        }}

        /* Scholars Grid */
        .scholars-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 16px;
        }}
        .scholar-card {{
            background: rgba(255,255,255,0.03); border-radius: 12px; padding: 18px;
            border: 1px solid rgba(255,255,255,0.06);
            transition: all 0.3s ease;
        }}
        .scholar-card:hover {{
            transform: translateY(-3px);
            border-color: rgba(124,58,237,0.4);
            box-shadow: 0 8px 25px rgba(124,58,237,0.15);
        }}
        .scholar-header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 10px;
        }}
        .scholar-name {{
            font-size: 1.1em; font-weight: 600; color: #fff;
        }}
        .scholar-affiliation {{
            font-size: 0.8em; color: #888;
            background: rgba(255,255,255,0.05);
            padding: 4px 10px; border-radius: 20px;
        }}
        .scholar-focus {{
            font-size: 0.85em; color: #00d4ff; margin-bottom: 8px;
        }}
        .scholar-desc {{
            font-size: 0.85em; color: #aaa; line-height: 1.5;
            margin-bottom: 12px;
        }}
        .scholar-links {{
            display: flex; gap: 8px; flex-wrap: wrap;
        }}
        .link-btn {{
            padding: 6px 12px; border-radius: 8px; font-size: 0.75em;
            text-decoration: none; transition: all 0.2s;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .link-btn.scholar {{
            background: rgba(66,133,244,0.1); color: #4285f4;
        }}
        .link-btn.scholar:hover {{
            background: rgba(66,133,244,0.2);
        }}
        .link-btn.website {{
            background: rgba(0,212,255,0.1); color: #00d4ff;
        }}
        .link-btn.website:hover {{
            background: rgba(0,212,255,0.2);
        }}
        .link-btn.arxiv {{
            background: rgba(180,39,44,0.1); color: #f77;
        }}
        .link-btn.arxiv:hover {{
            background: rgba(180,39,44,0.2);
        }}

        /* My Scholars Section */
        .my-scholars-section {{
            border-color: rgba(255,193,7,0.3);
            background: rgba(255,193,7,0.03);
        }}
        .scholar-card.my-scholar {{
            border-color: rgba(255,193,7,0.2);
        }}
        .scholar-card.my-scholar:hover {{
            border-color: rgba(255,193,7,0.5);
        }}
        .remove-btn {{
            position: absolute; top: 10px; right: 10px;
            background: rgba(239,68,68,0.2); color: #ef4444;
            border: none; border-radius: 50%; width: 24px; height: 24px;
            cursor: pointer; font-size: 12px; opacity: 0;
            transition: all 0.2s;
        }}
        .scholar-card.my-scholar:hover .remove-btn {{
            opacity: 1;
        }}
        .remove-btn:hover {{
            background: rgba(239,68,68,0.4);
        }}
        .empty-hint {{
            color: #666; font-style: italic; padding: 20px;
            text-align: center;
        }}

        /* Add Scholar Form */
        .add-scholar-section {{
            margin-top: 25px; padding-top: 25px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }}
        .add-title {{
            font-size: 1.1em; color: #fbbf24; margin-bottom: 15px;
        }}
        .add-form {{
            display: grid; gap: 12px;
        }}
        .form-row {{
            display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
        }}
        .form-group {{
            display: flex; flex-direction: column; gap: 6px;
        }}
        .form-group label {{
            font-size: 0.8em; color: #888;
        }}
        .form-group input {{
            padding: 10px 14px; border-radius: 8px;
            background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
            color: #fff; font-size: 0.9em;
        }}
        .form-group input:focus {{
            outline: none; border-color: #fbbf24;
        }}
        .form-group input::placeholder {{
            color: #555;
        }}
        .submit-btn {{
            padding: 12px 24px; border-radius: 10px;
            background: linear-gradient(135deg, #fbbf24, #f59e0b);
            color: #000; font-weight: 600; border: none;
            cursor: pointer; transition: all 0.2s;
            justify-self: start;
        }}
        .submit-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(251,191,36,0.3);
        }}

        /* Quick Add Section */
        .quick-add-section {{
            background: rgba(0,212,255,0.05); border: 1px solid rgba(0,212,255,0.2);
            border-radius: 12px; padding: 20px; margin-bottom: 20px;
        }}
        .quick-add-title {{
            font-size: 1em; color: #00d4ff; margin-bottom: 8px; font-weight: 600;
        }}
        .quick-add-hint {{
            font-size: 0.85em; color: #888; margin-bottom: 15px;
        }}
        .quick-add-input-group {{
            display: flex; gap: 10px;
        }}
        .quick-add-input-group input {{
            flex: 1; padding: 12px 16px; border-radius: 8px;
            background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
            color: #fff; font-size: 0.9em;
        }}
        .quick-add-input-group input:focus {{
            outline: none; border-color: #00d4ff;
        }}
        .parse-btn {{
            padding: 12px 20px; border-radius: 8px;
            background: linear-gradient(135deg, #00d4ff, #0ea5e9);
            color: #000; font-weight: 600; border: none;
            cursor: pointer; transition: all 0.2s; white-space: nowrap;
        }}
        .parse-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,212,255,0.3);
        }}
        .parse-btn:disabled {{
            opacity: 0.5; cursor: not-allowed;
        }}
        .or-divider {{
            display: flex; align-items: center; margin: 20px 0;
            color: #666; font-size: 0.85em;
        }}
        .or-divider::before, .or-divider::after {{
            content: ''; flex: 1; height: 1px;
            background: rgba(255,255,255,0.1);
        }}
        .or-divider span {{
            padding: 0 15px;
        }}

        .toast {{
            position: fixed; bottom: 20px; right: 20px;
            padding: 15px 25px; border-radius: 10px;
            color: #fff; font-size: 0.9em;
            transform: translateY(100px); opacity: 0;
            transition: all 0.3s; z-index: 1000;
        }}
        .toast.show {{
            transform: translateY(0); opacity: 1;
        }}
        .toast.success {{ background: #10b981; }}
        .toast.error {{ background: #ef4444; }}

        .footer {{
            text-align: center; padding: 25px; color: #555;
            font-size: 0.8em; margin-top: 25px;
        }}

        @media (max-width: 768px) {{
            .scholars-grid {{ grid-template-columns: 1fr; }}
            .category-tabs {{ flex-direction: column; align-items: center; }}
            .form-row {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎓 学者追踪</h1>
            <div class="subtitle">ML Theory & Statistics 核心学者</div>
            <div class="nav-links">
                <a href="/" class="nav-link">← 返回每日推荐</a>
                <a href="/journal" class="nav-link">📚 顶刊追踪</a>
            </div>
        </div>

        <div class="category-tabs">
            <a href="/scholars" class="category-tab {'active' if not selected_category else ''}" style="--tab-color: #fbbf24">
                <span class="tab-icon">⭐</span>
                <span class="tab-name">我关注的学者</span>
            </a>
            {tabs_html}
        </div>

        {my_scholars_section}

        {content_html}

        <div class="footer">
            <p>学者数据手动维护 | 链接指向 Google Scholar、官网和 arXiv</p>
        </div>
    </div>

    <div id="toast" class="toast"></div>

    <script>
        function showToast(message, type = 'success') {{
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast ' + type + ' show';
            setTimeout(() => toast.classList.remove('show'), 3000);
        }}

        document.getElementById('addScholarForm').addEventListener('submit', async (e) => {{
            e.preventDefault();

            const name = document.getElementById('scholarName').value;
            const affiliation = document.getElementById('scholarAffiliation').value;
            const focus = document.getElementById('scholarFocus').value;
            const email = document.getElementById('scholarEmail').value;
            const gsLink = document.getElementById('scholarGS').value;
            const website = document.getElementById('scholarWebsite').value;

            try {{
                const res = await fetch('/api/scholars/add', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        name, affiliation, focus, email,
                        google_scholar: gsLink, website
                    }})
                }});
                const data = await res.json();

                if (data.success) {{
                    showToast('✓ 学者添加成功！');
                    setTimeout(() => location.reload(), 1000);
                }} else {{
                    showToast(data.error || '添加失败', 'error');
                }}
            }} catch (err) {{
                showToast('请求失败: ' + err.message, 'error');
            }}
        }});

        async function parseGoogleScholar() {{
            const urlInput = document.getElementById('gsUrlInput');
            const url = urlInput.value.trim();

            if (!url) {{
                showToast('请输入 Google Scholar 链接', 'error');
                return;
            }}

            if (!url.includes('scholar.google.com')) {{
                showToast('请输入有效的 Google Scholar 链接', 'error');
                return;
            }}

            const btn = document.querySelector('.parse-btn');
            btn.disabled = true;
            btn.textContent = '⏳ 解析中...';

            try {{
                const res = await fetch('/api/scholars/parse_gscholar', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ url }})
                }});
                const data = await res.json();

                if (data.success) {{
                    // 填充表单
                    document.getElementById('scholarName').value = data.name || '';
                    document.getElementById('scholarAffiliation').value = data.affiliation || '';
                    document.getElementById('scholarFocus').value = data.focus || '';
                    document.getElementById('scholarEmail').value = data.email || '';
                    document.getElementById('scholarGS').value = data.google_scholar || '';
                    document.getElementById('scholarWebsite').value = data.website || '';

                    // 显示统计信息
                    let statsInfo = '';
                    if (data.citations > 0) statsInfo += ` 引用: ${{data.citations}}`;
                    if (data.h_index > 0) statsInfo += ` H-index: ${{data.h_index}}`;
                    if (statsInfo) showToast(`✓ 已解析: ${{data.name}}${{statsInfo}}`);
                    urlInput.value = '';
                }} else {{
                    showToast(data.error || '解析失败', 'error');
                }}
            }} catch (err) {{
                showToast('解析失败: ' + err.message, 'error');
            }} finally {{
                btn.disabled = false;
                btn.textContent = '🔗 解析';
            }}
        }}

        async function removeScholar(name) {{
            if (!confirm('确定要移除 ' + name + ' 吗？')) return;

            try {{
                const res = await fetch('/api/scholars/remove', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ name }})
                }});
                const data = await res.json();

                if (data.success) {{
                    showToast('已移除');
                    setTimeout(() => location.reload(), 800);
                }} else {{
                    showToast(data.message || '移除失败', 'error');
                }}
            }} catch (err) {{
                showToast('请求失败: ' + err.message, 'error');
            }}
        }}
    </script>
</body>
</html>'''


@app.route('/journal')
@app.route('/journal/<journal_key>')
@app.route('/journal/<journal_key>/v/<volume>')
@app.route('/journal/<journal_key>/v/<volume>/i/<issue>')
def journal_page(journal_key='AoS', volume=None, issue=None):
    """Show journal tracker page with volume/issue navigation."""
    from journal_tracker import generate_journal_page
    logger.debug(f"journal_page called: journal_key={journal_key}, volume={volume}, issue={issue}")
    return generate_journal_page(journal_key, volume, issue)


@app.route('/debug')
def debug_info():
    """Debug endpoint to check parsing."""
    dates = get_available_dates()
    date = dates[0] if dates else '2026-03-17'
    filepath = os.path.join(HISTORY_DIR, f'digest_{date}.md')
    papers, keywords = parse_markdown_digest(filepath)
    return jsonify({
        'date': date,
        'filepath': filepath,
        'file_exists': os.path.exists(filepath),
        'papers_count': len(papers),
        'keywords_count': len(keywords),
        'first_paper': papers[0] if papers else None
    })


@app.route('/liked')
def view_liked():
    """Show all liked papers."""
    return generate_favorites_page('liked')


@app.route('/disliked')
def view_disliked():
    """Show all disliked papers."""
    return generate_favorites_page('disliked')


def generate_favorites_page(feedback_type):
    """Generate a page showing liked or disliked papers."""
    feedback = load_feedback()
    paper_ids = feedback.get(feedback_type, [])

    # Load favorites file first (for liked papers - permanent storage)
    favorites = load_favorites()

    # Load paper cache as fallback - 使用 safe_load_json
    cache_path = os.path.join(BASE_DIR, 'cache', 'paper_cache.json')
    paper_cache = safe_load_json(cache_path, {})

    # Collect papers from all history files - 使用缓存版本
    all_papers = {}
    dates = get_available_dates()

    for date in dates:
        filepath = os.path.join(HISTORY_DIR, f'digest_{date}.md')
        if os.path.exists(filepath):
            papers, _ = parse_markdown_digest_cached(filepath)
            for paper in papers:
                if paper.get('id'):
                    all_papers[paper['id']] = paper
                    all_papers[paper['id']]['date'] = date

    # Filter papers based on feedback type
    # Priority: favorites > history > cache > placeholder
    filtered_papers = []
    found_count = 0
    for pid in paper_ids:
        # First check favorites file (permanent storage for liked papers)
        if feedback_type == 'liked' and pid in favorites:
            fav = favorites[pid]
            filtered_papers.append({
                'id': pid,
                'title': fav.get('title', f'论文 {pid}'),
                'link': fav.get('link', f'https://arxiv.org/abs/{pid}'),
                'authors': fav.get('authors', ''),
                'summary': fav.get('summary', fav.get('abstract', '')[:300] if fav.get('abstract') else ''),
                'relevance': fav.get('relevance', '来自您的收藏'),
                'score': fav.get('score', 0),
                'date': fav.get('date_published', fav.get('date_added', ''))[:10] if fav.get('date_published') or fav.get('date_added') else ''
            })
            found_count += 1
        elif pid in all_papers:
            filtered_papers.append(all_papers[pid])
            found_count += 1
        elif pid in paper_cache:
            # Use cached paper info
            cached = paper_cache[pid]
            filtered_papers.append({
                'id': pid,
                'title': cached.get('title', f'论文 {pid}'),
                'link': f'https://arxiv.org/abs/{pid}',
                'authors': cached.get('authors', '作者信息不可用'),
                'summary': cached.get('abstract', '摘要不可用'),
                'relevance': cached.get('relevance', '来自您的收藏'),
                'score': cached.get('score', 0),
                'date': cached.get('date', '')
            })
            found_count += 1
        else:
            # Create placeholder for missing paper
            filtered_papers.append({
                'id': pid,
                'title': f'论文 {pid}',
                'link': f'https://arxiv.org/abs/{pid}',
                'authors': '详情不可用',
                'summary': '此论文信息不在历史记录中，可能已被清理或未正确保存。',
                'relevance': '点击查看 arXiv 页面',
                'score': 0,
                'date': ''
            })

    # Sort by date added (newest first) for liked papers
    if feedback_type == 'liked':
        # Get date_added from favorites for sorting
        def get_sort_date(paper):
            pid = paper.get('id', '')
            if pid in favorites:
                # Parse date_added string to timestamp
                date_str = favorites[pid].get('date_added', '')
                if date_str:
                    try:
                        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    except:
                        pass
            return datetime.min

        filtered_papers.sort(key=get_sort_date, reverse=True)

    return render_favorites_html(feedback_type, filtered_papers,
                                  len(feedback.get('liked', [])), len(feedback.get('disliked', [])),
                                  found_count, len(paper_ids))


def render_favorites_html(feedback_type, papers, liked_count, disliked_count, found_count=0, total_count=0):
    """Render the favorites page showing liked or disliked papers."""
    title = "我喜欢的论文" if feedback_type == 'liked' else "不感兴趣的论文"
    empty_msg = "还没有喜欢任何论文，去浏览今日推荐吧！" if feedback_type == 'liked' else "还没有标记不感兴趣的论文"

    # Show count info if some papers are missing
    missing_info = ''
    if found_count < total_count and total_count > 0:
        missing_info = f'<div class="missing-info">显示 {found_count}/{total_count} 篇论文（{total_count - found_count} 篇详情不可用，<a href="#" onclick="fetchMissingPapers(); return false;">点击获取</a>）</div>'

    # Paper cards
    papers_html = ''
    for paper in papers:
        card_style = ''
        if feedback_type == 'liked':
            card_style = 'border-left: 4px solid #10b981;'
        elif feedback_type == 'disliked':
            card_style = 'opacity: 0.6; border-left: 4px solid #ef4444;'

        date_badge = f'<span class="date-badge">{paper.get("date", "")}</span>' if paper.get('date') else ''

        # Check if paper has incomplete info
        is_incomplete = not paper.get('score') or paper.get('score') == 0
        if is_incomplete:
            card_style += ' background: rgba(251,191,36,0.05);'

        fetch_btn = ''
        if is_incomplete:
            fetch_btn = f'<button class="fb-btn fetch" onclick="fetchPaperInfo(\'{paper.get("id", "")}\', this)">🔄 获取信息</button>'

        # Generate structured relevance HTML
        relevance_html = generate_relevance_html(paper)

        papers_html += f'''
        <div class="paper-card" data-paper-id="{paper.get('id', '')}" data-title="{paper.get('title', '').replace('"', '&quot;')}" data-summary="{paper.get('summary', '').replace('"', '&quot;')[:300]}" style="{card_style}">
            <div class="paper-header">
                {date_badge}
            </div>
            <div class="paper-title">
                <a href="{paper.get('link', '#')}" target="_blank">{paper.get('title', 'Unknown')}</a>
            </div>
            <div class="paper-authors">{paper.get('authors', '')}</div>
            <div class="paper-summary">{paper.get('summary', '')}</div>
            <div class="paper-relevance">
                <div class="paper-relevance-title">推荐理由</div>
                {relevance_html}
            </div>
            <div class="feedback-btns">
                <button class="fb-btn like {'active' if feedback_type == 'liked' else ''}" onclick="sendFeedback(this, 'like')">👍 喜欢</button>
                <button class="fb-btn dislike {'active' if feedback_type == 'disliked' else ''}" onclick="sendFeedback(this, 'dislike')">👎 不感兴趣</button>
                {fetch_btn}
                <button class="fb-btn pdf" onclick="downloadPdf('{paper.get('id', '')}')">📄 PDF</button>
                <a href="{paper.get('link', '#')}" class="fb-btn arxiv" target="_blank">arXiv →</a>
            </div>
            <div class="paper-footer">
                <span class="score-badge">Score: {paper.get('score', 0):.1f}</span>
            </div>
        </div>
'''

    if not papers:
        papers_html = f'''
        <div class="empty-state">
            <div class="empty-icon">{'❤️' if feedback_type == 'liked' else '👎'}</div>
            <div class="empty-text">{empty_msg}</div>
            <a href="/" class="nav-btn" style="display:inline-block;margin-top:20px;">查看今日推荐</a>
        </div>
'''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - arXiv Daily Digest</title>
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
            font-size: 2.5em;
            background: linear-gradient(135deg, #00d4ff 0%, #7c3aed 50%, #f472b6 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        .subtitle {{ color: #888; font-size: 1.1em; margin-bottom: 20px; }}
        .nav-tabs {{
            display: flex; justify-content: center; gap: 15px;
            margin-bottom: 25px; flex-wrap: wrap;
        }}
        .nav-tab {{
            padding: 12px 24px; background: rgba(255,255,255,0.05);
            border-radius: 12px; color: #888; text-decoration: none;
            transition: all 0.2s; border: 1px solid rgba(255,255,255,0.1);
        }}
        .nav-tab:hover {{ background: rgba(255,255,255,0.1); color: #fff; }}
        .nav-tab.active {{ background: rgba(124,58,237,0.3); color: #fff; border-color: rgba(124,58,237,0.5); }}
        .nav-tab.liked {{ border-left: 3px solid #10b981; }}
        .nav-tab.disliked {{ border-left: 3px solid #ef4444; }}
        .nav-tab.search {{ border-left: 3px solid #00d4ff; background: rgba(0,212,255,0.1); }}
        .nav-tab.search:hover {{ background: rgba(0,212,255,0.2); }}
        .nav-tab.scholars {{ border-left: 3px solid #10b981; background: rgba(16,185,129,0.1); }}
        .nav-tab.scholars:hover {{ background: rgba(16,185,129,0.2); }}
        .nav-tab.journal {{ border-left: 3px solid #f59e0b; background: rgba(245,158,11,0.1); }}
        .nav-tab.journal:hover {{ background: rgba(245,158,11,0.2); }}
        .nav-tab.stats {{ border-left: 3px solid #3b82f6; background: rgba(59,130,246,0.1); }}
        .nav-tab.stats:hover {{ background: rgba(59,130,246,0.2); }}
        .nav-tab.settings {{ border-left: 3px solid #a855f7; background: rgba(168,85,247,0.1); }}
        .nav-tab.settings:hover {{ background: rgba(168,85,247,0.2); }}
        .nav-tab.refresh {{ border-left: 3px solid #6b7280; background: rgba(107,114,128,0.1); }}
        .nav-tab.refresh:hover {{ background: rgba(107,114,128,0.2); }}
        .stats-bar {{
            display: flex; justify-content: center; gap: 30px;
            padding: 15px; margin-bottom: 20px;
            background: rgba(255,255,255,0.02); border-radius: 12px;
        }}
        .stat-item {{ text-align: center; }}
        .stat-num {{ font-size: 1.8em; font-weight: bold; color: #00d4ff; }}
        .stat-label {{ font-size: 0.8em; color: #888; }}
        .papers-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 20px;
        }}
        .paper-card {{
            background: rgba(255,255,255,0.03); border-radius: 16px; padding: 22px;
            border: 1px solid rgba(255,255,255,0.06);
            transition: all 0.3s ease; position: relative;
        }}
        .paper-card:hover {{ transform: translateY(-3px); border-color: rgba(0,212,255,0.3); }}
        .paper-header {{ margin-bottom: 10px; }}
        .date-badge {{
            background: rgba(0,212,255,0.2); color: #00d4ff;
            padding: 3px 10px; border-radius: 12px; font-size: 0.75em;
        }}
        .paper-title {{ font-size: 1.05em; font-weight: 600; color: #fff; margin-bottom: 10px; line-height: 1.4; }}
        .paper-title a {{ color: #fff; text-decoration: none; }}
        .paper-title a:hover {{ color: #00d4ff; }}
        .paper-authors {{ font-size: 0.85em; color: #888; margin-bottom: 12px; }}
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
            padding: 2px 0;
        }}
        .relevance-icon {{ font-size: 1em; min-width: 20px; text-align: center; }}
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
        .feedback-btns {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }}
        .fb-btn {{
            padding: 6px 14px; border-radius: 6px; border: none; cursor: pointer;
            font-size: 0.85em; transition: all 0.2s; text-decoration: none;
            display: inline-block;
        }}
        .fb-btn.like {{ background: rgba(16,185,129,0.2); color: #10b981; border: 1px solid #10b981; }}
        .fb-btn.like:hover, .fb-btn.like.active {{ background: rgba(16,185,129,0.5); }}
        .fb-btn.dislike {{ background: rgba(239,68,68,0.2); color: #ef4444; border: 1px solid #ef4444; }}
        .fb-btn.dislike:hover, .fb-btn.dislike.active {{ background: rgba(239,68,68,0.5); }}
        .fb-btn.pdf {{ background: rgba(59,130,246,0.2); color: #3b82f6; border: 1px solid #3b82f6; }}
        .fb-btn.pdf:hover {{ background: rgba(59,130,246,0.5); }}
        .fb-btn.arxiv {{ background: rgba(168,85,247,0.2); color: #a855f7; border: 1px solid #a855f7; }}
        .fb-btn.arxiv:hover {{ background: rgba(168,85,247,0.5); }}
        .fb-btn.follow {{ background: rgba(251,191,36,0.2); color: #fbbf24; border: 1px solid #fbbf24; }}
        .fb-btn.follow:hover {{ background: rgba(251,191,36,0.5); }}
        .fb-btn.fetch {{ background: rgba(251,191,36,0.2); color: #fbbf24; border: 1px solid #fbbf24; }}
        .fb-btn.fetch:hover {{ background: rgba(251,191,36,0.5); }}
        .fb-btn.fetch:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .empty-state {{
            text-align: center; padding: 60px 20px;
            background: rgba(255,255,255,0.02); border-radius: 20px;
        }}
        .empty-icon {{ font-size: 4em; margin-bottom: 20px; }}
        .empty-text {{ color: #888; font-size: 1.2em; }}
        .missing-info {{
            text-align: center; padding: 10px 20px; margin: 10px 0;
            background: rgba(251,191,36,0.1); border-radius: 10px;
            color: #fbbf24; font-size: 0.9em;
            border: 1px solid rgba(251,191,36,0.3);
        }}
        .footer {{
            text-align: center; padding: 30px; color: #555; font-size: 0.85em;
            margin-top: 30px;
        }}
        .toast {{
            position: fixed; bottom: 20px; right: 20px;
            background: #333; color: #fff; padding: 12px 24px;
            border-radius: 8px; z-index: 9999; animation: fadeIn 0.3s;
        }}
        @keyframes fadeIn {{ from {{opacity:0;transform:translateY(10px)}} to {{opacity:1;transform:translateY(0)}} }}
        @media (max-width: 768px) {{
            .papers-grid {{ grid-template-columns: 1fr; }}
            .stats-bar {{ flex-direction: column; gap: 10px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📚 {title}</h1>
            <div class="subtitle">arXiv Daily Digest · 收藏管理</div>
        </div>
        <div class="nav-tabs">
            <a href="/" class="nav-tab">📅 今日推荐</a>
            <a href="/search" class="nav-tab search">🔍 搜索</a>
            <a href="/scholars" class="nav-tab scholars">🎓 学者追踪</a>
            <a href="/journal" class="nav-tab journal">📚 顶刊追踪</a>
            <a href="/liked" class="nav-tab liked {'active' if feedback_type == 'liked' else ''}">❤️ 我喜欢的 ({liked_count})</a>
            <a href="/stats" class="nav-tab stats">📊 统计</a>
            <a href="/settings" class="nav-tab settings">⚙️ 设置</a>
        </div>
        <div class="stats-bar">
            <div class="stat-item">
                <div class="stat-num">{len(papers)}</div>
                <div class="stat-label">{'已喜欢' if feedback_type == 'liked' else '已标记'}</div>
            </div>
        </div>
        {missing_info}
        <div class="papers-grid">
            {papers_html}
        </div>
        <div class="footer">
            <p>arXiv Daily Recommender v3.0 | 用户反馈学习 + 多源整合</p>
        </div>
    </div>
    <script>
    function sendFeedback(btn, action) {{
        console.log('sendFeedback called:', action);
        const card = btn.closest('.paper-card');
        const paperId = card ? card.dataset.paperId : '';
        const title = card ? card.dataset.title : '';
        const summary = card ? card.dataset.summary : '';
        const authors = card ? card.dataset.authors : '';
        const score = card ? parseFloat(card.dataset.score) || 0 : 0;
        const relevance = card ? card.dataset.relevance : '';
        console.log('paperId:', paperId);

        fetch('/api/feedback', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                paper_id: paperId,
                action: action,
                title: title,
                abstract: summary,
                authors: authors,
                score: score,
                relevance: relevance
            }})
        }})
        .then(r => r.json())
        .then(data => {{
            console.log('response:', data);
            if (data.success) {{
                showToast(action === 'like' ? '✓ 已标记为喜欢' : '✓ 已标记为不感兴趣');
                setTimeout(() => location.reload(), 500);
            }} else {{
                showToast('✗ 操作失败');
            }}
        }})
        .catch(err => {{
            console.error('Error:', err);
            showToast('✗ 网络错误: ' + err.message);
        }});
    }}
    function showToast(message) {{
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2000);
    }}
    function downloadPdf(paperId) {{
        window.open('/api/pdf/' + paperId, '_blank');
    }}
    function fetchPaperInfo(paperId, btn) {{
        btn.disabled = true;
        btn.textContent = '⏳ 获取中...';
        fetch('/api/fetch_paper/' + paperId)
            .then(r => r.json())
            .then(data => {{
                if (data.success) {{
                    showToast('✓ 已获取论文信息');
                    setTimeout(() => location.reload(), 1000);
                }} else {{
                    showToast('✗ 获取失败: ' + data.error);
                    btn.disabled = false;
                    btn.textContent = '🔄 获取信息';
                }}
            }})
            .catch(err => {{
                showToast('✗ 网络错误');
                btn.disabled = false;
                btn.textContent = '🔄 获取信息';
            }});
    }}
    function fetchMissingPapers() {{
        const cards = document.querySelectorAll('.paper-card');
        let count = 0;
        cards.forEach(card => {{
            const fetchBtn = card.querySelector('.fb-btn.fetch');
            if (fetchBtn && !fetchBtn.disabled) {{
                const paperId = card.dataset.paperId;
                setTimeout(() => fetchPaperInfo(paperId, fetchBtn), count * 1000);
                count++;
            }}
        }});
        if (count === 0) {{
            showToast('没有需要获取信息的论文');
        }}
    }}
    </script>
</body>
</html>'''


@app.route('/date/<date>')
def view_date(date):
    return generate_page(date)


@app.route('/api/feedback', methods=['POST'])
def handle_feedback():
    data = request.json
    paper_id = data.get('paper_id')
    action = data.get('action')
    paper_title = data.get('title', '')
    paper_abstract = data.get('abstract', '')
    paper_authors = data.get('authors', '')
    paper_score = data.get('score', 0)
    paper_relevance = data.get('relevance', '')

    feedback = load_feedback()

    if action == 'like':
        if paper_id not in feedback['liked']:
            feedback['liked'].append(paper_id)
        if paper_id in feedback.get('disliked', []):
            feedback['disliked'].remove(paper_id)
        # Save paper info to cache when liked - try to get full info
        save_paper_to_cache(paper_id, paper_title, paper_abstract)
        # Also save to favorites file for permanent storage
        paper_info = {
            'id': paper_id,
            'title': paper_title,
            'authors': paper_authors,
            'abstract': paper_abstract,
            'summary': paper_abstract[:300] + '...' if len(paper_abstract) > 300 else paper_abstract,
            'link': f'https://arxiv.org/abs/{paper_id}',
            'score': paper_score,
            'relevance': paper_relevance,
            'date': datetime.now().strftime('%Y-%m-%d')
        }
        # Try to get full info from history if available
        full_info = find_paper_in_history(paper_id)
        if full_info:
            paper_info.update(full_info)
        add_to_favorites(paper_id, paper_info)
    elif action == 'dislike':
        if paper_id not in feedback.get('disliked', []):
            feedback.setdefault('disliked', []).append(paper_id)
        if paper_id in feedback['liked']:
            feedback['liked'].remove(paper_id)
        # Remove from favorites
        remove_from_favorites(paper_id)

    save_feedback(feedback)
    return jsonify({'success': True, 'feedback': feedback})


def save_paper_to_cache(paper_id, title, abstract):
    """Save paper info to cache for liked papers."""
    cache_path = os.path.join(BASE_DIR, 'cache', 'paper_cache.json')
    paper_cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                paper_cache = json.load(f)
        except:
            pass

    # Clean up any corrupted entries (string instead of dict)
    for k, v in list(paper_cache.items()):
        if not isinstance(v, dict):
            paper_cache[k] = {
                'title': '',
                'abstract': '',
                'date': v if isinstance(v, str) else datetime.now().strftime('%Y-%m-%d'),
                'score': 0
            }

    # Check if paper already has complete info in cache
    existing = paper_cache.get(paper_id, {})
    if isinstance(existing, dict) and existing.get('score', 0) > 0:
        # Already has complete info, just update date
        paper_cache[paper_id]['date'] = datetime.now().strftime('%Y-%m-%d')
    else:
        # Try to find full info from history files
        full_info = find_paper_in_history(paper_id)
        if full_info:
            paper_cache[paper_id] = full_info
        else:
            # Save basic info
            paper_cache[paper_id] = {
                'title': title,
                'abstract': abstract,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'score': 0
            }

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(paper_cache, f, ensure_ascii=False, indent=2)


def find_paper_in_history(paper_id):
    """Find paper info from history files - 使用缓存版本提高效率."""
    dates = get_available_dates()
    for date in dates:
        filepath = os.path.join(HISTORY_DIR, f'digest_{date}.md')
        if os.path.exists(filepath):
            papers, _ = parse_markdown_digest_cached(filepath)
            for paper in papers:
                if paper.get('id') == paper_id:
                    return {
                        'title': paper.get('title', ''),
                        'abstract': paper.get('summary', ''),
                        'authors': paper.get('authors', ''),
                        'date': date,
                        'score': paper.get('score', 0),
                        'relevance': paper.get('relevance', '')
                    }
    return None


@app.route('/api/feedback/stats')
def feedback_stats():
    feedback = load_feedback()
    return jsonify({
        'liked_count': len(feedback.get('liked', [])),
        'disliked_count': len(feedback.get('disliked', [])),
        'total_feedback': len(feedback.get('liked', [])) + len(feedback.get('disliked', []))
    })


@app.route('/api/pdf/<paper_id>')
def download_pdf(paper_id):
    pdf_path = os.path.join(BASE_DIR, 'cache', 'pdfs', f'{paper_id}.pdf')
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True)
    return f'<script>window.location.href="https://arxiv.org/pdf/{paper_id}.pdf";</script>'


@app.route('/api/dates')
def get_dates():
    return jsonify(get_available_dates())


@app.route('/api/feedback/learn', methods=['POST'])
def trigger_learning():
    """Trigger feedback learning to update topic weights."""
    import sys
    sys.path.insert(0, BASE_DIR)
    try:
        from arxiv_recommender_v5 import FeedbackLearner

        feedback_file = FEEDBACK_FILE
        cache_dir = os.path.join(BASE_DIR, 'cache')

        learner = FeedbackLearner(feedback_file, cache_dir)
        result = learner.learn_from_feedback(min_feedback=3)

        return jsonify({
            'success': True,
            'status': result.get('status'),
            'feedback_count': result.get('feedback_count', 0),
            'adjustments': result.get('adjustments', {}),
            'liked_topics': result.get('liked_topics', {}),
            'disliked_topics': result.get('disliked_topics', {})
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/citation/<paper_id>')
def get_citation(paper_id):
    """Get citation data for a paper."""
    import sys
    sys.path.insert(0, BASE_DIR)
    try:
        from arxiv_recommender_v5 import CitationAnalyzer

        cache_dir = os.path.join(BASE_DIR, 'cache')
        analyzer = CitationAnalyzer(cache_dir)
        data = analyzer.fetch_citation_data(paper_id)

        return jsonify({
            'success': True,
            'paper_id': paper_id,
            'citations': data.get('citations', 0),
            'influential_citations': data.get('influential_citations', 0),
            'references': data.get('references', 0)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/fetch_paper/<paper_id>')
def fetch_paper_info(paper_id):
    """Fetch paper info from arXiv API and save to cache."""
    import urllib.request
    import xml.etree.ElementTree as ET

    try:
        # Fetch from arXiv API
        url = f'http://export.arxiv.org/api/query?id_list={paper_id.replace("v1", "").replace("v2", "")}'
        req = urllib.request.Request(url, headers={'User-Agent': 'arXiv-Recommender/1.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read().decode('utf-8')

        # Parse XML
        root = ET.fromstring(xml_data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        entry = root.find('atom:entry', ns)
        if entry is None:
            return jsonify({'success': False, 'error': 'Paper not found'})

        title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
        summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')[:500]
        authors = ', '.join([a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)])

        # Save to cache
        cache_path = os.path.join(BASE_DIR, 'cache', 'paper_cache.json')
        paper_cache = {}
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    paper_cache = json.load(f)
            except:
                pass

        paper_cache[paper_id] = {
            'title': title,
            'abstract': summary,
            'authors': authors,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'score': 0,
            'relevance': '从 arXiv 获取'
        }

        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(paper_cache, f, ensure_ascii=False, indent=2)

        return jsonify({
            'success': True,
            'paper_id': paper_id,
            'title': title,
            'abstract': summary,
            'authors': authors
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/refresh')
def refresh_recommendations():
    """Force refresh today's recommendations."""
    import sys
    sys.path.insert(0, BASE_DIR)

    force = request.args.get('force', '0') == '1'

    try:
        from arxiv_recommender_v5 import run_pipeline, load_daily_recommendation, CONFIG as PIPELINE_CONFIG

        # Check if today's recommendation exists
        today = datetime.now().strftime('%Y-%m-%d')
        cached_papers, _ = load_daily_recommendation(PIPELINE_CONFIG['cache_dir'])

        if cached_papers and not force:
            return f'''<html><body style="font-family:sans-serif;padding:40px;background:#1a1a2e;color:#fff;text-align:center;">
                <h1>✅ 今日推荐已存在</h1>
                <p>日期: {today}</p>
                <p>论文数量: {len(cached_papers)}</p>
                <p>如需强制刷新，请 <a href="/api/refresh?force=1" style="color:#00d4ff">点击这里</a></p>
                <p><a href="/" style="color:#00d4ff">返回首页</a></p>
                </body></html>'''

        # Run pipeline with force refresh
        papers = run_pipeline(force_refresh=True)

        return f'''<html><body style="font-family:sans-serif;padding:40px;background:#1a1a2e;color:#fff;text-align:center;">
            <h1>✅ 推荐已刷新</h1>
            <p>日期: {today}</p>
            <p>论文数量: {len(papers)}</p>
            <p><a href="/" style="color:#00d4ff">返回首页查看</a></p>
            </body></html>'''
    except Exception as e:
        import traceback
        return f'''<html><body style="font-family:sans-serif;padding:40px;background:#1a1a2e;color:#fff;">
            <h1>❌ 刷新失败</h1>
            <p>错误: {str(e)}</p>
            <pre style="background:#333;padding:10px;overflow:auto;">{traceback.format_exc()}</pre>
            <p><a href="/" style="color:#00d4ff">返回首页</a></p>
            </body></html>'''


@app.route('/api/status')
def get_status():
    """Get recommendation status for today."""
    try:
        from arxiv_recommender_v5 import load_daily_recommendation, CONFIG as PIPELINE_CONFIG

        today = datetime.now().strftime('%Y-%m-%d')
        cached_papers, cached_themes = load_daily_recommendation(PIPELINE_CONFIG['cache_dir'])

        return jsonify({
            'date': today,
            'has_recommendation': cached_papers is not None,
            'paper_count': len(cached_papers) if cached_papers else 0,
            'themes': cached_themes or [],
            'generated_at': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Status error: {e}")
        return jsonify({'error': str(e)})


# ==================== Keyword Search ====================

@app.route('/search')
def search_page():
    """Show empty search page."""
    return render_search_page([], [])


@app.route('/search/<path:keywords>')
def search_keywords(keywords):
    """Search papers by custom keywords."""
    # Parse keywords
    keyword_list = [k.strip() for k in keywords.replace('/', ',').split(',') if k.strip()]

    if not keyword_list:
        return render_search_page([], [])

    # Import search function
    import sys
    sys.path.insert(0, BASE_DIR)

    try:
        from arxiv_recommender_v5 import search_by_keywords, generate_search_html

        # Search for papers
        papers = search_by_keywords(keyword_list, max_results=25, days_back=60)

        # Generate HTML
        html = generate_search_html(papers, keyword_list)
        return html

    except Exception as e:
        logger.error(f"Search error: {e}")
        return f'''<html><body style="font-family:sans-serif;padding:40px;background:#1a1a2e;color:#fff;">
            <h1>🔍 搜索出错</h1>
            <p>错误信息: {str(e)}</p>
            <p><a href="/" style="color:#00d4ff">返回首页</a></p>
            </body></html>'''


@app.route('/api/search', methods=['POST'])
def api_search():
    """API endpoint for keyword search."""
    data = request.get_json()
    keywords = data.get('keywords', [])

    if not keywords:
        return jsonify({'error': 'No keywords provided', 'papers': []})

    import sys
    sys.path.insert(0, BASE_DIR)

    try:
        from arxiv_recommender_v5 import search_by_keywords
        papers = search_by_keywords(keywords, max_results=25, days_back=60)
        return jsonify({
            'success': True,
            'papers': papers,
            'count': len(papers)
        })
    except Exception as e:
        return jsonify({'error': str(e), 'papers': []})


def render_search_page(papers, keywords):
    """Render the search page."""
    date = datetime.now().strftime('%Y-%m-%d')

    # Keywords cloud
    keywords_html = ' '.join([f'<span class="keyword-tag">{kw}</span>' for kw in keywords])

    # Paper cards
    papers_html = ''
    for paper in papers:
        authors = ', '.join(paper.get('authors', [])[:3])
        if len(paper.get('authors', [])) > 3:
            authors += f" et al. ({len(paper['authors'])} authors)"

        categories = paper.get('categories', [])[:3]
        # arXiv category friendly names
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
        cat_tags = ''.join(f'<span class="meta-tag" title="{c}">{category_names.get(c, c)}</span>' for c in categories)

        papers_html += f'''
        <div class="paper-card">
            <div class="paper-title">
                <a href="{paper.get('link', '#')}" target="_blank">{paper.get('title', 'Unknown')}</a>
            </div>
            <div class="paper-authors">{authors}</div>
            <div class="paper-meta">{cat_tags}</div>
            <div class="paper-summary">{paper.get('summary', '')}</div>
            <div class="paper-relevance">
                <div class="paper-relevance-title">匹配关键词</div>
                <div class="paper-relevance-text">{paper.get('relevance_reason', '关键词匹配')}</div>
            </div>
            <div class="paper-footer">
                <span class="score-badge">Score: {paper.get('score', 0):.1f}</span>
                <a href="{paper.get('link', '#')}" class="paper-link" target="_blank">arXiv →</a>
            </div>
        </div>
'''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>arXiv 关键词搜索</title>
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
            width: 450px; max-width: 100%;
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
            padding: 2px 0;
        }}
        .relevance-icon {{ font-size: 1em; min-width: 20px; text-align: center; }}
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
        .search-tips {{
            background: rgba(255,255,255,0.02); border-radius: 12px;
            padding: 15px 20px; margin-top: 20px; text-align: left;
            border: 1px solid rgba(255,255,255,0.05);
        }}
        .search-tips h3 {{ color: #00d4ff; font-size: 0.9em; margin-bottom: 10px; }}
        .search-tips ul {{ color: #888; font-size: 0.85em; padding-left: 20px; }}
        .search-tips li {{ margin: 5px 0; }}
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
            <div class="search-tips">
                <h3>💡 搜索技巧</h3>
                <ul>
                    <li>使用英文关键词效果更好（如：transformer, attention mechanism）</li>
                    <li>可以用逗号或空格分隔多个关键词</li>
                    <li>支持搜索标题和摘要中的内容</li>
                    <li>搜索结果按相关度排序</li>
                </ul>
            </div>
        </div>

        <div class="nav-tabs">
            <a href="/" class="nav-tab">📅 今日推荐</a>
            <a href="/search" class="nav-tab search active">🔍 搜索</a>
            <a href="/scholars" class="nav-tab scholars">🎓 学者追踪</a>
            <a href="/journal" class="nav-tab journal">📚 顶刊追踪</a>
            <a href="/liked" class="nav-tab liked">❤️ 喜欢</a>
            <a href="/stats" class="nav-tab stats">📊 统计</a>
            <a href="/settings" class="nav-tab settings">⚙️ 设置</a>
        </div>

        {f'<div class="keywords-section"><div class="keyword-tag" style="background:rgba(124,58,237,0.5)">搜索关键词</div><div>{keywords_html}</div><div class="stats">找到 {len(papers)} 篇相关论文 · 搜索时间: {date}</div></div><div class="papers-grid">{papers_html}</div>' if keywords else '<div class="keywords-section"><div class="stats">输入关键词开始搜索 arXiv 论文</div></div>'}

        {'<div class="no-results">未找到相关论文，请尝试其他关键词</div>' if keywords and not papers else ''}

        <div class="footer">
            <p>arXiv Keyword Search | 自由关键词论文搜索</p>
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


# ==================== Settings Page ====================

@app.route('/settings')
def settings_page():
    """Settings page for modifying keywords."""
    import sys
    sys.path.insert(0, BASE_DIR)

    try:
        from arxiv_recommender_v5 import load_user_config, get_priority_topics, get_dislike_topics

        config = load_user_config()
        priority_topics = get_priority_topics()
        dislike_topics = get_dislike_topics()

        # Get settings
        settings = config.get('settings', {})
        papers_per_day = settings.get('papers_per_day', 20)
        prefer_theory = settings.get('prefer_theory', True)

        # Theory preference
        theory_pref = config.get('theory_preference', {})
        theory_enabled = theory_pref.get('enabled', True)

    except Exception as e:
        logger.error(f"Error loading config: {e}")
        priority_topics = []
        dislike_topics = []
        papers_per_day = 20
        prefer_theory = True
        theory_enabled = True

    # Load keywords config for interactive management
    keywords_config = load_keywords_config()

    # 从配置文件获取关键词 (不再硬编码，避免重复维护)
    core_keywords = list(keywords_config.get('core_topics', {}).keys())
    secondary_keywords = list(keywords_config.get('secondary_topics', {}).keys())
    theory_keywords = keywords_config.get('theory_keywords', [])

    # Topics as text
    topics_text = ', '.join(priority_topics)
    dislike_text = ', '.join(dislike_topics)

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>设置 - arXiv 推荐系统</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh; color: #e0e0e0; padding: 20px;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .header {{
            text-align: center; padding: 30px 20px;
            background: rgba(255,255,255,0.03); border-radius: 20px;
            margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.08);
        }}
        .header h1 {{
            font-size: 2.2em;
            background: linear-gradient(135deg, #00d4ff 0%, #7c3aed 50%, #f472b6 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
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
        .settings-card {{
            background: rgba(255,255,255,0.03); border-radius: 16px;
            padding: 25px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.08);
        }}
        .settings-title {{
            font-size: 1.2em; color: #00d4ff; margin-bottom: 15px;
            display: flex; align-items: center; gap: 10px;
        }}
        .settings-desc {{
            color: #888; font-size: 0.9em; margin-bottom: 15px;
        }}
        .form-group {{ margin-bottom: 20px; }}
        .form-label {{
            display: block; color: #ccc; margin-bottom: 8px; font-weight: 500;
        }}
        .form-input {{
            width: 100%; padding: 12px 15px; font-size: 1em;
            background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px; color: #fff; outline: none;
            transition: all 0.2s;
        }}
        .form-input:focus {{ border-color: #00d4ff; }}
        .form-textarea {{
            width: 100%; padding: 12px 15px; font-size: 0.95em;
            background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px; color: #fff; outline: none;
            min-height: 120px; resize: vertical; font-family: inherit;
        }}
        .form-textarea:focus {{ border-color: #00d4ff; }}
        .checkbox-group {{
            display: flex; align-items: center; gap: 10px;
        }}
        .checkbox-input {{
            width: 20px; height: 20px; cursor: pointer;
        }}
        .checkbox-label {{ color: #ccc; cursor: pointer; }}
        .btn-group {{ display: flex; gap: 15px; margin-top: 25px; }}
        .btn {{
            padding: 12px 30px; font-size: 1em; border-radius: 10px;
            cursor: pointer; transition: all 0.2s; border: none;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, #7c3aed, #00d4ff); color: #fff;
        }}
        .btn-primary:hover {{ transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0,212,255,0.3); }}
        .btn-secondary {{
            background: rgba(255,255,255,0.1); color: #fff; border: 1px solid rgba(255,255,255,0.2);
        }}
        .btn-secondary:hover {{ background: rgba(255,255,255,0.15); }}
        .btn-regenerate {{
            background: linear-gradient(135deg, #f59e0b, #ef4444); color: #fff;
        }}
        .btn-regenerate:hover {{ transform: translateY(-2px); box-shadow: 0 4px 15px rgba(239,68,68,0.3); }}
        .toast {{
            position: fixed; bottom: 20px; right: 20px;
            background: #10b981; color: #fff; padding: 12px 24px;
            border-radius: 10px; z-index: 9999; display: none;
            animation: slideIn 0.3s ease;
        }}
        .toast.error {{ background: #ef4444; }}
        @keyframes slideIn {{
            from {{ transform: translateX(100%); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}
        .help-text {{ color: #666; font-size: 0.85em; margin-top: 5px; }}
        .topic-preview {{
            display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px;
        }}
        .topic-tag {{
            background: rgba(124,58,237,0.2); padding: 4px 12px;
            border-radius: 15px; font-size: 0.85em; color: #a78bfa;
            border: 1px solid rgba(124,58,237,0.3);
        }}
        /* Interactive Keyword Tags */
        .keyword-tags-container {{
            display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 15px;
        }}
        .keyword-tag-item {{
            display: inline-flex; align-items: center; gap: 6px;
            background: linear-gradient(135deg, rgba(124,58,237,0.3), rgba(0,212,255,0.3));
            padding: 6px 12px; border-radius: 20px; font-size: 0.9em;
            border: 1px solid rgba(255,255,255,0.1); transition: all 0.2s;
        }}
        .keyword-tag-item:hover {{
            transform: scale(1.02);
            border-color: rgba(0,212,255,0.5);
        }}
        .keyword-tag-item.secondary {{
            background: linear-gradient(135deg, rgba(16,185,129,0.3), rgba(0,212,255,0.2));
        }}
        .keyword-tag-item.theory {{
            background: linear-gradient(135deg, rgba(245,158,11,0.3), rgba(239,68,68,0.2));
        }}
        .keyword-tag-delete {{
            cursor: pointer; color: #ef4444; font-weight: bold;
            font-size: 1.1em; line-height: 1; opacity: 0.7;
        }}
        .keyword-tag-delete:hover {{ opacity: 1; }}
        .keyword-add-form {{
            display: flex; gap: 10px; margin-top: 15px;
        }}
        .keyword-add-form input {{
            flex: 1; padding: 10px 15px; font-size: 0.95em;
            background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px; color: #fff; outline: none;
        }}
        .keyword-add-form input:focus {{ border-color: #00d4ff; }}
        .keyword-add-form select {{
            padding: 10px; border-radius: 10px;
            background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
            color: #fff; cursor: pointer;
        }}
        .keyword-add-form button {{
            padding: 10px 20px; border-radius: 10px;
            background: linear-gradient(135deg, #7c3aed, #00d4ff); color: #fff;
            border: none; cursor: pointer; font-weight: 500;
        }}
        .keyword-add-form button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 15px rgba(0,212,255,0.3);
        }}
        .keyword-section-label {{
            font-size: 0.85em; color: #888; margin-bottom: 8px; margin-top: 15px;
        }}
        .keyword-section-label:first-child {{ margin-top: 0; }}
        .footer {{ text-align: center; padding: 30px; color: #555; font-size: 0.85em; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚙️ 推荐设置</h1>
            <p style="color:#888;">自定义推荐关键词和偏好</p>
        </div>

        <div class="nav-tabs">
            <a href="/" class="nav-tab">📅 今日推荐</a>
            <a href="/search" class="nav-tab search">🔍 搜索</a>
            <a href="/scholars" class="nav-tab scholars">🎓 学者追踪</a>
            <a href="/journal" class="nav-tab journal">📚 顶刊追踪</a>
            <a href="/liked" class="nav-tab liked">❤️ 喜欢</a>
            <a href="/stats" class="nav-tab stats">📊 统计</a>
            <a href="/settings" class="nav-tab settings active">⚙️ 设置</a>
        </div>

        <form id="settingsForm">
            <div class="settings-card" id="keywords">
                <div class="settings-title">🎯 推荐关键词</div>
                <div class="settings-desc">
                    在此管理你的研究关键词，系统会优先推荐相关论文
                </div>

                <div class="keyword-section-label">🔥 核心关键词（高优先级）</div>
                <div class="keyword-tags-container" id="coreKeywords">
                    {''.join([f'<span class="keyword-tag-item" data-keyword="{kw}" data-type="core">{kw}<span class="keyword-tag-delete" onclick="deleteKeyword(this)">&times;</span></span>' for kw in core_keywords])}
                </div>

                <div class="keyword-section-label">📈 次要关键词（中优先级）</div>
                <div class="keyword-tags-container" id="secondaryKeywords">
                    {''.join([f'<span class="keyword-tag-item secondary" data-keyword="{kw}" data-type="secondary">{kw}<span class="keyword-tag-delete" onclick="deleteKeyword(this)">&times;</span></span>' for kw in secondary_keywords])}
                </div>

                <div class="keyword-section-label">📚 理论关键词（带证明/界限）</div>
                <div class="keyword-tags-container" id="theoryKeywords">
                    {''.join([f'<span class="keyword-tag-item theory" data-keyword="{kw}" data-type="theory">{kw}<span class="keyword-tag-delete" onclick="deleteKeyword(this)">&times;</span></span>' for kw in theory_keywords])}
                </div>

                <div class="keyword-add-form">
                    <input type="text" id="newKeyword" placeholder="输入新关键词..." onkeypress="if(event.key==='Enter'){{event.preventDefault();addKeyword();}}">
                    <select id="keywordType">
                        <option value="core">🔥 核心关键词</option>
                        <option value="secondary">📈 次要关键词</option>
                        <option value="theory">📚 理论关键词</option>
                    </select>
                    <button type="button" onclick="addKeyword()">添加</button>
                </div>
            </div>

            <div class="settings-card">
                <div class="settings-title">🚫 不感兴趣的主题</div>
                <div class="settings-desc">
                    这些主题的论文会被降权处理
                </div>
                <div class="form-group">
                    <label class="form-label">降权主题（用逗号分隔）</label>
                    <textarea class="form-textarea" id="dislikeTopics" name="dislikeTopics"
                              placeholder="例如：optimal transport, meta-learning">{dislike_text}</textarea>
                </div>
            </div>

            <div class="settings-card">
                <div class="settings-title">📊 推荐参数</div>
                <div class="form-group">
                    <label class="form-label">每日推荐数量</label>
                    <input type="number" class="form-input" id="papersPerDay" name="papersPerDay"
                           value="{papers_per_day}" min="5" max="50" style="max-width:150px;">
                </div>
                <div class="form-group">
                    <div class="checkbox-group">
                        <input type="checkbox" class="checkbox-input" id="preferTheory" name="preferTheory"
                               {"checked" if prefer_theory else ""}>
                        <label class="checkbox-label" for="preferTheory">优先推荐理论论文（带证明、界限等）</label>
                    </div>
                </div>
                <div class="form-group">
                    <div class="checkbox-group">
                        <input type="checkbox" class="checkbox-input" id="theoryEnabled" name="theoryEnabled"
                               {"checked" if theory_enabled else ""}>
                        <label class="checkbox-label" for="theoryEnabled">启用理论偏好（给理论论文加分）</label>
                    </div>
                </div>
            </div>

            <div class="btn-group">
                <button type="submit" class="btn btn-primary">💾 保存设置</button>
                <button type="button" class="btn btn-regenerate" onclick="saveAndRegenerate()">
                    🔄 保存并重新生成今日推荐
                </button>
                <button type="button" class="btn btn-secondary" onclick="location.href='/'">取消</button>
            </div>
        </form>

        <div class="footer">
            <p>arXiv Recommender Settings | 修改设置后可选择重新生成推荐</p>
        </div>
    </div>

    <div id="toast" class="toast"></div>

    <script>
    function showToast(message, isError = false) {{
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = isError ? 'toast error' : 'toast';
        toast.style.display = 'block';
        setTimeout(() => toast.style.display = 'none', 3000);
    }}

    // Keyword management functions
    async function addKeyword() {{
        const input = document.getElementById('newKeyword');
        const keyword = input.value.trim();
        const type = document.getElementById('keywordType').value;

        if (!keyword) {{
            showToast('请输入关键词', true);
            return;
        }}

        try {{
            const response = await fetch('/api/keywords', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{keyword: keyword, type: type}})
            }});
            const result = await response.json();

            if (result.success) {{
                // Add tag to UI
                const container = document.getElementById(type + 'Keywords');
                const tag = document.createElement('span');
                tag.className = 'keyword-tag-item' + (type === 'secondary' ? ' secondary' : type === 'theory' ? ' theory' : '');
                tag.setAttribute('data-keyword', keyword.toLowerCase());
                tag.setAttribute('data-type', type);
                tag.innerHTML = keyword.toLowerCase() + '<span class="keyword-tag-delete" onclick="deleteKeyword(this)">&times;</span>';
                container.appendChild(tag);

                input.value = '';
                showToast('✓ 已添加: ' + keyword);
            }} else {{
                showToast('✗ 添加失败: ' + result.error, true);
            }}
        }} catch (err) {{
            showToast('✗ 网络错误: ' + err.message, true);
        }}
    }}

    async function deleteKeyword(element) {{
        const tag = element.parentElement;
        const keyword = tag.getAttribute('data-keyword');
        const type = tag.getAttribute('data-type');

        try {{
            const response = await fetch('/api/keywords', {{
                method: 'DELETE',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{keyword: keyword, type: type}})
            }});
            const result = await response.json();

            if (result.success) {{
                tag.remove();
                showToast('✓ 已删除: ' + keyword);
            }} else {{
                showToast('✗ 删除失败: ' + result.error, true);
            }}
        }} catch (err) {{
            showToast('✗ 网络错误: ' + err.message, true);
        }}
    }}

    document.getElementById('settingsForm').addEventListener('submit', async function(e) {{
        e.preventDefault();
        await saveSettings(false);
    }});

    async function saveSettings(regenerate = false) {{
        // Collect keywords from tags
        const coreKws = Array.from(document.querySelectorAll('#coreKeywords .keyword-tag-item')).map(el => el.getAttribute('data-keyword'));
        const secondaryKws = Array.from(document.querySelectorAll('#secondaryKeywords .keyword-tag-item')).map(el => el.getAttribute('data-keyword'));
        const theoryKws = Array.from(document.querySelectorAll('#theoryKeywords .keyword-tag-item')).map(el => el.getAttribute('data-keyword'));

        const data = {{
            coreTopics: coreKws,
            secondaryTopics: secondaryKws,
            theoryKeywords: theoryKws,
            dislikeTopics: document.getElementById('dislikeTopics').value,
            papersPerDay: parseInt(document.getElementById('papersPerDay').value),
            preferTheory: document.getElementById('preferTheory').checked,
            theoryEnabled: document.getElementById('theoryEnabled').checked,
            regenerate: regenerate
        }};

        try {{
            const response = await fetch('/api/settings', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify(data)
            }});
            const result = await response.json();

            if (result.success) {{
                showToast('✓ 设置已保存！');
                if (regenerate) {{
                    showToast('🔄 正在重新生成推荐...');
                    setTimeout(() => location.href = '/', 1500);
                }}
            }} else {{
                showToast('✗ 保存失败: ' + result.error, true);
            }}
        }} catch (err) {{
            showToast('✗ 网络错误: ' + err.message, true);
        }}
    }}

    function saveAndRegenerate() {{
        saveSettings(true);
    }}
    </script>
</body>
</html>'''


@app.route('/api/settings', methods=['POST'])
def save_settings():
    """Save user settings and sync to user_profile.json (unified config)."""
    data = request.get_json()

    try:
        from config_manager import get_config
        cm = get_config()

        # Parse topics from arrays (new format)
        core_topics = data.get('coreTopics', [])
        secondary_topics = data.get('secondaryTopics', [])
        theory_keywords = data.get('theoryKeywords', [])
        dislike_text = data.get('dislikeTopics', '')
        dislike_topics = [t.strip() for t in dislike_text.split(',') if t.strip()]

        # If coreTopics is empty, try legacy format
        if not core_topics:
            priority_text = data.get('priorityTopics', '')
            core_topics = [t.strip() for t in priority_text.split(',') if t.strip()]

        # Clear existing keywords first
        cm._keywords.clear()

        # Set core topics (default weight based on importance)
        core_weights = {
            'statistical learning theory': 4.5,
            'nonparametric estimation': 4.0,
            'conditional density estimation': 3.5,
            'in-context learning': 5.0,
            'conformal prediction': 5.0,
            'generalization': 4.0,
            'excess risk': 4.0,
            'minimax rates': 3.5,
            'sample complexity': 3.5,
            'finite-sample': 3.0,
            'transformer theory': 3.0,
        }
        for topic in core_topics:
            weight = core_weights.get(topic.lower(), 4.0)
            cm.set_keyword(topic, weight, 'core')

        # Set secondary topics
        secondary_weights = {
            'uniform convergence': 3.0,
            'algorithmic stability': 2.5,
            'empirical risk minimization': 2.0,
            'concentration inequalities': 3.0,
            'learning theory': 2.5,
            'estimation': 0.5,
            'risk bounds': 2.5,
        }
        for topic in secondary_topics:
            weight = secondary_weights.get(topic.lower(), 2.5)
            cm.set_keyword(topic, weight, 'secondary')

        # Set theory keywords in config
        if theory_keywords:
            cm._config['theory_keywords'] = theory_keywords

        # Set dislike topics
        for topic in dislike_topics:
            cm.set_keyword(topic, -1.0, 'dislike')

        # Update settings
        cm._settings.papers_per_day = data.get('papersPerDay', 20)
        cm._settings.prefer_theory = data.get('preferTheory', True)

        # Save to user_profile.json
        cm.save()

        # Reload config in recommender module
        from config_manager import reload_config
        reload_config()

        logger.info(f"Saved {len(core_topics)} core, {len(secondary_topics)} secondary, {len(theory_keywords)} theory keywords")

        # Regenerate if requested
        regenerate = data.get('regenerate', False)
        if regenerate:
            try:
                import threading
                from arxiv_recommender_v5 import run_pipeline
                # Run in background
                thread = threading.Thread(target=run_pipeline, kwargs={'force_refresh': True})
                thread.start()
            except Exception as e:
                logger.error(f"Error regenerating: {e}")

        return jsonify({
            'success': True,
            'message': f'Saved {len(core_topics)} core, {len(secondary_topics)} secondary, {len(theory_keywords)} theory keywords',
            'core_count': len(core_topics),
            'secondary_count': len(secondary_topics),
            'theory_count': len(theory_keywords)
        })

    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


# ==================== Reading Statistics ====================

@app.route('/stats')
def reading_stats():
    """Reading statistics page."""
    feedback = load_feedback()
    favorites = load_favorites()

    # Calculate statistics
    liked_ids = feedback.get('liked', [])
    disliked_ids = feedback.get('disliked', [])
    favorite_ids = list(favorites.keys())

    # Get available dates
    dates = get_available_dates()

    # Calculate this week's stats
    from datetime import datetime, timedelta
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Parse dates from paper IDs (format: YYMM.NNNNN)
    def parse_paper_date(paper_id):
        try:
            # arXiv ID format: YYMM.NNNNN
            year_month = paper_id.split('v')[0][:4]
            year = 2000 + int(year_month[:2])
            month = int(year_month[2:4])
            return datetime(year, month, 1)
        except:
            return None

    # Count papers by time period
    weekly_liked = sum(1 for pid in liked_ids if parse_paper_date(pid) and parse_paper_date(pid) >= week_ago)
    monthly_liked = sum(1 for pid in liked_ids if parse_paper_date(pid) and parse_paper_date(pid) >= month_ago)

    # Load today's papers for keyword analysis
    today_papers = []
    today_str = today.strftime('%Y-%m-%d')
    today_file = os.path.join(HISTORY_DIR, f'digest_{today_str}.md')
    if os.path.exists(today_file):
        today_papers, _ = parse_markdown_digest(today_file)

    # Analyze keywords from liked papers
    keyword_counts = {}
    import re
    for pid in liked_ids:
        # Find paper in favorites or history
        if pid in favorites:
            text = (favorites[pid].get('title', '') + ' ' + favorites[pid].get('abstract', '')).lower()
        else:
            text = ''
            for date in dates[:7]:  # Check recent dates
                filepath = os.path.join(HISTORY_DIR, f'digest_{date}.md')
                if os.path.exists(filepath):
                    papers, _ = parse_markdown_digest(filepath)
                    for p in papers:
                        if p.get('id') == pid:
                            text = (p.get('title', '') + ' ' + p.get('summary', '')).lower()
                            break
                if text:
                    break

        # Count keywords
        keywords = re.findall(r'\b[a-z]+(?:\s+[a-z]+)?\b', text)
        for kw in keywords:
            if len(kw) > 4:  # Skip short words
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

    top_keywords = sorted(keyword_counts.items(), key=lambda x: -x[1])[:15]

    # Calculate total papers seen
    total_seen = 0
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                total_seen = len(cache_data)
        except:
            pass

    # Pre-calculate values for f-string
    avg_daily_likes = len(liked_ids) / max(len(dates), 1)
    like_rate = len(liked_ids) * 100 // max(len(liked_ids) + len(disliked_ids), 1)
    total_feedback = len(liked_ids) + len(disliked_ids)

    # Generate keywords HTML
    keywords_html = ''.join([f'<div class="keyword-item"><span>{kw}</span><span class="keyword-count">{count}</span></div>' for kw, count in top_keywords])

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>阅读统计 - arXiv 推荐系统</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh; color: #e0e0e0; padding: 20px;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .header {{
            text-align: center; padding: 30px 20px;
            background: rgba(255,255,255,0.03); border-radius: 20px;
            margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.08);
        }}
        .header h1 {{
            font-size: 2.2em;
            background: linear-gradient(135deg, #00d4ff 0%, #7c3aed 50%, #f472b6 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
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
        .stats-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px; margin-bottom: 30px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.03); border-radius: 16px; padding: 25px;
            text-align: center; border: 1px solid rgba(255,255,255,0.06);
            transition: all 0.3s;
        }}
        .stat-card:hover {{ transform: translateY(-3px); border-color: rgba(0,212,255,0.3); }}
        .stat-number {{
            font-size: 2.8em; font-weight: bold;
            background: linear-gradient(135deg, #00d4ff, #7c3aed);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        .stat-label {{ color: #888; font-size: 0.9em; margin-top: 8px; }}
        .stat-card.liked .stat-number {{ color: #10b981; -webkit-text-fill-color: #10b981; }}
        .stat-card.disliked .stat-number {{ color: #ef4444; -webkit-text-fill-color: #ef4444; }}
        .stat-card.favorites .stat-number {{ color: #f59e0b; -webkit-text-fill-color: #f59e0b; }}
        .section {{
            background: rgba(255,255,255,0.03); border-radius: 16px; padding: 25px;
            margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.06);
        }}
        .section-title {{
            font-size: 1.2em; color: #fff; margin-bottom: 20px;
            display: flex; align-items: center; gap: 10px;
        }}
        .keywords-list {{
            display: flex; flex-wrap: wrap; gap: 10px;
        }}
        .keyword-item {{
            background: linear-gradient(135deg, rgba(124,58,237,0.3), rgba(0,212,255,0.3));
            padding: 8px 16px; border-radius: 20px; color: #fff;
            display: flex; align-items: center; gap: 8px;
        }}
        .keyword-count {{
            background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 10px;
            font-size: 0.85em;
        }}
        .progress-bar {{
            height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px;
            overflow: hidden; margin-top: 10px;
        }}
        .progress-fill {{
            height: 100%; background: linear-gradient(90deg, #00d4ff, #7c3aed);
            border-radius: 4px; transition: width 0.5s;
        }}
        .footer {{ text-align: center; padding: 30px; color: #555; font-size: 0.85em; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 阅读统计</h1>
            <p style="color:#888;">追踪你的论文阅读习惯</p>
        </div>

        <div class="nav-tabs">
            <a href="/" class="nav-tab">📅 今日推荐</a>
            <a href="/search" class="nav-tab search">🔍 搜索</a>
            <a href="/scholars" class="nav-tab scholars">🎓 学者追踪</a>
            <a href="/journal" class="nav-tab journal">📚 顶刊追踪</a>
            <a href="/liked" class="nav-tab liked">❤️ 喜欢</a>
            <a href="/stats" class="nav-tab stats active">📊 统计</a>
            <a href="/settings" class="nav-tab settings">⚙️ 设置</a>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{total_seen}</div>
                <div class="stat-label">📚 总共浏览</div>
            </div>
            <div class="stat-card liked">
                <div class="stat-number">{len(liked_ids)}</div>
                <div class="stat-label">❤️ 喜欢的论文</div>
            </div>
            <div class="stat-card disliked">
                <div class="stat-number">{len(disliked_ids)}</div>
                <div class="stat-label">👎 不感兴趣</div>
            </div>
            <div class="stat-card favorites">
                <div class="stat-number">{len(favorite_ids)}</div>
                <div class="stat-label">⭐ 收藏的论文</div>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{weekly_liked}</div>
                <div class="stat-label">📅 本周喜欢</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{monthly_liked}</div>
                <div class="stat-label">📆 本月喜欢</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(dates)}</div>
                <div class="stat-label">🗓️ 活跃天数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{avg_daily_likes:.1f}</div>
                <div class="stat-label">📈 日均喜欢</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">🏷️ 你最关注的关键词</div>
            <div class="keywords-list">
                {keywords_html}
            </div>
        </div>

        <div class="section">
            <div class="section-title">📈 喜欢率</div>
            <div style="color:#888; margin-bottom:10px;">
                你喜欢的论文占所有反馈的 {like_rate}%
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {like_rate}%"></div>
            </div>
        </div>

        <div class="footer">
            <p>arXiv Recommender Statistics | 数据保存在本地</p>
        </div>
    </div>
</body>
</html>'''


# ==================== Related Papers ====================

@app.route('/api/related/<paper_id>')
def get_related_papers(paper_id):
    """Get related papers based on a given paper."""
    import sys
    sys.path.insert(0, BASE_DIR)

    try:
        # First, get the paper info
        paper_info = None
        favorites = load_favorites()

        # Check favorites first
        if paper_id in favorites:
            paper_info = favorites[paper_id]
        else:
            # Try to fetch from arXiv
            import urllib.request
            url = f"http://export.arxiv.org/api/query?id_list={{{paper_id}}}"
            req = urllib.request.Request(url, headers={{'User-Agent': 'Mozilla/5.0'}})
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                import xml.etree.ElementTree as ET
                xml_data = resp.read().decode('utf-8')
                root = ET.fromstring(xml_data)
                ns = {{'atom': 'http://www.w3.org/2005/Atom'}}

                for entry in root.findall('atom:entry', ns):
                    title_elem = entry.find('atom:title', ns)
                    abstract_elem = entry.find('atom:summary', ns)
                    paper_info = {{
                        'title': title_elem.text.strip() if title_elem is not None else '',
                        'abstract': abstract_elem.text.strip() if abstract_elem is not None else ''
                    }}

        if not paper_info:
            return jsonify({{'error': 'Paper not found', 'related': []}})

        # Extract keywords from paper
        text = (paper_info.get('title', '') + ' ' + paper_info.get('abstract', '')).lower()

        # Find important terms
        import re
        # Extract potential keywords (2-4 word phrases)
        words = re.findall(r'\b[a-z]+\b', text)
        word_freq = {}
        for w in words:
            if len(w) > 4:  # Skip short words
                word_freq[w] = word_freq.get(w, 0) + 1

        top_keywords = sorted(word_freq.items(), key=lambda x: -x[1])[:5]
        keywords = [k[0] for k in top_keywords]

        # Search for related papers
        from arxiv_recommender_v5 import search_by_keywords
        related = search_by_keywords(keywords, max_results=10, days_back=180)

        # Remove the original paper
        related = [p for p in related if p.get('id') != paper_id][:5]

        return jsonify({{'success': True, 'related': related, 'keywords': keywords}})

    except Exception as e:
        return jsonify({{'error': str(e), 'related': []}})


# ==================== Keywords Management API ====================

@app.route('/api/keywords', methods=['GET', 'POST', 'DELETE'])
def manage_keywords():
    """API for managing keywords configuration.

    GET: Return current keywords config
    POST: Add a new keyword (body: {"keyword": "...", "type": "core|secondary|theory"})
    DELETE: Delete a keyword (body: {"keyword": "...", "type": "core|secondary|theory"})
    """
    if request.method == 'GET':
        # Return current keywords config
        config = load_keywords_config()
        return jsonify({
            'success': True,
            'config': config
        })

    elif request.method == 'POST':
        data = request.get_json()

        # 检查是否是批量更新（前端 saveKeywords 发送整个配置对象）
        if 'core_topics' in data or 'secondary_topics' in data or 'demote_topics' in data:
            # 批量更新整个配置
            config = load_keywords_config()

            # 更新各类关键词
            if 'core_topics' in data:
                config['core_topics'] = data['core_topics']
            if 'secondary_topics' in data:
                config['secondary_topics'] = data['secondary_topics']
            if 'theory_keywords' in data:
                config['theory_keywords'] = data['theory_keywords']
            if 'demote_topics' in data:
                config['demote_topics'] = data['demote_topics']
            if 'dislike_topics' in data:
                # dislike_topics 可能是数组或对象
                dislike = data['dislike_topics']
                if isinstance(dislike, list):
                    config['dislike_topics'] = {k: -1.0 for k in dislike}
                else:
                    config['dislike_topics'] = dislike

            save_keywords_config(config)
            logger.info(f"Batch updated keywords config via web UI")
            return jsonify({'success': True, 'message': 'Keywords configuration updated'})

        # 单个关键词添加（兼容旧接口）
        keyword = data.get('keyword', '').strip().lower()
        kw_type = data.get('type', 'core')

        if not keyword:
            return jsonify({'success': False, 'error': 'Keyword cannot be empty'})

        config = load_keywords_config()

        if kw_type == 'core':
            if 'core_topics' not in config:
                config['core_topics'] = {}
            if keyword not in config['core_topics']:
                config['core_topics'][keyword] = 1.0
        elif kw_type == 'secondary':
            if 'secondary_topics' not in config:
                config['secondary_topics'] = {}
            if keyword not in config['secondary_topics']:
                config['secondary_topics'][keyword] = 0.5
        elif kw_type == 'theory':
            if 'theory_keywords' not in config:
                config['theory_keywords'] = []
            if keyword not in config['theory_keywords']:
                config['theory_keywords'].append(keyword)
        elif kw_type == 'demote':
            if 'demote_topics' not in config:
                config['demote_topics'] = {}
            if keyword not in config['demote_topics']:
                config['demote_topics'][keyword] = -1.0
        elif kw_type == 'dislike':
            if 'dislike_topics' not in config:
                config['dislike_topics'] = {}
            config['dislike_topics'][keyword] = -1.0
        else:
            return jsonify({'success': False, 'error': 'Invalid keyword type'})

        save_keywords_config(config)
        return jsonify({'success': True, 'message': f'Added keyword: {keyword}'})

    elif request.method == 'DELETE':
        # Delete a keyword
        data = request.get_json()
        keyword = data.get('keyword', '').strip().lower()
        kw_type = data.get('type', 'core')

        if not keyword:
            return jsonify({'success': False, 'error': 'Keyword cannot be empty'})

        config = load_keywords_config()
        removed = False

        if kw_type == 'core':
            if keyword in config.get('core_topics', {}):
                del config['core_topics'][keyword]
                removed = True
        elif kw_type == 'secondary':
            if keyword in config.get('secondary_topics', {}):
                del config['secondary_topics'][keyword]
                removed = True
        elif kw_type == 'theory':
            if keyword in config.get('theory_keywords', []):
                config['theory_keywords'].remove(keyword)
                removed = True

        if removed:
            save_keywords_config(config)
            return jsonify({'success': True, 'message': f'Removed keyword: {keyword}'})
        else:
            return jsonify({'success': False, 'error': 'Keyword not found'})


if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("arXiv Recommender Web Server v3.0")
    logger.info("New: Citation Analysis + Feedback Learning")
    logger.info("=" * 50)
    logger.info(f"History dates available: {len(get_available_dates())}")

    # 定期更新期刊的后台任务
    def scheduled_journal_updates():
        """Background task for scheduled journal updates.

        - JMLR: 每天检查更新
        - 统计四大 (AoS, JASA, Biometrika, JRSS-B): 每周检查更新
        """
        import time
        from datetime import datetime, timedelta

        # 更新配置
        JOURNAL_SCHEDULE = {
            'JMLR': {'interval_hours': 24, 'description': '每天'},      # JMLR: 每天更新
            'AoS': {'interval_hours': 168, 'description': '每周'},     # 统计四大: 每周更新
            'JASA': {'interval_hours': 168, 'description': '每周'},
            'Biometrika': {'interval_hours': 168, 'description': '每周'},
            'JRSS-B': {'interval_hours': 168, 'description': '每周'},
        }

        # 加载上次更新时间记录
        def load_last_update_times():
            update_log_path = os.path.join(BASE_DIR, 'cache', 'journal_update_log.json')
            return safe_load_json(update_log_path, {})

        def save_last_update_time(journal_key):
            update_log_path = os.path.join(BASE_DIR, 'cache', 'journal_update_log.json')
            log = load_last_update_times()
            if journal_key not in log:
                log[journal_key] = {}
            log[journal_key]['last_check'] = datetime.now().isoformat()
            with open(update_log_path, 'w', encoding='utf-8') as f:
                json.dump(log, f, indent=2)

        def should_update(journal_key):
            """检查是否需要更新"""
            log = load_last_update_times()
            config = JOURNAL_SCHEDULE.get(journal_key, {'interval_hours': 168})
            last_check = log.get(journal_key, {}).get('last_check', '')

            if not last_check:
                return True

            try:
                last_time = datetime.fromisoformat(last_check)
                hours_since = (datetime.now() - last_time).total_seconds() / 3600
                return hours_since >= config['interval_hours']
            except:
                return True

        time.sleep(15)  # 等待服务器完全启动

        while True:
            try:
                now = datetime.now()
                logger.info(f"[Scheduled Update] Checking journals at {now.strftime('%Y-%m-%d %H:%M')}...")

                # 检查每个期刊是否需要更新
                journals_to_update = []
                for journal_key, config in JOURNAL_SCHEDULE.items():
                    if should_update(journal_key):
                        journals_to_update.append(journal_key)
                        logger.info(f"  [{journal_key}] Due for update ({config['description']})")

                if journals_to_update:
                    from journal_update import update_journal

                    for journal_key in journals_to_update:
                        try:
                            logger.info(f"[Scheduled Update] Updating {journal_key}...")
                            added = update_journal(journal_key, from_year=2025, force=False)
                            save_last_update_time(journal_key)
                            logger.info(f"[Scheduled Update] {journal_key}: +{added} new papers")
                        except Exception as e:
                            logger.error(f"[Scheduled Update] Error updating {journal_key}: {e}")

                        time.sleep(2)  # 避免请求过快

                    logger.info("[Scheduled Update] All updates complete.")
                else:
                    logger.info("[Scheduled Update] No journals due for update.")

            except Exception as e:
                logger.error(f"[Scheduled Update] Error: {e}")

            # 每小时检查一次是否有期刊需要更新
            time.sleep(3600)

    # 在后台线程中运行定期更新
    update_thread = threading.Thread(target=scheduled_journal_updates, daemon=True)
    update_thread.start()

    logger.info("Open http://localhost:5555 in your browser")
    logger.info("=" * 50)
    app.run(host='localhost', port=5555, debug=False, use_reloader=False)