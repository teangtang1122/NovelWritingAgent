"""Tests for MCP resource URI scheme — parsing and construction."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.mcp.resources import parse_uri, build_uri, ParsedUri, list_resource_uris, get_resource_description


class ParseUriTest(unittest.TestCase):
    """Verify moshu:// URI parsing."""

    def test_projects_index(self):
        r = parse_uri("moshu://projects")
        self.assertIsNotNone(r)
        self.assertEqual(r.resource_type, "projects_index")
        self.assertEqual(r.project_id, "")
        self.assertEqual(r.entity_id, "")

    def test_project_detail(self):
        r = parse_uri("moshu://projects/abc123")
        self.assertIsNotNone(r)
        self.assertEqual(r.resource_type, "project_detail")
        self.assertEqual(r.project_id, "abc123")

    def test_chapters_index(self):
        r = parse_uri("moshu://projects/p1/chapters")
        self.assertIsNotNone(r)
        self.assertEqual(r.resource_type, "chapters_index")
        self.assertEqual(r.project_id, "p1")

    def test_chapter_detail(self):
        r = parse_uri("moshu://projects/p1/chapters/ch99")
        self.assertIsNotNone(r)
        self.assertEqual(r.resource_type, "chapter_detail")
        self.assertEqual(r.project_id, "p1")
        self.assertEqual(r.entity_id, "ch99")

    def test_characters_index(self):
        r = parse_uri("moshu://projects/p1/characters")
        self.assertIsNotNone(r)
        self.assertEqual(r.resource_type, "characters_index")

    def test_character_detail(self):
        r = parse_uri("moshu://projects/p1/characters/c42")
        self.assertIsNotNone(r)
        self.assertEqual(r.resource_type, "character_detail")
        self.assertEqual(r.entity_id, "c42")

    def test_worldbuilding_index(self):
        r = parse_uri("moshu://projects/p1/worldbuilding")
        self.assertIsNotNone(r)
        self.assertEqual(r.resource_type, "worldbuilding_index")

    def test_worldbuilding_detail(self):
        r = parse_uri("moshu://projects/p1/worldbuilding/wb7")
        self.assertIsNotNone(r)
        self.assertEqual(r.resource_type, "worldbuilding_detail")
        self.assertEqual(r.entity_id, "wb7")

    def test_outline_index(self):
        r = parse_uri("moshu://projects/p1/outline")
        self.assertIsNotNone(r)
        self.assertEqual(r.resource_type, "outline_index")

    def test_outline_detail(self):
        r = parse_uri("moshu://projects/p1/outline/n5")
        self.assertIsNotNone(r)
        self.assertEqual(r.resource_type, "outline_detail")
        self.assertEqual(r.entity_id, "n5")

    def test_relationships(self):
        r = parse_uri("moshu://projects/p1/relationships")
        self.assertIsNotNone(r)
        self.assertEqual(r.resource_type, "relationships")

    def test_invalid_scheme_returns_none(self):
        self.assertIsNone(parse_uri("http://projects"))
        self.assertIsNone(parse_uri("file:///tmp/test"))
        self.assertIsNone(parse_uri("moshu:"))

    def test_invalid_path_returns_none(self):
        self.assertIsNone(parse_uri("moshu://invalid"))
        self.assertIsNone(parse_uri("moshu://projects/p1/invalid"))
        self.assertIsNone(parse_uri("moshu://projects/p1/chapters/x/y/z"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_uri(""))

    def test_uuid_project_id(self):
        """UUID-style project IDs should parse correctly."""
        r = parse_uri("moshu://projects/550e8400-e29b-41d4-a716-446655440000/chapters")
        self.assertIsNotNone(r)
        self.assertEqual(r.project_id, "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(r.resource_type, "chapters_index")


class BuildUriTest(unittest.TestCase):
    """Verify moshu:// URI construction."""

    def test_projects(self):
        self.assertEqual(build_uri("projects"), "moshu://projects")

    def test_project_detail(self):
        self.assertEqual(build_uri("projects", "abc"), "moshu://projects/abc")

    def test_chapters(self):
        self.assertEqual(build_uri("projects", "p1", "chapters"), "moshu://projects/p1/chapters")

    def test_chapter_detail(self):
        self.assertEqual(
            build_uri("projects", "p1", "chapters", "ch1"),
            "moshu://projects/p1/chapters/ch1",
        )

    def test_roundtrip(self):
        """build_uri output should parse back to the same values."""
        uri = build_uri("projects", "myproj", "characters", "char42")
        r = parse_uri(uri)
        self.assertIsNotNone(r)
        self.assertEqual(r.project_id, "myproj")
        self.assertEqual(r.entity_id, "char42")
        self.assertEqual(r.resource_type, "character_detail")


class ListResourceUrisTest(unittest.TestCase):
    """Verify list_resource_uris returns expected URIs."""

    def test_returns_expected_count(self):
        uris = list_resource_uris("p1")
        self.assertEqual(len(uris), 7)

    def test_contains_projects_index(self):
        uris = list_resource_uris("p1")
        self.assertIn("moshu://projects", uris)

    def test_contains_project_detail(self):
        uris = list_resource_uris("p1")
        self.assertIn("moshu://projects/p1", uris)

    def test_contains_all_index_types(self):
        uris = list_resource_uris("p1")
        expected = [
            "moshu://projects/p1/chapters",
            "moshu://projects/p1/characters",
            "moshu://projects/p1/worldbuilding",
            "moshu://projects/p1/outline",
            "moshu://projects/p1/relationships",
        ]
        for e in expected:
            self.assertIn(e, uris)

    def test_all_uris_parse(self):
        """Every URI returned by list_resource_uris must parse successfully."""
        for uri in list_resource_uris("test-proj"):
            r = parse_uri(uri)
            self.assertIsNotNone(r, f"Failed to parse: {uri}")


class ResourceDescriptionTest(unittest.TestCase):
    """Verify resource descriptions exist for all types."""

    def test_all_types_have_descriptions(self):
        types = [
            "projects_index", "project_detail",
            "chapters_index", "chapter_detail",
            "characters_index", "character_detail",
            "worldbuilding_index", "worldbuilding_detail",
            "outline_index", "outline_detail",
            "relationships",
        ]
        for t in types:
            desc = get_resource_description(t)
            self.assertTrue(desc, f"Empty description for {t}")

    def test_unknown_type_returns_generic(self):
        desc = get_resource_description("unknown_type")
        self.assertIn("Moshu", desc)


if __name__ == "__main__":
    unittest.main()
