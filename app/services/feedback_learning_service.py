"""Feedback learning service — learn topic weights from user feedback and history."""

from __future__ import annotations

import json
import os
from collections import Counter
from typing import Dict, List

from logger_config import get_logger

from app.services.paper_utils import parse_arxiv_identity
from app.services.settings_service import (
    DEFAULT_PRIORITY_TOPICS,
    get_dislike_topics,
    get_priority_topics,
    get_topic_weights,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Standalone function (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------


def learn_from_feedback(feedback: Dict, papers: List[Dict]) -> Dict[str, float]:
    """Learn topic weights from user feedback."""
    priority_topics = get_priority_topics()
    topic_weights = get_topic_weights()

    if not feedback.get('liked') and not feedback.get('disliked'):
        return topic_weights

    # Analyze liked papers
    liked_topics: Counter = Counter()
    disliked_topics: Counter = Counter()

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


# ---------------------------------------------------------------------------
# Full feedback learner class (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------


class FeedbackLearner:
    """Learn durable topic signals from local feedback and cached history."""

    def __init__(self, feedback_file: str, cache_dir: str):
        self.feedback_file = feedback_file
        self.cache_dir = cache_dir

    def _load_feedback(self) -> Dict:
        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {'liked': [], 'disliked': []}

    def _iter_cached_papers(self) -> List[Dict]:
        papers: List[Dict] = []
        run_dir = os.path.join(self.cache_dir, 'recommendation_runs')
        if os.path.isdir(run_dir):
            for filename in sorted(os.listdir(run_dir)):
                if not filename.endswith('.json'):
                    continue
                try:
                    with open(os.path.join(run_dir, filename), 'r', encoding='utf-8') as f:
                        papers.extend(json.load(f).get('papers', []))
                except (OSError, json.JSONDecodeError):
                    continue

        for filename in ('daily_recommendation.json', 'favorite_papers.json', 'paper_cache.json'):
            path = os.path.join(self.cache_dir, filename)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and 'papers' in data:
                papers.extend(data.get('papers') or [])
            elif isinstance(data, dict):
                for paper_id, value in data.items():
                    if isinstance(value, dict):
                        item = dict(value)
                        item.setdefault('id', paper_id)
                        papers.append(item)
        return papers

    @staticmethod
    def _paper_keys(paper: Dict) -> set:
        identity = parse_arxiv_identity(paper.get('id') or paper.get('link') or '')
        keys = {paper.get('id', ''), identity['base_id'], identity['canonical_id']}
        return {key for key in keys if key}

    def _topic_counts(self, paper_ids: List[str], paper_index: Dict[str, Dict]) -> Counter:
        topics = list(dict.fromkeys(
            get_priority_topics()
            + get_dislike_topics()
            + DEFAULT_PRIORITY_TOPICS
            + ['federated learning', 'benchmark']
        ))
        counts: Counter = Counter()
        for paper_id in paper_ids:
            identity = parse_arxiv_identity(paper_id)
            paper = paper_index.get(paper_id) or paper_index.get(identity['base_id'])
            if not paper:
                continue
            text = f"{paper.get('title', '')} {paper.get('abstract', paper.get('summary', ''))}".lower()
            for topic in topics:
                if topic.lower() in text:
                    counts[topic] += 1
        return counts

    def learn_from_feedback(self, min_feedback: int = 3) -> Dict:
        feedback = self._load_feedback()
        liked_ids = feedback.get('liked', [])
        disliked_ids = feedback.get('disliked', [])
        feedback_count = len(liked_ids) + len(disliked_ids)
        if feedback_count < min_feedback:
            return {
                'status': 'insufficient_feedback',
                'feedback_count': feedback_count,
                'adjustments': {},
                'liked_topics': {},
                'disliked_topics': {},
            }

        paper_index: Dict[str, Dict] = {}
        for paper in self._iter_cached_papers():
            if not isinstance(paper, dict):
                continue
            for key in self._paper_keys(paper):
                paper_index[key] = paper

        liked_topics = self._topic_counts(liked_ids, paper_index)
        disliked_topics = self._topic_counts(disliked_ids, paper_index)
        adjustments = {}
        for topic in set(liked_topics) | set(disliked_topics):
            delta = liked_topics.get(topic, 0) - disliked_topics.get(topic, 0)
            if delta:
                adjustments[topic] = round(delta * 0.25, 3)

        return {
            'status': 'learned',
            'feedback_count': feedback_count,
            'adjustments': adjustments,
            'liked_topics': dict(liked_topics),
            'disliked_topics': dict(disliked_topics),
        }


__all__ = ["FeedbackLearner", "learn_from_feedback"]
