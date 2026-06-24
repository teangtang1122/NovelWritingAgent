from app.prompts.packs.workspace_quality import PACK
from app.services.agent.prompt_builder import build_system_prompt
from app.services.workspace.tool_schemas import (
    build_workspace_tool_schemas,
    select_workspace_tool_names,
)


def test_cataloging_request_selects_cataloging_tools():
    names = select_workspace_tool_names(
        scope="project",
        message="\u7ed9\u8fd9\u672c\u4e66\u5efa\u6863",
    )

    assert "start_cataloging_job" in names
    assert "apply_pending_cataloging" in names
    assert "delete_project" not in names

    schema_names = {
        schema["function"]["name"]
        for schema in build_workspace_tool_schemas(names)
    }
    assert schema_names == set(names)


def test_scoped_workspace_prompt_does_not_append_full_tool_policy():
    names = select_workspace_tool_names(
        scope="project",
        message="\u5e2e\u6211\u770b\u770b\u8fd9\u4e2a\u9879\u76ee",
    )

    prompt = build_system_prompt(
        PACK,
        scope="project",
        outline_batch_count=3,
        auto_apply=True,
        tool_names=names,
    )

    assert "\u3010\u672c\u8f6e\u53ef\u7528\u5de5\u5177\u3011" in prompt
    assert "get_project_info" in prompt
    assert "delete_project" not in prompt


def test_selected_text_adds_local_text_tools():
    names = select_workspace_tool_names(
        scope="project",
        message="\u6539\u5199\u8fd9\u6bb5",
        selected_text=True,
    )

    assert "rewrite_text" in names
    assert "expand_text" in names
    assert "continue_text" in names
