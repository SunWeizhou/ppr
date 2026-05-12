"""Test QueryRewriter with and without LLM provider."""
import unittest
from unittest.mock import MagicMock
from dataclasses import asdict

from app.services.query_rewriter import QueryRewriter, RewriteResult


class TestRewriteResult(unittest.TestCase):
    def test_no_rewrite_when_no_llm(self):
        """Without LLM, rewriter returns original query unchanged."""
        rewriter = QueryRewriter(provider_factory=lambda: None)
        result = rewriter.rewrite("RL papers")
        # Note: "RL" is an abbreviation — rule-based will expand it
        self.assertEqual(result.original, "RL papers")

    def test_abbreviation_expansion_rule_based(self):
        """Rule-based rewriter expands common abbreviations."""
        rewriter = QueryRewriter(provider_factory=lambda: None)
        result = rewriter.rewrite("GNN")
        self.assertIn("graph neural network", result.rewritten.lower())
        self.assertTrue(result.was_rewritten)

    def test_short_query_not_rewritten_if_no_abbrev(self):
        """Full-term queries without abbreviations pass through unchanged."""
        rewriter = QueryRewriter(provider_factory=lambda: None)
        result = rewriter.rewrite("attention mechanism")
        self.assertEqual(result.original, "attention mechanism")
        self.assertFalse(result.was_rewritten)

    def test_llm_rewrite_used_when_available(self):
        """When LLM is available, uses it for rewriting."""
        mock_provider = MagicMock()
        mock_provider.chat.return_value = (
            '{"rewritten": "reinforcement learning reward shaping", '
            '"explanation": "Expanded RL to reinforcement learning and added related term", '
            '"expanded_terms": ["reinforcement learning", "reward shaping"]}'
        )
        rewriter = QueryRewriter(provider_factory=lambda: mock_provider)
        result = rewriter.rewrite("RL reward")
        self.assertEqual(result.rewritten, "reinforcement learning reward shaping")
        self.assertTrue(result.was_rewritten)
        self.assertIn("reinforcement learning", result.expanded_terms)

    def test_llm_failure_falls_back_to_rule(self):
        """If LLM raises, fall back to rule-based rewrite."""
        mock_provider = MagicMock()
        mock_provider.chat.side_effect = Exception("API error")
        rewriter = QueryRewriter(provider_factory=lambda: mock_provider)
        result = rewriter.rewrite("GNN")
        self.assertIn("graph neural network", result.rewritten.lower())

    def test_result_serializable(self):
        """RewriteResult should be easily serializable."""
        result = RewriteResult(
            original="test",
            rewritten="test query",
            was_rewritten=True,
            explanation="Added query",
            expanded_terms=["query"],
        )
        d = asdict(result)
        self.assertEqual(d["original"], "test")
        self.assertTrue(d["was_rewritten"])


class TestAbbreviationExpansion(unittest.TestCase):
    def test_common_ml_abbreviations(self):
        rewriter = QueryRewriter(provider_factory=lambda: None)

        cases = {
            "RL": "reinforcement learning",
            "NLP": "natural language processing",
            "CV": "computer vision",
            "GAN": "generative adversarial network",
            "LLM": "large language model",
            "CNN": "convolutional neural network",
            "RNN": "recurrent neural network",
            "VAE": "variational autoencoder",
        }
        for abbr, expansion in cases.items():
            result = rewriter.rewrite(abbr)
            self.assertIn(
                expansion,
                result.rewritten.lower(),
                f"Expected '{expansion}' in rewrite of '{abbr}', got '{result.rewritten}'",
            )
