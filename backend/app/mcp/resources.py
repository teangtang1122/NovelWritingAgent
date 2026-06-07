"""MCP resource URI scheme for Moshu.

Defines the moshu:// URI scheme, parsing, and resource types.
All Moshu resources use a stable, hierarchical URI format.

URI patterns:
    moshu://projects
    moshu://projects/{project_id}
    moshu://projects/{project_id}/chapters
    moshu://projects/{project_id}/chapters/{chapter_id}
    moshu://projects/{project_id}/characters
    moshu://projects/{project_id}/characters/{character_id}
    moshu://projects/{project_id}/worldbuilding
    moshu://projects/{project_id}/worldbuilding/{entry_id}
    moshu://projects/{project_id}/outline
    moshu://projects/{project_id}/outline/{node_id}
    moshu://projects/{project_id}/relationships
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# ── Resource URI patterns ────────────────────────────────────────────────

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^moshu://projects$"), "projects_index"),
    (re.compile(r"^moshu://projects/([^/]+)$"), "project_detail"),
    (re.compile(r"^moshu://projects/([^/]+)/chapters$"), "chapters_index"),
    (re.compile(r"^moshu://projects/([^/]+)/chapters/([^/]+)$"), "chapter_detail"),
    (re.compile(r"^moshu://projects/([^/]+)/characters$"), "characters_index"),
    (re.compile(r"^moshu://projects/([^/]+)/characters/([^/]+)$"), "character_detail"),
    (re.compile(r"^moshu://projects/([^/]+)/worldbuilding$"), "worldbuilding_index"),
    (re.compile(r"^moshu://projects/([^/]+)/worldbuilding/([^/]+)$"), "worldbuilding_detail"),
    (re.compile(r"^moshu://projects/([^/]+)/outline$"), "outline_index"),
    (re.compile(r"^moshu://projects/([^/]+)/outline/([^/]+)$"), "outline_detail"),
    (re.compile(r"^moshu://projects/([^/]+)/relationships$"), "relationships"),
]


@dataclass(frozen=True)
class ParsedUri:
    """Result of parsing a moshu:// URI."""
    uri: str
    resource_type: str
    project_id: str = ""
    entity_id: str = ""


def parse_uri(uri: str) -> ParsedUri | None:
    """Parse a moshu:// URI into a ParsedUri, or None if invalid.

    Args:
        uri: A string like "moshu://projects/abc123/chapters"

    Returns:
        ParsedUri with resource_type and extracted IDs, or None if no match.
    """
    for pattern, resource_type in _PATTERNS:
        m = pattern.match(uri)
        if m:
            groups = m.groups()
            project_id = groups[0] if len(groups) >= 1 else ""
            entity_id = groups[1] if len(groups) >= 2 else ""
            return ParsedUri(
                uri=uri,
                resource_type=resource_type,
                project_id=project_id,
                entity_id=entity_id,
            )
    return None


def build_uri(*parts: str) -> str:
    """Build a moshu:// URI from path parts.

    Examples:
        build_uri("projects") -> "moshu://projects"
        build_uri("projects", "abc") -> "moshu://projects/abc"
        build_uri("projects", "abc", "chapters") -> "moshu://projects/abc/chapters"
    """
    return "moshu://" + "/".join(parts)


# ── Resource metadata ────────────────────────────────────────────────────

@dataclass
class ResourceMeta:
    """Metadata for an MCP resource."""
    uri: str
    name: str
    description: str
    mime_type: str = "application/json"


# Resource type descriptions for listings
_RESOURCE_DESCRIPTIONS: dict[str, str] = {
    "projects_index": "List of all projects",
    "project_detail": "Project metadata and settings",
    "chapters_index": "Chapter list for a project",
    "chapter_detail": "Chapter content and metadata",
    "characters_index": "Character list for a project",
    "character_detail": "Character card with full details",
    "worldbuilding_index": "Worldbuilding entry list",
    "worldbuilding_detail": "Worldbuilding entry content",
    "outline_index": "Outline tree structure",
    "outline_detail": "Outline node with summary",
    "relationships": "Character relationships",
}


def get_resource_description(resource_type: str) -> str:
    """Return a human-readable description for a resource type."""
    return _RESOURCE_DESCRIPTIONS.get(resource_type, "Moshu resource")


def list_resource_uris(project_id: str) -> list[str]:
    """List all resource URIs for a given project.

    Returns the index-level URIs. Entity-detail URIs require
    knowing the entity IDs and are constructed on demand.
    """
    return [
        "moshu://projects",
        build_uri("projects", project_id),
        build_uri("projects", project_id, "chapters"),
        build_uri("projects", project_id, "characters"),
        build_uri("projects", project_id, "worldbuilding"),
        build_uri("projects", project_id, "outline"),
        build_uri("projects", project_id, "relationships"),
    ]
