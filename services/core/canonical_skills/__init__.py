"""
CANONICAL SKILLS PACKAGE
Canonical Skills for AI_OS

UPDATED 2026-03-09: Added 10 text processing skills
"""
from canonical_skills.base import Skill, SkillResult, Artifact
from canonical_skills.registry import skill_registry

# Core skills
from canonical_skills.echo import EchoSkill
from canonical_skills.write_file import WriteFileSkill

# Text processing skills (NEW v1.1)
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

__all__ = [
    "Skill",
    "SkillResult",
    "Artifact",
    "skill_registry",
    # Core
    "EchoSkill",
    "WriteFileSkill",
    # Text Processing
    "TextTokenizeSkill",
    "TextCountWordsSkill",
    "TextExtractKeywordsSkill",
    "TextRegexExtractSkill",
    "TextParseJsonSkill",
    "TextParseCsvSkill",
    "TextFormatSkill",
    "TextCleanSkill",
    "TextSplitSkill",
    "TextMergeSkill"
]
