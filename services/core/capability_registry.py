"""
Capability Registry

Semantic capability matching for planner.

Features:
- Keyword-based capability matching
- Skill-based capability lookup
- Usage tracking for learning
"""

import json
import re
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal

from logging_config import get_logger

logger = get_logger(__name__)


class CapabilityRegistry:
    """
    Registry for semantic capability matching.
    
    Maps goals → capabilities → pipelines → skills
    """
    
    # Default capability definitions
    DEFAULT_CAPABILITIES = {
        "cap_research_topic": {
            "display_name": "Research Topic",
            "description": "Research a topic on the web and compile findings",
            "keywords": ["research", "find information", "investigate", "analyze market", "competitor analysis", "survey"],
            "skills": ["core.web_research", "core.summarize_text", "core.write_file"],
        },
        "cap_generate_report": {
            "display_name": "Generate Report", 
            "description": "Generate a structured report from data",
            "keywords": ["report", "summarize", "compile", "document", "write up"],
            "skills": ["core.summarize_text", "core.write_file"],
        },
        "cap_analyze_data": {
            "display_name": "Analyze Data",
            "description": "Analyze and extract insights from data",
            "keywords": ["analyze", "extract", "insights", "statistics", "metrics"],
            "skills": ["core.analyze_text", "core.summarize_text"],
        },
        "cap_execute_command": {
            "display_name": "Execute Command",
            "description": "Execute system commands",
            "keywords": ["run", "execute", "command", "bash", "shell"],
            "skills": ["core.run_command"],
        },
        "cap_manage_files": {
            "display_name": "Manage Files",
            "description": "Read, write, list, and search files",
            "keywords": ["file", "write", "read", "list", "search", "directory"],
            "skills": ["core.file_read", "core.write_file", "core.file_list", "core.file_search", "core.create_directory"],
        },
        "cap_simple_task": {
            "display_name": "Simple Task",
            "description": "Simple echo task for testing",
            "keywords": ["test", "echo", "hello", "simple"],
            "skills": ["core.echo"],
        },
    }
    
    async def initialize(self) -> None:
        """Initialize with default capabilities."""
        async with AsyncSessionLocal() as session:
            for cap_id, config in self.DEFAULT_CAPABILITIES.items():
                await session.execute(
                    text("""
                        INSERT INTO capability_registry (
                            capability_id, display_name, description, keywords, skills, lifecycle_state, created_at
                        ) VALUES (
                            :cap_id, :display_name, :description, :keywords, :skills, 'active', NOW()
                        )
                        ON CONFLICT (capability_id) DO NOTHING
                    """),
                    {
                        "cap_id": cap_id,
                        "display_name": config["display_name"],
                        "description": config["description"],
                        "keywords": json.dumps(config["keywords"]),
                        "skills": json.dumps(config["skills"]),
                    }
                )
            await session.commit()
            logger.info("capability_registry_initialized", count=len(self.DEFAULT_CAPABILITIES))

    async def match_capability(self, goal_text: str) -> Optional[dict]:
        """
        Match goal text to best capability using keyword matching.
        
        Returns capability with highest keyword overlap.
        """
        goal_lower = goal_text.lower()
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        capability_id,
                        display_name,
                        description,
                        keywords,
                        skills,
                        usage_count
                    FROM capability_registry
                    WHERE lifecycle_state = 'active'
                """)
            )
            rows = result.fetchall()
            
            best_match = None
            best_score = 0
            
            for row in rows:
                cap_id, display_name, description, keywords, skills, usage_count = row
                
                if not keywords:
                    continue
                
                keywords_list = keywords if isinstance(keywords, list) else []
                
                # Count keyword matches
                matches = sum(1 for kw in keywords_list if kw.lower() in goal_lower)
                
                # Boost by usage count (prefers proven capabilities)
                score = matches + (usage_count * 0.1)
                
                if score > best_score:
                    best_score = score
                    best_match = {
                        "capability_id": cap_id,
                        "display_name": display_name,
                        "description": description,
                        "skills": skills,
                        "match_score": matches,
                    }
            
            if best_match:
                # Increment usage
                await session.execute(
                    text("""
                        UPDATE capability_registry 
                        SET usage_count = usage_count + 1, updated_at = NOW()
                        WHERE capability_id = :cap_id
                    """),
                    {"cap_id": best_match["capability_id"]}
                )
                await session.commit()
                
                logger.info(
                    "capability_matched",
                    capability=best_match["capability_id"],
                    score=best_match["match_score"]
                )
            
            return best_match

    async def get_capability(self, capability_id: str) -> Optional[dict]:
        """Get capability by ID."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT capability_id, display_name, description, keywords, skills
                    FROM capability_registry
                    WHERE capability_id = :cap_id
                """),
                {"cap_id": capability_id}
            )
            row = result.fetchone()
            
            if not row:
                return None
            
            return {
                "capability_id": row[0],
                "display_name": row[1],
                "description": row[2],
                "keywords": row[3],
                "skills": row[4],
            }

    async def get_all_capabilities(self) -> list[dict]:
        """Get all active capabilities."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT capability_id, display_name, description, keywords, skills, usage_count
                    FROM capability_registry
                    WHERE lifecycle_state = 'active'
                    ORDER BY usage_count DESC
                """)
            )
            rows = result.fetchall()
            
            return [
                {
                    "capability_id": r[0],
                    "display_name": r[1],
                    "description": r[2],
                    "keywords": r[3],
                    "skills": r[4],
                    "usage_count": r[5],
                }
                for r in rows
            ]


# Singleton
capability_registry = CapabilityRegistry()


async def initialize_registry():
    """Initialize the capability registry."""
    await capability_registry.initialize()


async def match_goal_to_capability(goal_text: str) -> Optional[dict]:
    """Match a goal to capability."""
    return await capability_registry.match_capability(goal_text)


if __name__ == "__main__":
    import asyncio
    
    async def demo():
        # Initialize
        await capability_registry.initialize()
        
        # Test matching
        test_goals = [
            "Research AI trends and summarize findings",
            "Analyze competitor pricing data",
            "Generate quarterly report",
            "Run system check",
            "Simple test task",
        ]
        
        print("🎯 Capability Matching Demo\n")
        
        for goal in test_goals:
            result = await capability_registry.match_capability(goal)
            if result:
                print(f"Goal: {goal}")
                print(f"  → Capability: {result['display_name']}")
                print(f"  → Skills: {result['skills']}")
                print()
    
    asyncio.run(demo())
