"""
AUTO-REGISTRATION OF ALL CANONICAL SKILLS
==========================================

This script is imported on system startup to register all canonical skills.

Skills are registered in the skill_registry and become available for goal execution.

Updated: 2026-03-09 - Added 10 text processing skills
"""
from logging_config import get_logger

logger = get_logger(__name__)


def register_all_canonical_skills():
    """
    Register all canonical skills in the skill registry.

    This function is called during system startup.
    """
    from canonical_skills.registry import skill_registry

    # Core skills
    from canonical_skills.echo import EchoSkill
    from canonical_skills.write_file import WriteFileSkill

    # Text processing skills
    from canonical_skills.text_tokenize import TextTokenizeSkill
    from canonical_skills.text_count_words import TextCountWordsSkill
    from canonical_skills.text_extract_keywords import TextExtractKeywordsSkill
    from canonical_skills.text_regex_extract import TextRegexExtractSkill
    from canonical_skills.text_parse_json import TextParseJsonSkill
    from canonical_skills.text_parse_csv import TextParseCsvSkill
    from canonical_skills.text_format import TextFormatSkill
    from canonical_skills.text_clean import TextCleanSkill
    from canonical_skills.text_split import TextSplitSkill
    from canonical_skills.text_merge import TextMergeSkill

    # Register core skills
    skill_registry.register(EchoSkill())
    skill_registry.register(WriteFileSkill())

    # Register text processing skills (NEW v1.1)
    skill_registry.register(TextTokenizeSkill())
    skill_registry.register(TextCountWordsSkill())
    skill_registry.register(TextExtractKeywordsSkill())
    skill_registry.register(TextRegexExtractSkill())
    skill_registry.register(TextParseJsonSkill())
    skill_registry.register(TextParseCsvSkill())
    skill_registry.register(TextFormatSkill())
    skill_registry.register(TextCleanSkill())
    skill_registry.register(TextSplitSkill())
    skill_registry.register(TextMergeSkill())

    logger.info(
        "canonical_skills_registered",
        total_skills=len(skill_registry.list()),
        new_skills=10
    )


# Auto-register on import
register_all_canonical_skills()
