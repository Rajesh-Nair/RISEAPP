# Prompts Directory

This directory contains all prompts used by the agents in a centralized, easy-to-edit format.

## Structure

Each prompt is stored as a separate markdown (`.md`) file for:
- Easy editing without touching code
- Version control tracking of prompt changes
- Clear separation of concerns
- Better maintainability

## Files

### Brand Classifier Agent
- **`brand_classifier_system.md`** - System instruction for the Brand Classifier Agent
- **`brand_classifier_classify.md`** - Template for classification prompts (uses variables: `{text}`, `{categories_str}`)

### Validation Agent
- **`validation_system.md`** - System instruction for the Validation Agent
- **`validation_validate.md`** - Template for validation prompts (uses variables: `{original_text}`, `{brand_name}`, `{nature_of_business}`, `{category_description}`)

## Usage

Prompts are loaded using the `PromptLoader` class from `src.prompts`:

```python
from src.prompts import get_prompt_loader

# Load a static prompt
loader = get_prompt_loader()
system_instruction = loader.load_prompt("brand_classifier_system.md")

# Load and format a template prompt
prompt = loader.format_prompt(
    "brand_classifier_classify.md",
    text="Shopping at AMAZON",
    categories_str="- ID 1: Retail Shopping"
)
```

## Template Variables

When editing template prompts (files with `_classify.md` or `_validate.md` suffix):
- Use single braces `{variable_name}` for template variables that will be replaced
- Use double braces `{{` and `}}` for literal braces in JSON examples

## Best Practices

1. **Keep prompts focused** - Each file should contain one complete prompt
2. **Use descriptive names** - File names should clearly indicate the agent and purpose
3. **Document variables** - Include comments or documentation about required template variables
4. **Test changes** - After editing prompts, test the agents to ensure they work correctly
5. **Version control** - Commit prompt changes separately from code changes for better tracking
