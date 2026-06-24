"""Compact writing prompt router for genre- and task-specific prose guidance."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WritingRule:
    key: str
    label: str
    keywords: tuple[str, ...]
    body: str


GENRE_RULES: tuple[WritingRule, ...] = (
    WritingRule(
        key="xianxia",
        label="仙侠/玄幻",
        keywords=("仙侠", "玄幻", "修仙", "宗门", "灵气", "境界", "功法", "法宝", "妖兽", "天道", "飞升"),
        body=(
            "- 设定只在行动中露出：境界、功法、法宝、规则必须影响选择、代价或胜负。\n"
            "- 战斗不要只报招式名；写目标、破绽、地形、消耗、反制和代价。\n"
            "- 升级/突破要有前置压力和具体限制，避免突然开挂碾压。"
        ),
    ),
    WritingRule(
        key="urban",
        label="都市/现实",
        keywords=("都市", "职场", "现实", "商战", "豪门", "娱乐圈", "校园", "家庭", "生活"),
        body=(
            "- 爽点来自现实压力下的反差：身份、资源、关系、证据、舆论或利益交换。\n"
            "- 细节落在可感知的生活动作和场景物件上，不要把人物写成概念标签。\n"
            "- 冲突要有现实后果：钱、名声、工作、亲密关系、法律或社交代价。"
        ),
    ),
    WritingRule(
        key="romance",
        label="情感/言情",
        keywords=("言情", "甜宠", "虐恋", "追妻", "爱情", "恋爱", "告白", "心动", "婚恋", "霸总", "双向"),
        body=(
            "- 情感推进靠行为和选择，不靠空泛心动、误会解释或作者替人物下结论。\n"
            "- 拉扯要有双方目标和底线；甜要具体，虐要有因果，不能只堆情绪词。\n"
            "- 对话保留潜台词：人物常常说一半、躲一半，让动作补足真实意图。"
        ),
    ),
    WritingRule(
        key="revenge",
        label="重生/复仇/打脸",
        keywords=("重生", "复仇", "打脸", "逆袭", "退婚", "背叛", "前世", "信息差", "报复", "翻盘"),
        body=(
            "- 核心爽点是信息差和布局：先埋证据、筹码或误判，再释放结果。\n"
            "- 反派不能无脑送；让对手有合理优势，主角胜在准备、取舍和节奏。\n"
            "- 每次反击解决一个层级的问题，同时露出更大的压力或新隐患。"
        ),
    ),
    WritingRule(
        key="suspense",
        label="悬疑/规则/惊悚",
        keywords=("悬疑", "推理", "规则怪谈", "惊悚", "恐怖", "诡异", "无限流", "副本", "线索", "谜案"),
        body=(
            "- 恐惧来自未知边界和错误选择的代价，不靠血腥形容堆砌。\n"
            "- 线索要可回收：本章至少给出一个可见细节、一个误导或一个规则边界。\n"
            "- 信息释放要分层，人物先根据不完整信息行动，再承担后果。"
        ),
    ),
    WritingRule(
        key="historical",
        label="历史/架空/古言",
        keywords=("历史", "架空", "古代", "朝堂", "宫廷", "权谋", "科举", "种田", "王朝", "侯府"),
        body=(
            "- 场景细节受时代制度约束：礼法、官阶、物价、交通、家族和身份边界。\n"
            "- 避免现代口吻和现代价值直接套入；让人物用当时可理解的方式争取利益。\n"
            "- 权谋冲突要写筹码交换、消息来源和公开/私下两层后果。"
        ),
    ),
    WritingRule(
        key="comedy",
        label="轻松/搞笑",
        keywords=("搞笑", "轻松", "沙雕", "吐槽", "喜剧", "反差", "日常流"),
        body=(
            "- 笑点来自规则内的反差和误判，不要脱离人物性格硬塞段子。\n"
            "- 包袱之后要推动情节或关系变化，不能只停在吐槽。\n"
            "- 节奏用短句和反应链：铺垫、偏差、停顿、反应，避免解释笑点。"
        ),
    ),
    WritingRule(
        key="scifi_apocalypse",
        label="科幻/末世",
        keywords=("科幻", "星际", "机甲", "末世", "灾变", "异能", "废土", "AI", "外星", "实验"),
        body=(
            "- 规则要可验证：技术、资源、异能或灾变机制必须影响行动方案。\n"
            "- 紧张感来自资源限制、时间压力和系统性风险，不只来自怪物出现。\n"
            "- 少解释大设定，多写角色如何利用、误判或付出代价。"
        ),
    ),
)


TASK_RULES: tuple[WritingRule, ...] = (
    WritingRule(
        key="opening",
        label="开篇/黄金章",
        keywords=("开篇", "开头", "第一章", "第1章", "黄金三章", "破题", "开场"),
        body=(
            "- 开头直接切进异常、选择、冲突或不可逆变化，禁止先交代世界观。\n"
            "- 前三百字给出人物处境、眼前压力和一个具体钩子。\n"
            "- 背景信息只给读者理解当前动作所必需的一小块。"
        ),
    ),
    WritingRule(
        key="continue",
        label="续写",
        keywords=("续写", "继续", "接着", "下一段", "下一章", "往下写", "承接"),
        body=(
            "- 从上文最后一个动作、问题或情绪继续，不重述已发生内容。\n"
            "- 本段至少推进一个新变化：发现、决定、冲突升级、关系变化或代价落地。\n"
            "- 保持人物当下状态连续，不能重置情绪、位置和信息掌握程度。"
        ),
    ),
    WritingRule(
        key="rewrite",
        label="改写/润色",
        keywords=("改写", "重写", "润色", "修改", "优化", "降AI", "去AI", "重塑"),
        body=(
            "- 保留事实、视角、人物目的和事件顺序，只优化表达、节奏和细节密度。\n"
            "- 删除解释性、总结性、标签化句子，换成动作、对话和可观察细节。\n"
            "- 不新增原文没有的重大剧情、角色关系或设定。"
        ),
    ),
    WritingRule(
        key="expand",
        label="扩写/细化",
        keywords=("扩写", "细化", "加长", "补细节", "丰富", "展开", "铺开"),
        body=(
            "- 扩写不是灌水；每个新增细节必须承担信息、情绪、冲突或节奏功能。\n"
            "- 优先补动作反应链、环境对行动的阻力、人物的小选择和后果。\n"
            "- 不要集中插入长段背景，新增内容要嵌进原有句群之间。"
        ),
    ),
    WritingRule(
        key="dialogue",
        label="对话/争执",
        keywords=("对话", "台词", "争吵", "交锋", "谈判", "对白", "质问", "试探"),
        body=(
            "- 每个人说话要服务自己的目标，不能为了讲设定而发言。\n"
            "- 用停顿、回避、反问、动作和话题转移写潜台词。\n"
            "- 区分角色声音：词汇、句长、礼貌程度、攻击方式和沉默习惯。"
        ),
    ),
    WritingRule(
        key="action",
        label="动作/战斗/高潮",
        keywords=("打斗", "战斗", "追逐", "逃亡", "高潮", "决战", "冲突", "搏杀", "危机"),
        body=(
            "- 每轮动作都要改变局势：位置、伤势、筹码、信息或心理优势。\n"
            "- 写清角色目标和限制，不要只堆招式、速度和形容词。\n"
            "- 高潮要有反转或代价，胜利不能像流程结算。"
        ),
    ),
    WritingRule(
        key="emotion",
        label="情绪/关系",
        keywords=("情绪", "情感", "心动", "告白", "崩溃", "虐", "甜", "和解", "决裂", "关系"),
        body=(
            "- 情绪先通过身体反应、动作迟疑、话语选择和决定呈现，再让读者理解。\n"
            "- 关系变化要落在具体行为上：靠近、退让、隐瞒、坦白、保护或放弃。\n"
            "- 避免直接写很悲伤、很感动、很紧张，用可见反应替代标签。"
        ),
    ),
    WritingRule(
        key="transition",
        label="过渡/铺垫",
        keywords=("过渡", "铺垫", "日常", "缓一缓", "间章", "准备", "调查"),
        body=(
            "- 过渡场也要有功能：补线索、变关系、立目标、埋隐患或展示代价。\n"
            "- 日常不要静态聊天，给人物一个正在做的事，让信息从行动里冒出来。\n"
            "- 结尾要把读者推向下一场，而不是自然散场。"
        ),
    ),
    WritingRule(
        key="ending_hook",
        label="章末钩子",
        keywords=("结尾", "章末", "悬念", "钩子", "收尾", "断章", "卡点"),
        body=(
            "- 章末收在新信息、选择压力、反转、危险逼近或关系变脸上。\n"
            "- 不要用总结感想收尾；让最后一句改变读者对当前局势的判断。\n"
            "- 钩子要和本章因果相关，不能凭空扔无关爆点。"
        ),
    ),
)


DEFAULT_WRITING_RULE = WritingRule(
    key="chapter_body",
    label="章节正文",
    keywords=(),
    body=(
        "- 直接交付可发布正文，不写大纲、分析、说明或章节标题。\n"
        "- 每个场景都要推进剧情、加深人物、释放信息或制造压力，避免纯装饰描写。\n"
        "- 用动作、对白、选择和后果承载情绪，不用作者总结替代戏剧过程。"
    ),
)


def _coerce_tags(tags: Any) -> list[str]:
    if not tags:
        return []
    if isinstance(tags, list):
        return [str(tag).strip() for tag in tags if str(tag).strip()]
    if isinstance(tags, str):
        raw = tags.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except Exception:
            return [part.strip() for part in raw.replace("，", ",").split(",") if part.strip()]
        if isinstance(parsed, list):
            return [str(tag).strip() for tag in parsed if str(tag).strip()]
        return [raw]
    return [str(tags).strip()]


def _score_rule(rule: WritingRule, text: str, tags: list[str]) -> int:
    score = 0
    for keyword in rule.keywords:
        if any(keyword == tag or keyword in tag for tag in tags):
            score += 3
        if keyword.lower() in text:
            score += 1
    return score


def _select_rules(
    rules: tuple[WritingRule, ...],
    *,
    text: str,
    tags: list[str],
    limit: int,
) -> list[WritingRule]:
    scored = [
        (score, index, rule)
        for index, rule in enumerate(rules)
        if (score := _score_rule(rule, text, tags)) > 0
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [rule for _, _, rule in scored[:limit]]


def detect_writing_genres(
    *,
    project_title: str = "",
    project_description: str = "",
    project_tags: Any = None,
    world_context: str = "",
    requirements: str = "",
) -> list[str]:
    tags = _coerce_tags(project_tags)
    text = "\n".join([project_title, project_description, " ".join(tags), world_context[:2000], requirements]).lower()
    return [rule.key for rule in _select_rules(GENRE_RULES, text=text, tags=tags, limit=2)]


def detect_writing_tasks(
    *,
    requirements: str = "",
    outline_context: str = "",
    source_text: str = "",
    plot_design: Any = None,
    roleplay_results: Any = None,
) -> list[str]:
    text = "\n".join([
        requirements,
        outline_context[:2000],
        source_text[:1200],
        str(plot_design or "")[:1200],
        str(roleplay_results or "")[:1200],
    ]).lower()
    return [rule.key for rule in _select_rules(TASK_RULES, text=text, tags=[], limit=3)]


def build_writing_directives(
    *,
    project_title: str = "",
    project_description: str = "",
    project_tags: Any = None,
    outline_context: str = "",
    world_context: str = "",
    requirements: str = "",
    source_text: str = "",
    plot_design: Any = None,
    roleplay_results: Any = None,
) -> str:
    """Return a compact system-prompt section for this writing call."""
    tags = _coerce_tags(project_tags)
    genre_text = "\n".join([
        project_title,
        project_description,
        " ".join(tags),
        world_context[:2000],
        requirements,
    ]).lower()
    task_text = "\n".join([
        requirements,
        outline_context[:2000],
        source_text[:1200],
        str(plot_design or "")[:1200],
        str(roleplay_results or "")[:1200],
    ]).lower()
    genre_rules = _select_rules(GENRE_RULES, text=genre_text, tags=tags, limit=2)
    task_rules = _select_rules(TASK_RULES, text=task_text, tags=[], limit=3)

    if not genre_rules and not task_rules:
        task_rules = [DEFAULT_WRITING_RULE]

    lines = ["【本次写作专项提示】"]
    if genre_rules:
        lines.append("类型路由：" + "、".join(rule.label for rule in genre_rules))
        for rule in genre_rules:
            lines.append(f"【{rule.label}写法】\n{rule.body}")
    if task_rules:
        lines.append("任务路由：" + "、".join(rule.label for rule in task_rules))
        for rule in task_rules:
            lines.append(f"【{rule.label}写法】\n{rule.body}")
    lines.append("以上规则只用于生成正文；不要复述规则、不要输出分析、不要改变既定事实。")
    return "\n".join(lines)
