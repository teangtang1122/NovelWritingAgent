"""Small runtime schema upgrades for the local SQLite-first app."""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_runtime_schema(engine: Engine) -> None:
    """Apply additive schema upgrades that create_all cannot apply to existing DBs."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        if inspector.has_table("api_configs"):
            columns = {column["name"] for column in inspector.get_columns("api_configs")}
            additions = {
                "max_output_tokens": "INTEGER",
                "deconstruct_input_char_limit": "INTEGER",
                "deconstruct_item_char_limit": "INTEGER",
            }
            for name, column_type in additions.items():
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE api_configs ADD COLUMN {name} {column_type}"))

        if inspector.has_table("assistant_conversations"):
            columns = {column["name"] for column in inspector.get_columns("assistant_conversations")}
            if "scope" not in columns:
                conn.execute(text("ALTER TABLE assistant_conversations ADD COLUMN scope VARCHAR(50) NOT NULL DEFAULT 'writer'"))

        if inspector.has_table("projects"):
            columns = {column["name"] for column in inspector.get_columns("projects")}
            additions = {
                "forbidden_sentence_patterns": "TEXT",
                "rhetoric_guidelines": "TEXT",
            }
            for name, column_type in additions.items():
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE projects ADD COLUMN {name} {column_type}"))
