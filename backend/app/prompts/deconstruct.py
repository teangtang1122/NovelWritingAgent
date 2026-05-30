"""Prompt templates for deconstruct / book analysis map-reduce pipeline."""

# ── Map phase ────────────────────────────────────────────────────────

MAP_OUTPUT_RULES = (
    "\n\n【JSON输出硬性规范】\n"
    "1. 只输出 minified JSON：不要换行排版，不要 Markdown，不要解释文字。\n"
    "2. 输出必须以 { 开头，以 } 结束，最后一个字符必须是右花括号。\n"
    "3. 顶层字段必须完整，字段名必须使用模板中的英文名，不得新增中文字段名。\n"
    "4. 这是读法分析事实卡片，不是最终档案。只记录剧情节点、节奏、模式、高光和必要角色名。\n"
    "5. 数量上限：characters最多8个，events最多9个，clues最多5个，themes最多6个，techniques最多6个。\n"
    "6. 长度上限：events.summary/clues.detail 每项最多100个中文字符，role_hint最多40个中文字符，themes/techniques每项最多12个中文字符。\n"
    "7. 如果内容太多，优先保留主线事件、冲突转折、伏笔线索、节奏变化和写作手法。\n"
    "8. 整个JSON输出必须紧凑完整，不得在字符串或数组中间截断。宁可少写几条也要保证JSON完整闭合。\n"
)

MAP_SYSTEM_PROMPT = (
    "你是一位小说拆书流水线中的分块事实提取器。你的任务不是写最终报告，而是从当前文本片段中提取短小、准确、可合并的事实卡片。\n"
    "后续会基于这些事实卡片生成读法分析、节奏曲线、情节高光和写作模式总结，所以你必须保持输出短、准、结构稳定。\n\n"
    "【核心要求】\n"
    "1. 必须只输出一个合法JSON对象——不要输出Markdown代码块、解释文字、前缀或后缀。\n"
    "2. 角色名必须使用原文姓名；事件必须写清谁做了什么、造成什么结果。\n"
    "3. characters 只保留必要角色姓名、身份提示和提及次数，不写外貌、关系网、背景故事或角色档案。\n"
    "4. 只提取事实，不扩写、不评价、不生成最终档案。没有信息时使用空数组 [] 或空字符串 ''，但不得省略顶层字段。\n"
    "5. JSON必须可被 json.loads 直接解析，不得包含尾随逗号、注释或非标准语法。\n"
    "6. 宁可输出空数组或少写几条，也必须保证JSON以 } 完整闭合。截断的JSON会导致整段作废。\n\n"
    "【禁止事项】\n"
    "- 禁止用「主角」「父亲」「老人」「少女」等代称代替角色姓名——必须从原文中提取实际姓名。\n"
    "- 禁止使用「神秘力量」「性格复杂」「实力强大」等空洞描述——必须具体说明是什么力量、什么性格特征、如何强大。\n"
    "- 禁止输出 character_profiles、outline_hints、worldbuilding_entries、world_facts、golden_three_signals 等档案/导入字段。\n"
    "- 禁止在 JSON 外输出任何内容。"
)

MAP_JSON_TEMPLATE = (
    '{"characters":[{"name":"","role_hint":"","mentions":0}],'
    '"events":[{"summary":"","type":"intro|conflict|reveal|turn|climax|resolution|setup|other","characters":[""],"importance":"high|medium|low"}],'
    '"clues":[{"item":"","detail":""}],'
    '"pacing":"slow|medium|fast|intense",'
    '"narrative_mode":"description|dialogue|action|reflection|exposition|mixed",'
    '"themes":[""],"techniques":[""]}'
)

JSON_REPAIR_SYSTEM_PROMPT = (
    "你是JSON修复器，只修复语法，不重新分析文本，不增删事实。"
    "输入是模型输出的近似JSON，可能有中文引号、漏引号、尾随逗号、截断字段或Markdown。"
    "你必须只返回一个可被 json.loads 解析的合法JSON对象。"
)


def map_instructions(options: dict) -> str:
    """Build map-phase instruction text for chunk analysis."""
    parts = [
        "【分块事实卡片要求】",
        "1. characters 只记录角色名、身份提示和提及次数，目的是帮助判断事件参与者，不生成角色档案。",
        "2. events 只记录主线事件事实：summary 写谁做了什么以及结果，不确定的信息不要猜。",
        "3. clues 记录伏笔、线索、未解谜团或后续可能回收的信息。",
        "4. themes 每条不超过8字；techniques 只写本段明确出现的写作手法。",
        "5. pacing 判断：slow=描写/思考为主；medium=事件推进与描写交替；fast=连续事件/对话驱动；intense=高潮战斗/重大揭示。",
        "6. 这是给合并模型看的读法分析原料，宁可短而准，不要长而散。",
    ]
    return "\n".join(parts)


# ── Reduce phase ─────────────────────────────────────────────────────

REDUCE_SYSTEM_PROMPT = (
    "你是一位资深网文编辑与拆书整合专家，专精于将分散的文本分析结果合成为一份完整、连贯的读法分析报告。\n"
    "你的工作不是重新分析原文，也不是生成可导入档案，而是将各分块的剧情节点、节奏、高光、伏笔和写作手法去重、排序、归纳成有机整体。\n\n"
    "【整合原则】\n"
    "1. 情节节点：根据分块 events/clues/themes 提炼关键节点，按故事位置排序，保留转折、揭示、高潮和收束。\n"
    "2. 高光提炼：只提炼读者能感受到的爽点、情绪点、揭示点、动作高潮，不写成大纲章节。\n"
    "3. 节奏归纳：综合 pacing 与事件密度，形成节奏曲线和关键变化标签。\n"
    "4. 写作模式：综合 techniques/themes，总结反复出现的技巧、主题和结构特征。\n"
    "5. 字段补全：如果某个字段在所有分块中都为空，保留空数组，但不省略字段。\n\n"
    "【禁止事项】\n"
    "- 禁止输出角色档案、完整大纲结构、世界观条目或任何可导入资产。\n"
    "- 禁止输出与分块分析结果矛盾的信息——你的工作是整合而非编造。\n"
    "- 禁止将分块结果直接拼接而不做去重——如果同一事件在不同分块中被描述，必须合并或选择最优表述。\n"
    "- 禁止在 JSON 外输出任何内容。\n\n"
    "【质量判断】\n"
    "- 好的整合报告：能帮助作者理解作品如何推进、何处有爽点/爆点、节奏如何变化、反复使用了哪些写法。\n"
    "- 失败的整合报告：复述剧情流水账，或偷偷生成角色卡、大纲、世界观等建档内容。"
)


def reduce_template(options: dict) -> str:
    """Build the reduce-phase JSON output template based on enabled modules."""
    optional_fields = []
    if options.get("golden_three"):
        optional_fields.append(
            '  "golden_three": {"hook":"","protagonist_goal":"","core_conflict":"","reader_expectation":"","chapter_1_function":"","chapter_2_function":"","chapter_3_function":"","problems":[""],"optimization_suggestions":[""]},'
        )
    optional_fields.append('  "structure": {"volumes": [],"total_estimated_chapters":0},')
    optional_fields.append(
        '  "plot_nodes": [{"description":"","type":"intro|development|turn|climax|resolution","position_pct":0,"importance":"high|medium|low"}],'
    )
    optional_fields.append('  "characters": [],')
    optional_fields.append('  "worldbuilding_entries": [],')
    optional_fields.append(
        '  "highlights": [{"type":"climax|reveal|emotional|action","description":"","position_pct":0,"intensity":"low|medium|high"}],'
    )
    optional_fields.append(
        '  "rhythm_curve": [{"position_pct":0,"pace":"slow|medium|fast|intense","label":""}],'
        if options.get("rhythm") else '  "rhythm_curve": [],'
    )
    optional_fields.append(
        '  "patterns": [{"type":"technique|theme|structure","description":"","frequency":"rare|moderate|frequent","examples":[""]}]'
        if options.get("patterns")
        else '  "patterns": []'
    )
    return "{\n" + "\n".join(optional_fields) + "\n}"


def reduce_instructions(options: dict) -> str:
    """Build reduce-phase integration instructions based on enabled modules."""
    instructions = [
        "【整合规则】",
        "1. 输入是分块读法事实卡片，不是最终档案。你要基于 characters/events/clues/themes/techniques/pacing 生成情节节点、高光、节奏和写作模式。",
        "2. 不生成角色档案、大纲结构或世界观条目；对应字段只能输出空数组或空对象。",
        "3. 伏笔和高光：从 clues 与 events 中提炼 plot_nodes/highlights，保留重要揭示、转折、高潮和后续钩子。",
        "4. 节奏曲线（rhythm_curve）：综合各分块 pacing，标注舒缓、推进、高潮、转折位置。",
        "5. 写作模式（patterns）：综合 techniques/themes，总结反复出现的写法、主题和结构特点。",
    ]
    if options.get("golden_three"):
        instructions.append(
            "\n【黄金三章模块】\n"
            "6. 黄金三章只能依据提示中单独提供的「前三章原文摘录」分析，不能用全书后文倒推开篇：\n"
            "- 评价开篇钩子的有效性。\n"
            "- 明确主角初始目标和核心冲突。\n"
            "- 分析前三章各自承担的功能和衔接效果。\n"
            "- 指出开篇存在的问题（如节奏拖沓、信息量过大、主角被动等）并给出优化建议。"
        )
    return "\n".join(instructions)


# ── Reduce per-section templates ─────────────────────────────────────

REDUCE_SECTION_TEMPLATES = {
    "plot_highlights": (
        '{"plot_nodes":[{"description":"","type":"intro|development|turn|climax|resolution","position_pct":0,"importance":"high|medium|low"}],'
        '"highlights":[{"type":"climax|reveal|emotional|action","description":"","position_pct":0,"intensity":"low|medium|high"}]}'
    ),
    "rhythm_patterns": (
        '{"rhythm_curve":[{"position_pct":0,"pace":"slow|medium|fast|intense","label":""}],'
        '"patterns":[{"type":"technique|theme|structure","description":"","frequency":"rare|moderate|frequent","examples":[""]}]}'
    ),
    "golden_three": (
        '{"golden_three":{"hook":"","protagonist_goal":"","core_conflict":"","reader_expectation":"","chapter_1_function":"","chapter_2_function":"","chapter_3_function":"","problems":[""],"optimization_suggestions":[""]}}'
    ),
}

REDUCE_SECTION_INSTRUCTIONS = {
    "plot_highlights": "只生成情节节点时序和爽点/爆点分布。不要输出 structure、characters、worldbuilding_entries。节点是读法分析节点，不是可导入大纲。",
    "rhythm_patterns": "只生成节奏曲线和写作模式。综合 pacing/themes/techniques，不要输出角色或大纲。",
    "golden_three": "只分析黄金三章。只能依据前三章原文摘录，不能用后文倒推开篇。",
}

REDUCE_SECTION_LABELS = {
    "plot_highlights": "情节与高光",
    "rhythm_patterns": "节奏与模式",
    "golden_three": "黄金三章",
}
