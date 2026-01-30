# Prompts

Markdown prompts for the **lineage detection** agent. Editable separately from code.

## Files

- **`lineage_detect_system.md`** – System instruction: role, task (internal → external chunk matching), output format.
- **`lineage_detect_match.md`** – Template for each match run. Variables: `{internal_chunk}`, `{candidates_block}`.

## Usage

```python
from src.agents.prompts import get_prompt_loader

loader = get_prompt_loader()
system = loader.load_prompt("lineage_detect_system.md")
prompt = loader.format_prompt(
    "lineage_detect_match.md",
    internal_chunk="...",
    candidates_block="...",
)
```

## Template variables

Use `{name}` in templates; pass `name=value` to `format_prompt`. Use `{{` and `}}` for literal braces in JSON examples.
