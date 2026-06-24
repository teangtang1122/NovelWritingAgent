"""Chapter Quality pack — full writing rules for chapter body generation."""
from __future__ import annotations

from ..anti_ai_prompts import build_anti_ai_system_prompt
from ..chapter_prompts import CHAPTER_ENDING_HOOK_TYPES, CHAPTER_OPENING_HOOKS, LITERARY_TECHNIQUES
from ..craft_prompts import build_craft_system_prompt
from ..dialogue_prompts import build_dialogue_system_prompt
from ..paragraph_hooks_prompts import build_paragraph_hooks_system_prompt
from . import PromptPack


def _build_scoped_system(*, style_context: str, writing_directives: str) -> str:
    return (
        "你是一位资深中文商业小说写手。你的任务是根据项目上下文直接生成可发布的章节正文，不写大纲、分析、解释或标题。\n\n"
        f"{writing_directives.strip()}\n\n"
        "【硬性输出】\n"
        "- 只输出正文文本；不要前言、后记、解释、评分、Markdown 或章节标题。\n"
        "- 段落用空行分隔；默认写 1800-2500 字，除非用户或工具参数另有要求。\n"
        "- 严格遵守既定大纲、人物状态、世界观规则、前文事实和叙事视角。\n\n"
        "【正文写法】\n"
        "- 开场直接切入人物正在面对的动作、问题、对话或异常，不用背景介绍开头。\n"
        "- 每一段至少承担一种功能：推进剧情、制造压力、揭示人物、释放信息或设置钩子。\n"
        "- 用角色的具体动作、感官、对白和选择表现情绪；少用抽象心理标签。\n"
        "- 对话要有目的和潜台词，角色声音要能区分；不要让角色替作者讲设定。\n"
        "- 场景描写只写当前视角能感知且会影响行动/气氛/判断的细节。\n"
        "- 高潮段要有局势变化、反转或代价；章末至少留下一个悬念、选择、发现或关系变化。\n\n"
        "【去AI味硬约束】\n"
        "- 禁止元评论和总结腔：不要写“这一切都说明”“值得注意的是”“命运的齿轮”。\n"
        "- 禁止空泛修辞堆叠：不要连续比喻、成语堆砌、排比灌水或装饰性感官描写。\n"
        "- 禁止高频虚词模板：仿佛、似乎、彰显、诠释、映射、油然而生、心潮澎湃等能删则删。\n"
        "- 不要跳进非视角角色内心；不知道的事不要替读者上帝视角交代。\n\n"
        f"【风格设定】\n{style_context}"
    )


def _build_system(*, style_context: str, writing_directives: str = "") -> str:
    """Build the full chapter writer system prompt.

    This is the verbatim logic from ``chapter_writer_prompts.build_chapter_writer_messages()``,
    extracted into a pack callable.
    """
    if writing_directives.strip():
        return _build_scoped_system(
            style_context=style_context,
            writing_directives=writing_directives,
        )

    craft_rules = build_craft_system_prompt()
    dialogue_rules = build_dialogue_system_prompt()
    anti_ai_rules = build_anti_ai_system_prompt()
    hooks_rules = build_paragraph_hooks_system_prompt()

    return (
        "你是一位资深小说写手，专精于将剧情设计和对白素材织成流畅、有感染力的章节正文。\n\n"
        "【任务】\n"
        "根据提供的剧情设计、角色对白素材和项目上下文，写出完整的章节正文。你不是在写大纲或摘要——你是直接交付可发布的正文。\n\n"
        "【写作原则】\n"
        "1. 剧情设计是你的骨架——其中指定的场景、冲突、情绪走向必须被遵守，但具体的措辞和描写由你决定。\n"
        "2. 角色扮演的对白是你的血肉——将对话自然地织入叙事中，用动作和细节连接对话段落。\n"
        "3. 叙事视角和文风严格遵循【风格设定】。\n"
        "4. 正文控制在 1800-2500 字。不长不短。\n"
        "5. 短句、动作描写、感官细节优先。不要写元评论、水词、抽象抒情。\n\n"
        "【章节结构】\n"
        "- 开头：用章首引子切入——悬念对白、中断动作、倒计时、或意象伏笔。禁止以背景交代或环境描写开头。\n"
        "- 中段：场景之间用蒙太奇切换，不需要过渡句。短句快切制造紧张，细节感官制造舒缓。每章至少 2 个紧张峰值。\n"
        "- 结尾：必须使用至少 1 种章末悬念钩子收束，禁止平淡过渡结尾。\n\n"
        "【输出格式】\n"
        "只输出章节正文本身。不要加任何前言、后记、解释或元评论。不要加章节标题（标题由系统自动添加）。\n"
        "不要使用 Markdown 格式。段落用空行分隔。\n\n"
        f"{craft_rules}\n\n"
        f"{dialogue_rules}\n\n"
        f"{anti_ai_rules}\n\n"
        f"{hooks_rules}\n\n"
        "【章首引子类型】\n"
        f"{CHAPTER_OPENING_HOOKS}\n\n"
        "【章末钩子类型】\n"
        f"{CHAPTER_ENDING_HOOK_TYPES}\n\n"
        "【文学技法】\n"
        f"{LITERARY_TECHNIQUES}\n\n"
        f"【风格设定】\n{style_context}"
    )


PACK = PromptPack(
    name="chapter_quality",
    version="1.0",
    pack_type="chapter",
    description="Quality chapter writer — full craft rules, dialogue, hooks, literary techniques",
    input_fields=[
        "style_context", "outline_context", "world_context",
        "character_profiles", "recent_summaries",
        "plot_design", "roleplay_results", "requirements", "writing_directives",
    ],
    max_token_budget=12000,
    output_format="prose",
    output_schema=None,
    available_tools=[],
    unavailable_tools=[],
    forbidden_behaviors=[
        "禁止添加前言、后记、解释或元评论",
        "禁止添加章节标题",
        "禁止使用 Markdown 格式",
        "正文必须控制在 1800-2500 字",
    ],
    default_temperature=0.8,
    default_max_tokens=6000,
    context_budget={"style": 2000, "outline": 3000, "world": 2000, "characters": 2000, "summaries": 1500},
    tool_policy="none",
    build_system_prompt=_build_system,
)
