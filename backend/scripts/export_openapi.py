"""Print the OpenAPI schema as UTF-8 JSON (used by the frontend's gen:types)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.schemas.meetings import MeetingContextIn  # noqa: E402

schema = create_app(Settings(_env_file=None)).openapi()

# MeetingContextIn is sent as a JSON string form field, so FastAPI omits it
# from OpenAPI. Add it so the frontend can derive its type from the generated file.
schemas = schema.setdefault("components", {}).setdefault("schemas", {})
ctx = MeetingContextIn.model_json_schema(
    ref_template="#/components/schemas/{model}", mode="validation"
)
for name, definition in ctx.pop("$defs", {}).items():
    schemas.setdefault(name, definition)
# Defaults are optional on input; drop them so the generated TS type marks them optional.
for prop in ctx.get("properties", {}).values():
    prop.pop("default", None)
schemas["MeetingContextIn"] = ctx

sys.stdout.buffer.write(json.dumps(schema, ensure_ascii=False, indent=2).encode("utf-8"))
sys.stdout.buffer.write(b"\n")
