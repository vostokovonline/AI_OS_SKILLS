"""
Capability Graph Planner - AI-OS

Instead of pattern matching, this system PLANS execution using capability dependencies.

Architecture:
Goal → Capabilities → Graph Expansion → Ordered Plan → Skill Binding → Execution

Pattern = cached successful plan (optional accelerator)
Graph = source of truth for planning
"""
from typing import List, Dict, Any, Optional
from logging_config import get_logger
from semantic.embedding_service import embed_text, cosine_similarity
from semantic.capability_inference import infer_capabilities

logger = get_logger(__name__)


# Capability Graph with dependencies
# Each capability can require other capabilities to be executed first
CAP_GRAPH: Dict[str, Dict[str, Any]] = {
    "information_retrieval": {
        "requires": [],
        "provides": ["information_retrieval"],
        "description": "Finding and collecting information"
    },
    "summarization": {
        "requires": ["information_retrieval"],
        "provides": ["summarization"],
        "description": "Condensing information"
    },
    "analysis": {
        "requires": ["information_retrieval"],
        "provides": ["analysis"],
        "description": "Breaking down information"
    },
    "code_generation": {
        "requires": [],
        "provides": ["code_generation"],
        "description": "Writing code"
    },
    "code_execution": {
        "requires": ["code_generation"],
        "provides": ["code_execution"],
        "description": "Running code"
    },
    "writing": {
        "requires": [],
        "provides": ["writing"],
        "description": "Creating written content"
    },
    "data_processing": {
        "requires": [],
        "provides": ["data_processing"],
        "description": "Manipulating data"
    },
    "decision_making": {
        "requires": ["analysis"],
        "provides": ["decision_making"],
        "description": "Making choices"
    },
}


# Capability → Skill mapping
CAPABILITY_TO_SKILLS: Dict[str, List[str]] = {
    "information_retrieval": ["core.web_research", "core.file_search"],
    "summarization": ["core.summarize_text", "core.text_merge"],
    "analysis": ["core.analyze_text", "core.text_extract_keywords"],
    "code_generation": ["core.write_file", "core.create_directory"],
    "code_execution": ["core.run_command"],
    "writing": ["core.write_file"],
    "data_processing": ["core.text_parse_csv", "core.text_parse_json", "core.text_regex_extract"],
    "decision_making": ["core.echo"],  # Placeholder
}


class CapabilityGraphPlanner:
    """
    Plans execution using capability dependencies.
    
    Key insight:
    - Pattern = cached successful plan (optional)
    - Graph = source of truth for planning
    
    This enables TRUE generalization - system doesn't match, it PLANS.
    """
    
    def __init__(self):
        self._skill_registry = None
    
    def set_skill_registry(self, registry):
        """Set skill registry for skill binding."""
        self._skill_registry = registry
    
    def plan(self, goal_title: str, goal_description: str = "") -> Dict[str, Any]:
        """
        Create execution plan from goal.
        
        Args:
            goal_title: Goal title
            goal_description: Goal description
            
        Returns:
            Dict with:
            - capabilities: inferred capabilities
            - primary: primary capabilities
            - secondary: secondary capabilities
            - plan: ordered list of capabilities
            - skills: bound skills
            - confidence: planning confidence
        """
        # Step 1: Infer capabilities
        capabilities = infer_capabilities(goal_title, goal_description)
        
        if not capabilities:
            logger.info("no_capabilities_inferred", goal=goal_title[:50])
            return {"capabilities": [], "plan": [], "skills": [], "confidence": 0.0}
        
        # Step 2: Classify capabilities
        primary = [c for c in capabilities if c["confidence"] >= 0.6]
        secondary = [c for c in capabilities if 0.3 <= c["confidence"] < 0.6]
        
        logger.info(
            "capabilities_inferred",
            goal=goal_title[:50],
            primary=[c["name"] for c in primary],
            secondary=[c["name"] for c in secondary]
        )
        
        # Step 3: Expand to ordered plan using graph dependencies
        all_caps = primary + secondary
        ordered_plan = self._expand_capabilities(all_caps)
        
        # Step 4: Bind skills to capabilities
        skills = self._bind_skills(ordered_plan)
        
        # Step 5: Calculate confidence
        confidence = self._calculate_confidence(primary, secondary, skills)
        
        return {
            "capabilities": [c["name"] for c in capabilities],
            "primary": [c["name"] for c in primary],
            "secondary": [c["name"] for c in secondary],
            "plan": ordered_plan,
            "skills": skills,
            "confidence": confidence
        }
    
    def _expand_capabilities(self, capabilities: List[Dict[str, Any]]) -> List[str]:
        """
        Expand capabilities using graph dependencies.
        
        Uses topological sort to ensure dependencies come before dependents.
        
        Example:
            Input: ["summarization"]
            Output: ["information_retrieval", "summarization"]
        
        Args:
            capabilities: List of {name, confidence} dicts
            
        Returns:
            Ordered list of capability names
        """
        # Get all required capabilities
        all_caps = set()
        
        for cap in capabilities:
            cap_name = cap["name"]
            all_caps.add(cap_name)
            
            # Add required dependencies recursively
            self._add_dependencies(cap_name, all_caps)
        
        # Topological sort
        ordered = self._topological_sort(list(all_caps))
        
        logger.info("plan_expanded", capabilities=list(all_caps), ordered=ordered)
        
        return ordered
    
    def _add_dependencies(self, cap_name: str, result: set):
        """Recursively add dependencies."""
        if cap_name not in CAP_GRAPH:
            return
        
        requires = CAP_GRAPH.get(cap_name, {}).get("requires", [])
        for req in requires:
            result.add(req)
            self._add_dependencies(req, result)
    
    def _topological_sort(self, capabilities: List[str]) -> List[str]:
        """
        Sort capabilities topologically based on dependencies.
        
        Args:
            capabilities: List of capability names
            
        Returns:
            Topologically sorted list
        """
        # Build dependency map
        deps = {cap: set() for cap in capabilities}
        dependents = {cap: set() for cap in capabilities}
        
        for cap in capabilities:
            if cap in CAP_GRAPH:
                required = CAP_GRAPH[cap].get("requires", [])
                for req in required:
                    if req in capabilities:
                        deps[cap].add(req)
                        dependents[req].add(cap)
        
        # Kahn's algorithm
        result = []
        queue = [cap for cap in capabilities if not deps[cap]]
        
        while queue:
            cap = queue.pop(0)
            result.append(cap)
            
            for dep in dependents[cap]:
                deps[dep].remove(cap)
                if not deps[dep]:
                    queue.append(dep)
        
        # Handle cycles (shouldn't happen in well-formed graph)
        if len(result) < len(capabilities):
            remaining = [c for c in capabilities if c not in result]
            result.extend(remaining)
        
        return result
    
    def _bind_skills(self, ordered_plan: List[str]) -> List[str]:
        """
        Bind skills to capabilities in order.
        
        Each capability maps to one or more skills.
        
        Args:
            ordered_plan: Ordered list of capability names
            
        Returns:
            Ordered list of skill IDs
        """
        skills = []
        seen_skills = set()
        
        for cap in ordered_plan:
            if cap in CAPABILITY_TO_SKILLS:
                for skill_id in CAPABILITY_TO_SKILLS[cap]:
                    if skill_id not in seen_skills:
                        skills.append(skill_id)
                        seen_skills.add(skill_id)
        
        logger.info("skills_bound", plan=ordered_plan, skills=skills)
        
        return skills
    
    def _calculate_confidence(
        self, 
        primary: List[Dict], 
        secondary: List[Dict],
        skills: List[str]
    ) -> float:
        """
        Calculate confidence in the plan.
        
        Factors:
        - Has primary capabilities: +0.3
        - Has secondary capabilities: +0.2
        - Has skills for all capabilities: +0.3
        - Quality of skill mapping: +0.2
        """
        if not primary and not secondary:
            return 0.0
        
        score = 0.0
        
        if primary:
            score += 0.3
        
        if secondary:
            score += 0.2
        
        # Check if we have skills for all capabilities
        all_caps = set(c["name"] for c in primary) | set(c["name"] for c in secondary)
        covered_caps = set()
        for cap in all_caps:
            if cap in CAPABILITY_TO_SKILLS:
                covered_caps.add(cap)
        
        coverage = len(covered_caps) / len(all_caps) if all_caps else 0
        score += coverage * 0.3
        
        # Skill quality
        if skills:
            score += 0.2
        
        return min(score, 1.0)


# Global instance
capability_planner = CapabilityGraphPlanner()
