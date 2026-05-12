import re

with open('docs/superpowers/plans/2026-05-11-phase4-recommendation-engine.md', 'r') as f:
    text = f.read()

tests = ""
engine = ""

for block in re.split(r'```python', text)[1:]:
    content = block.split('```')[0]
    if '# Append to tests/test_recommendation_engine.py' in content:
        tests += content.replace('# Append to tests/test_recommendation_engine.py\n', '')
    elif 'Append to `app/services/recommendation_engine.py`' in block or '# ---------------------------------------------------------------------------' in content:
        # Some are just plain code blocks
        engine += content

with open('tests/test_recommendation_engine.py', 'a') as f:
    # Need to convert pytest asserts to unittest asserts
    tests = tests.replace('assert len(candidates) > 0', 'self.assertGreater(len(candidates), 0)')
    tests = tests.replace('assert all(isinstance(c, Candidate) for c in candidates)', 'self.assertTrue(all(isinstance(c, Candidate) for c in candidates))')
    tests = tests.replace('assert all(c.source_strategy == "for_you" for c in candidates)', 'self.assertTrue(all(c.source_strategy == "for_you" for c in candidates))')
    tests = tests.replace('assert len(candidates) == len(papers)', 'self.assertEqual(len(candidates), len(papers))')
    tests = tests.replace('assert candidates[0].reason', 'self.assertTrue(candidates[0].reason)')
    tests = tests.replace('assert candidates[0].paper_id == "high"', 'self.assertEqual(candidates[0].paper_id, "high")')
    tests = tests.replace('assert all(c.source_strategy == "trending" for c in candidates)', 'self.assertTrue(all(c.source_strategy == "trending" for c in candidates))')
    tests = tests.replace('assert candidates[0].paper_id == "new"', 'self.assertEqual(candidates[0].paper_id, "new")')
    tests = tests.replace('assert len(candidates) == 2', 'self.assertEqual(len(candidates), 2)')
    tests = tests.replace('assert candidates[0].paper_id == "1"', 'self.assertEqual(candidates[0].paper_id, "1")')
    tests = tests.replace('assert "Nature" in candidates[0].reason', 'self.assertIn("Nature", candidates[0].reason)')
    tests = tests.replace('assert len(candidates) == 1', 'self.assertEqual(len(candidates), 1)')
    tests = tests.replace('assert candidates[0].score == 0.0', 'self.assertEqual(candidates[0].score, 0.0)')
    tests = tests.replace('assert all(c.source_strategy == "question" for c in candidates)', 'self.assertTrue(all(c.source_strategy == "question" for c in candidates))')
    tests = tests.replace('class TestBaseStrategy:', 'import unittest\nclass TestBaseStrategy(unittest.TestCase):')
    tests = tests.replace('class TestForYouStrategy:', 'class TestForYouStrategy(unittest.TestCase):')
    tests = tests.replace('class TestTrendingStrategy:', 'class TestTrendingStrategy(unittest.TestCase):')
    tests = tests.replace('class TestEntityStrategy:', 'class TestEntityStrategy(unittest.TestCase):')
    tests = tests.replace('class TestReadingStrategy:', 'class TestReadingStrategy(unittest.TestCase):')
    tests = tests.replace('class TestQuestionStrategy:', 'class TestQuestionStrategy(unittest.TestCase):')
    # For TestBaseStrategy, we need to handle pytest.raises
    tests = tests.replace('with pytest.raises(TypeError):', 'with self.assertRaises(TypeError):')
    
    f.write(tests)

with open('app/services/recommendation_engine.py', 'a') as f:
    f.write(engine)

