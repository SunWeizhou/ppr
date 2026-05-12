import re
import os

with open('docs/superpowers/plans/2026-05-11-phase4-recommendation-engine.md', 'r') as f:
    text = f.read()

tests = []
engine = []

blocks = re.split(r'```python', text)[1:]
for block in blocks:
    content = block.split('```')[0].strip()
    if 'test_recommendation_engine.py' in content:
        # Remove the first comment line
        lines = content.split('\n')
        if lines[0].startswith('#'):
            lines = lines[1:]
        tests.append('\n'.join(lines).strip())
    elif 'recommendation_engine.py' in content or content.startswith('import abc') or content.startswith('def _days_since_publication') or content.startswith('# -----') or content.startswith('from logger_config import') or content.startswith('def build_display_reason'):
        # For engine, some blocks don't have the filename but start with 'import abc' etc
        lines = content.split('\n')
        if lines[0].startswith('# app/'):
            lines = lines[2:] # Remove filename and docstring because we handle it
        engine.append('\n'.join(lines).strip())

tests_str = '\n\n'.join(tests)
engine_str = '\n\n'.join(engine)

# Clean up tests string
# Convert to unittest
tests_str = tests_str.replace('import pytest', 'import unittest')
tests_str = re.sub(r'class Test([a-zA-Z0-9_]+):', r'class Test\1(unittest.TestCase):', tests_str)

# Convert pytest asserts to unittest asserts
tests_str = tests_str.replace('assert c.paper_id == "2401.00001"', 'self.assertEqual(c.paper_id, "2401.00001")')
tests_str = tests_str.replace('assert c.source_strategy == "for_you"', 'self.assertEqual(c.source_strategy, "for_you")')
tests_str = tests_str.replace('assert c.score_breakdown["relevance"] == 0.8', 'self.assertEqual(c.score_breakdown["relevance"], 0.8)')
tests_str = tests_str.replace('assert c.score_breakdown == {}', 'self.assertEqual(c.score_breakdown, {})')
tests_str = tests_str.replace('assert c.paper_data == {}', 'self.assertEqual(c.paper_data, {})')
tests_str = tests_str.replace('assert d["paper_id"] == "x"', 'self.assertEqual(d["paper_id"], "x")')
tests_str = tests_str.replace('assert isinstance(d, dict)', 'self.assertIsInstance(d, dict)')
tests_str = tests_str.replace('assert result["composite"] == 0.0', 'self.assertEqual(result["composite"], 0.0)')
tests_str = tests_str.replace('assert len(result["breakdown"]) == 5', 'self.assertEqual(len(result["breakdown"]), 5)')
tests_str = tests_str.replace('assert abs(result["composite"] - 1.0) < 1e-6', 'self.assertAlmostEqual(result["composite"], 1.0, places=5)')
tests_str = tests_str.replace('assert abs(total - 1.0) < 1e-6', 'self.assertAlmostEqual(total, 1.0, places=5)')
tests_str = tests_str.replace('assert rel_only["composite"] > cit_only["composite"]', 'self.assertGreater(rel_only["composite"], cit_only["composite"])')
tests_str = tests_str.replace('assert abs(result["composite"] - 0.7) < 1e-6', 'self.assertAlmostEqual(result["composite"], 0.7, places=5)')
tests_str = tests_str.replace('assert 0.0 <= result["composite"] <= 1.0', 'self.assertTrue(0.0 <= result["composite"] <= 1.0)')
tests_str = tests_str.replace('assert normalize_citation_score(0) == 0.0', 'self.assertEqual(normalize_citation_score(0), 0.0)')
tests_str = tests_str.replace('assert 0.0 < normalize_citation_score(10) < normalize_citation_score(100)', 'self.assertTrue(0.0 < normalize_citation_score(10) < normalize_citation_score(100))')
tests_str = tests_str.replace('assert normalize_citation_score(10000) <= 1.0', 'self.assertLessEqual(normalize_citation_score(10000), 1.0)')
tests_str = tests_str.replace('assert normalize_freshness_score(0) > 0.9', 'self.assertGreater(normalize_freshness_score(0), 0.9)')
tests_str = tests_str.replace('assert normalize_freshness_score(365) < 0.2', 'self.assertLess(normalize_freshness_score(365), 0.2)')
tests_str = tests_str.replace('with pytest.raises(TypeError):', 'with self.assertRaises(TypeError):')

tests_str = tests_str.replace('assert len(candidates) > 0', 'self.assertGreater(len(candidates), 0)')
tests_str = tests_str.replace('assert all(isinstance(c, Candidate) for c in candidates)', 'self.assertTrue(all(isinstance(c, Candidate) for c in candidates))')
tests_str = tests_str.replace('assert all(c.source_strategy == "for_you" for c in candidates)', 'self.assertTrue(all(c.source_strategy == "for_you" for c in candidates))')
tests_str = tests_str.replace('assert len(candidates) == len(papers)', 'self.assertEqual(len(candidates), len(papers))')
tests_str = tests_str.replace('assert candidates[0].reason  # non-empty reason', 'self.assertTrue(candidates[0].reason)')
tests_str = tests_str.replace('assert candidates[0].paper_id == "high"', 'self.assertEqual(candidates[0].paper_id, "high")')
tests_str = tests_str.replace('assert all(c.source_strategy == "trending" for c in candidates)', 'self.assertTrue(all(c.source_strategy == "trending" for c in candidates))')
tests_str = tests_str.replace('assert candidates[0].paper_id == "new"', 'self.assertEqual(candidates[0].paper_id, "new")')
tests_str = tests_str.replace('assert len(candidates) == 2', 'self.assertEqual(len(candidates), 2)')
tests_str = tests_str.replace('assert candidates[0].paper_id == "1"', 'self.assertEqual(candidates[0].paper_id, "1")')
tests_str = tests_str.replace('assert "Nature" in candidates[0].reason', 'self.assertIn("Nature", candidates[0].reason)')
tests_str = tests_str.replace('assert len(candidates) == 1', 'self.assertEqual(len(candidates), 1)')
tests_str = tests_str.replace('assert candidates[0].score == 0.0', 'self.assertEqual(candidates[0].score, 0.0)')
tests_str = tests_str.replace('assert all(c.source_strategy == "question" for c in candidates)', 'self.assertTrue(all(c.source_strategy == "question" for c in candidates))')
tests_str = tests_str.replace('assert "sections" in result', 'self.assertIn("sections", result)')
tests_str = tests_str.replace('assert len(result["sections"]) > 0', 'self.assertGreater(len(result["sections"]), 0)')
tests_str = tests_str.replace('assert "strategy" in section', 'self.assertIn("strategy", section)')
tests_str = tests_str.replace('assert "title" in section', 'self.assertIn("title", section)')
tests_str = tests_str.replace('assert "candidates" in section', 'self.assertIn("candidates", section)')
tests_str = tests_str.replace('assert "for_you" in strategy_names', 'self.assertIn("for_you", strategy_names)')
tests_str = tests_str.replace('assert len(ids) == len(set(ids))', 'self.assertEqual(len(ids), len(set(ids)))')
tests_str = tests_str.replace('assert len(section["candidates"]) <= 5', 'self.assertLessEqual(len(section["candidates"]), 5)')
tests_str = tests_str.replace('assert "graph neural networks" in candidates[0].reason.lower() or "drug discovery" in candidates[0].reason.lower()', 'self.assertTrue("graph neural networks" in candidates[0].reason.lower() or "drug discovery" in candidates[0].reason.lower())')
tests_str = tests_str.replace('assert "250" in candidates[0].reason', 'self.assertIn("250", candidates[0].reason)')
tests_str = tests_str.replace('assert "hinton" in candidates[0].reason.lower() or "Geoffrey" in candidates[0].reason', 'self.assertTrue("hinton" in candidates[0].reason.lower() or "Geoffrey" in candidates[0].reason)')
tests_str = tests_str.replace('assert isinstance(reason, str)', 'self.assertIsInstance(reason, str)')
tests_str = tests_str.replace('assert len(reason) > 0', 'self.assertGreater(len(reason), 0)')
tests_str = tests_str.replace('assert len(reason) <= 120  # One-line constraint', 'self.assertLessEqual(len(reason), 120)')
tests_str = tests_str.replace('assert len(result["sections"]) >= 2  # At least for_you and trending', 'self.assertGreaterEqual(len(result["sections"]), 2)')
tests_str = tests_str.replace('assert len(result["all_candidates"]) > 0', 'self.assertGreater(len(result["all_candidates"]), 0)')
tests_str = tests_str.replace('assert c.reason', 'self.assertTrue(c.reason)')
tests_str = tests_str.replace('assert len(display) > 0', 'self.assertGreater(len(display), 0)')
tests_str = tests_str.replace('assert result["sections"] == []', 'self.assertEqual(result["sections"], [])')
tests_str = tests_str.replace('assert result["all_candidates"] == []', 'self.assertEqual(result["all_candidates"], [])')
tests_str = tests_str.replace('assert "composite" in result', 'self.assertIn("composite", result)')
tests_str = tests_str.replace('assert "breakdown" in result', 'self.assertIn("breakdown", result)')
tests_str = tests_str.replace('assert all(dim in result["breakdown"] for dim in ("relevance", "citation", "freshness", "entity_affinity", "feedback"))', 'self.assertTrue(all(dim in result["breakdown"] for dim in ("relevance", "citation", "freshness", "entity_affinity", "feedback")))')
tests_str = tests_str.replace('assert "raw" in dim_info', 'self.assertIn("raw", dim_info)')
tests_str = tests_str.replace('assert "weight" in dim_info', 'self.assertIn("weight", dim_info)')
tests_str = tests_str.replace('assert "weighted" in dim_info', 'self.assertIn("weighted", dim_info)')

# Handle "assert candidates[0].reason" -> "self.assertTrue(candidates[0].reason)" (some might still be left)

final_engine = '"""Multi-strategy recommendation engine with multi-dimensional scoring."""\n\n' + engine_str
final_tests = '"""Tests for the multi-strategy recommendation engine."""\n\n' + tests_str

with open('app/services/recommendation_engine.py', 'w') as f:
    f.write(final_engine)

with open('tests/test_recommendation_engine.py', 'w') as f:
    f.write(final_tests)

print("Extraction completed!")
