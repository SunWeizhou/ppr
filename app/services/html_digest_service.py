"""HTML generators for daily digest and keyword search results."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Dict, List

from logger_config import get_logger

from app.services.settings_service import load_keywords_config

logger = get_logger(__name__)


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
            <a href="/" class="nav-tab active">\U0001f4c5 今日推荐</a>
            <a href="/search.html" class="nav-tab">\U0001f50d 关键词搜索</a>
            <a href="/journal.html" class="nav-tab">\U0001f4da 顶刊追踪</a>
            <a href="/scholars.html" class="nav-tab">\U0001f393 学者追踪</a>
            <a href="/liked.html" class="nav-tab">❤️ 我喜欢的</a>
            <a href="/" class="nav-tab">\U0001f504 Return to Web App</a>
        </div>

        <!-- Today's Matched Keywords -->
        <div class="today-keywords-section">
            <div class="today-keywords-title">\U0001f4cc 今日匹配关键词 (Top {len(today_keywords)})</div>
            <div class="today-keywords-tags">
                {today_keywords_html if today_keywords_html else '<span style="color:#888">暂无匹配关键词</span>'}
            </div>
        </div>

        <!-- Keywords Management Section -->
        <div class="keywords-section">
            <div class="keywords-header" onclick="toggleKeywords()">
                <h2>\U0001f3f7️ 关键词管理</h2>
                <span class="keywords-toggle" id="keywords-toggle">▼</span>
            </div>
            <div class="keywords-content" id="keywords-content">
                <div class="keyword-category">
                    <div class="keyword-category-title">\U0001f525 核心关键词 (Core Topics)</div>
                    <div class="keyword-tags" id="core-topics-tags">
                        {core_topics_html}
                    </div>
                    <div class="keyword-add-form">
                        <input type="text" id="new-core-topic" placeholder="添加核心关键词...">
                        <button onclick="addKeyword('core')">添加</button>
                    </div>
                </div>

                <div class="keyword-category">
                    <div class="keyword-category-title">\U0001f4da 次要关键词 (Secondary Topics)</div>
                    <div class="keyword-tags" id="secondary-topics-tags">
                        {secondary_topics_html}
                    </div>
                    <div class="keyword-add-form">
                        <input type="text" id="new-secondary-topic" placeholder="添加次要关键词...">
                        <button onclick="addKeyword('secondary')">添加</button>
                    </div>
                </div>

                <div class="keyword-category">
                    <div class="keyword-category-title">\U0001f9e0 理论关键词 (Theory Keywords)</div>
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
                    \U0001f4be 保存关键词并重新生成推荐
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

            if (type === 'theory' || type === 'dislike') {{
                if (!keywordsConfig[configKey].includes(value)) {{
                    keywordsConfig[configKey].push(value);
                }}
            }} else {{
                keywordsConfig[configKey][value] = type === 'demote' ? -1.0 : 3.0;
            }}

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
        matched: set = set()
        all_keywords = list(core_topics.keys()) + list(secondary_topics.keys()) + theory_keywords

        for paper in papers[:20]:
            text = (paper.get('title', '') + ' ' + paper.get('abstract', ''))
            for kw in all_keywords:
                if self._count_keyword(text, kw) > 0:
                    matched.add(kw)

        return sorted(matched)

    @staticmethod
    def _count_keyword(text: str, keyword: str) -> int:
        """Count keyword occurrences with flexible matching."""
        keyword_lower = keyword.lower()
        text_lower = text.lower()

        if ' ' in keyword_lower or '-' in keyword_lower:
            return text_lower.count(keyword_lower)
        else:
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            return len(re.findall(pattern, text_lower))

    def _generate_relevance_html(self, paper: Dict) -> str:
        """Generate HTML for structured relevance reasons with icons."""
        breakdown = paper.get('relevance_breakdown', [])
        if not breakdown:
            return f'<div class="relevance-item"><span class="relevance-icon">\U0001f4a1</span><span class="relevance-text">{paper.get("relevance_reason", "Matches your research interests")}</span></div>'

        html_items = []
        for reason in breakdown[:4]:
            icon = reason.get('icon', '\U0001f4cc')
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
                    <button class="fb-btn like" onclick="sendFeedback('{paper['id']}', 'like')">\U0001f44d 喜欢</button>
                    <button class="fb-btn dislike" onclick="sendFeedback('{paper['id']}', 'dislike')">\U0001f44e 不感兴趣</button>
                    <button class="fb-btn abstract" id="btn-{paper['id']}" onclick="toggleAbstract('{paper['id']}')">展开摘要</button>
                    <button class="fb-btn pdf" onclick="downloadPdf('{paper['id']}')">\U0001f4c4 PDF</button>
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


# ---------------------------------------------------------------------------
# Search HTML generator (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------


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
            <h1>\U0001f50d 关键词论文搜索</h1>
            <div class="search-box">
                <input type="text" class="search-input" id="keywordInput"
                       placeholder="输入关键词，用逗号或空格分隔..."
                       value="{', '.join(keywords)}">
                <button class="search-btn" onclick="doSearch()">搜索</button>
            </div>
        </div>

        <div class="nav-tabs">
            <a href="/" class="nav-tab">\U0001f4c5 今日推荐</a>
            <a href="/search" class="nav-tab active">\U0001f50d 关键词搜索</a>
            <a href="/journal" class="nav-tab">\U0001f4da 顶刊追踪</a>
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


__all__ = ["HTMLGenerator", "generate_search_html"]
