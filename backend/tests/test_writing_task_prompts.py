from app.prompts.packs.chapter_quality import PACK as CHAPTER_PACK
from app.prompts.text_operations import build_continue_messages
from app.prompts.writing_task_prompts import (
    build_writing_directives,
    detect_writing_genres,
    detect_writing_tasks,
)


def test_writing_directives_route_xianxia_action_continue():
    directives = build_writing_directives(
        project_tags='["\u4ed9\u4fa0"]',
        requirements="\u7eed\u5199\u4e00\u573a\u5b97\u95e8\u6218\u6597\u9ad8\u6f6e",
    )

    assert "\u4ed9\u4fa0/\u7384\u5e7b" in directives
    assert "\u7eed\u5199" in directives
    assert "\u52a8\u4f5c/\u6218\u6597/\u9ad8\u6f6e" in directives


def test_detect_writing_genres_uses_project_tags_and_description():
    genres = detect_writing_genres(
        project_description="\u4e00\u90e8\u89c4\u5219\u602a\u8c08\u65e0\u9650\u6d41\u5c0f\u8bf4",
        project_tags=["\u60ac\u7591"],
    )

    assert "suspense" in genres


def test_detect_writing_tasks_uses_requirements():
    tasks = detect_writing_tasks(requirements="\u6539\u5199\u8fd9\u6bb5\u544a\u767d\u5bf9\u8bdd")

    assert "rewrite" in tasks
    assert "dialogue" in tasks


def test_chapter_pack_includes_writing_directives():
    directives = build_writing_directives(
        project_tags=["\u90fd\u5e02", "\u8a00\u60c5"],
        requirements="\u6539\u5199\u8fd9\u6bb5\u544a\u767d",
    )

    prompt = CHAPTER_PACK.build_system_prompt(
        style_context="\u81ea\u7136",
        writing_directives=directives,
    )

    assert "\u672c\u6b21\u5199\u4f5c\u4e13\u9879\u63d0\u793a" in prompt
    assert "\u90fd\u5e02/\u73b0\u5b9e" in prompt
    assert "\u6539\u5199/\u6da6\u8272" in prompt


def test_continue_messages_include_writing_directives():
    directives = build_writing_directives(
        project_tags=["\u4ed9\u4fa0"],
        requirements="\u7eed\u5199",
        source_text="\u4ed6\u63e1\u7d27\u5251\uff0c\u671b\u5411\u5c71\u95e8\u5916\u7684\u706b\u5149\u3002",
    )

    messages = build_continue_messages(
        style_context="\u81ea\u7136",
        outline_context="\u7b2c\u4e09\u7ae0\uff1a\u5b97\u95e8\u5371\u673a",
        summaries="\u524d\u6587\u6458\u8981",
        prompt="\u7eed\u5199",
        text="\u4ed6\u63e1\u7d27\u5251\uff0c\u671b\u5411\u5c71\u95e8\u5916\u7684\u706b\u5149\u3002",
        writing_directives=directives,
    )

    assert "\u672c\u6b21\u5199\u4f5c\u4e13\u9879\u63d0\u793a" in messages[0]["content"]
    assert "\u4ed9\u4fa0/\u7384\u5e7b" in messages[0]["content"]
