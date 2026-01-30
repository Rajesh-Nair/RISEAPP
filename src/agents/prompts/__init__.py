"""Prompt management module for agents.

This module provides utilities for loading and managing prompts from separate files.
Prompts are stored as markdown files for easy editing and version control.
"""

from pathlib import Path
from typing import Dict, Optional
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from logger.custom_logger import CustomLogger
from exception.custom_exception import CustomException

logger = CustomLogger().get_logger(__file__)


class PromptLoader:
    """Utility class for loading and formatting prompts from files.
    
    Prompts are stored as markdown files in the prompts directory.
    Supports template variables using Python string formatting.
    """
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        """Initialize PromptLoader.
        
        Args:
            prompts_dir: Directory containing prompt files. 
                        Defaults to src/prompts relative to this file.
        """
        if prompts_dir is None:
            prompts_dir = Path(__file__).resolve().parent
        
        self.prompts_dir = Path(prompts_dir)
        self._cache: Dict[str, str] = {}
        
        if not self.prompts_dir.exists():
            raise CustomException(f"Prompts directory not found: {self.prompts_dir}")
    
    def load_prompt(self, filename: str, use_cache: bool = True) -> str:
        """Load a prompt from a file.
        
        Args:
            filename: Name of the prompt file (e.g., "lineage_detect_system.md")
            use_cache: Whether to use cached version if available
            
        Returns:
            str: Prompt content as string
            
        Raises:
            CustomException: If prompt file not found or cannot be read
        """
        # Check cache first
        if use_cache and filename in self._cache:
            return self._cache[filename]
        
        # Construct file path
        prompt_path = self.prompts_dir / filename
        
        if not prompt_path.exists():
            raise CustomException(
                f"Prompt file not found: {prompt_path}. "
                f"Available files: {list(self.prompts_dir.glob('*.md'))}"
            )
        
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Cache the content
            if use_cache:
                self._cache[filename] = content
            
            logger.debug(f"Loaded prompt from {filename}")
            return content
        except Exception as e:
            raise CustomException(f"Failed to load prompt from {filename}: {e}")
    
    def format_prompt(self, filename: str, **kwargs) -> str:
        """Load and format a prompt template with variables.
        
        Args:
            filename: Name of the prompt file
            **kwargs: Variables to substitute in the prompt template
            
        Returns:
            str: Formatted prompt string
            
        Example:
            prompt = loader.format_prompt(
                "lineage_detect_match.md",
                internal_chunk="...",
                candidates_block="..."
            )
        """
        template = self.load_prompt(filename)
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise CustomException(
                f"Missing template variable in {filename}: {e}. "
                f"Provided variables: {list(kwargs.keys())}"
            )
        except Exception as e:
            raise CustomException(f"Failed to format prompt {filename}: {e}")
    
    def clear_cache(self):
        """Clear the prompt cache."""
        self._cache.clear()
        logger.debug("Prompt cache cleared")


# Global prompt loader instance
_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """Get or create the global prompt loader instance.
    
    Returns:
        PromptLoader: Global prompt loader instance
    """
    global _loader
    if _loader is None:
        _loader = PromptLoader()
    return _loader


def load_prompt(filename: str) -> str:
    """Convenience function to load a prompt file.
    
    Args:
        filename: Name of the prompt file
        
    Returns:
        str: Prompt content
    """
    return get_prompt_loader().load_prompt(filename)


def format_prompt(filename: str, **kwargs) -> str:
    """Convenience function to load and format a prompt template.
    
    Args:
        filename: Name of the prompt file
        **kwargs: Variables to substitute in the template
        
    Returns:
        str: Formatted prompt
    """
    return get_prompt_loader().format_prompt(filename, **kwargs)
