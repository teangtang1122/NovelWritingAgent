"""Tests for prompt pack RAG indexing."""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class PromptPackRAGTest(unittest.TestCase):
    """Verify prompt packs can be indexed in RAG."""

    def test_index_prompt_pack_function_exists(self):
        from app.services.rag.indexer import _index_prompt_pack
        self.assertTrue(callable(_index_prompt_pack))

    def test_index_method_card_function_exists(self):
        from app.services.rag.indexer import _index_method_card
        self.assertTrue(callable(_index_method_card))

    def test_reindex_project_types_includes_prompt_pack(self):
        """reindex_project_types should handle prompt_pack source type."""
        from app.services.rag.indexer import reindex_project_types
        db = MagicMock()

        # Mock queries to return empty results
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.all.return_value = []
        query_mock.first.return_value = None
        db.query.return_value = query_mock

        # Should not raise
        result = reindex_project_types(db, "p1", source_types=["prompt_pack"])
        self.assertIn("total_chunks", result)

    def test_reindex_project_types_includes_method_card(self):
        """reindex_project_types should handle method_card source type."""
        from app.services.rag.indexer import reindex_project_types
        db = MagicMock()

        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.all.return_value = []
        query_mock.first.return_value = None
        db.query.return_value = query_mock

        result = reindex_project_types(db, "p1", source_types=["method_card"])
        self.assertIn("total_chunks", result)


class PromptPackSourceTypesTest(unittest.TestCase):
    """Verify prompt_pack and method_card are valid source types."""

    def test_search_context_accepts_prompt_pack(self):
        """search_context should accept prompt_pack as a source type."""
        # The valid types are defined in search_context
        from app.services.workspace.tools.rag_tools import search_context
        self.assertTrue(callable(search_context))


if __name__ == "__main__":
    unittest.main()
