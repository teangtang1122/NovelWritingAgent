"""Single source of truth for prompt content.

This module provides functions to extract prompt content from the canonical
source files. Both internal assistant and external agent prompt packs read
from here — edit these files to change behavior everywhere.
"""
from __future__ import annotations


def get_forbidden_patterns() -> list[str]:
    """Get the complete forbidden patterns list from anti_ai_prompts.py."""
    from .anti_ai_prompts import (
        TIER1_BANNED_WORDS,
        TIER2_THRESHOLD_WORDS,
        CHAPTER_END_BAN_PATTERNS,
    )

    patterns: list[str] = []
    # Tier 1 words
    for category_words in TIER1_BANNED_WORDS.values():
        patterns.extend(category_words)
    # Tier 2 threshold words
    patterns.extend(TIER2_THRESHOLD_WORDS)
    # Chapter end patterns
    patterns.extend(CHAPTER_END_BAN_PATTERNS)
    return list(dict.fromkeys(patterns))  # dedupe, preserve order


def get_quality_rubric() -> dict:
    """Get the quality rubric for chapter evaluation."""
    return {
        "dimensions": [
            {"name": "opening_hook", "description": "开头吸引力：第一段是否能抓住读者", "max_score": 10},
            {"name": "plot_progression", "description": "情节推进：剧情是否有实质进展", "max_score": 10},
            {"name": "character_portrayal", "description": "角色塑造：角色是否立体、有记忆点", "max_score": 10},
            {"name": "dialogue_quality", "description": "对话质量：对话是否自然、有信息量", "max_score": 10},
            {"name": "suspense", "description": "悬念设置：是否有足够的钩子", "max_score": 10},
            {"name": "pacing", "description": "节奏控制：快慢是否得当", "max_score": 10},
            {"name": "show_dont_tell", "description": "展示性描写：是否用展示而非叙述", "max_score": 10},
            {"name": "language_quality", "description": "语言质量：文笔是否流畅", "max_score": 10},
        ],
        "passing_score": 60,
        "max_score": 80,
    }


def get_chapter_writing_rules() -> str:
    """Get the core chapter writing rules as a single text block."""
    return (
        "【正文要求】1800-2500字。开头要吸引人，章末要留钩子。展示而非叙述，短句优先。\n\n"
        "【剧情设计】写作前先设计：场景、冲突、情绪曲线、转折点、结尾钩子。\n"
        "【角色对话】每个角色说话要符合性格，对话要有信息量，推动剧情或揭示性格。"
    )
