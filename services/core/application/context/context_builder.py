"""
Context OS - LLM Context Builder
==================================
Система построения контекста для LLM вызовов.
Включает RAG, Code Graph, и semantic memory.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum


class ContextSource(Enum):
    """Источники контекста"""
    SEMANTIC_MEMORY = "semantic_memory"
    CODE_GRAPH = "code_graph"
    GOAL_CONTEXT = "goal_context"
    EXECUTION_HISTORY = "execution_history"
    SKILL_REGISTRY = "skill_registry"
    PATTERNS = "patterns"
    USER_PREFERENCES = "user_preferences"


@dataclass
class ContextChunk:
    """Чанк контекста"""
    source: ContextSource
    content: str
    relevance_score: float  # 0-1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.value,
            "content": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "relevance_score": self.relevance_score,
            "metadata": self.metadata,
        }


@dataclass
class LLMContext:
    """
    Полный контекст для LLM вызова.
    """
    goal_id: Optional[str] = None
    goal_title: str = ""
    goal_type: str = ""
    task_description: str = ""
    
    # Контекстные чанки
    chunks: List[ContextChunk] = field(default_factory=list)
    
    # Метаданные
    created_at: datetime = field(default_factory=datetime.utcnow)
    token_count: int = 0
    
    # Настройки
    max_tokens: int = 120000  # Default context window
    include_history: bool = True
    include_patterns: bool = True
    
    def add_chunk(self, chunk: ContextChunk) -> None:
        self.chunks.append(chunk)
        self._recalculate_tokens()
    
    def _recalculate_tokens(self) -> None:
        """Примерный подсчет токенов"""
        total_chars = sum(len(c.content) for c in self.chunks)
        self.token_count = total_chars // 4  # Rough estimate
    
    def is_within_limit(self) -> bool:
        return self.token_count <= self.max_tokens
    
    def get_truncated(self, max_tokens: int) -> 'LLMContext':
        """Получить контекст урезанный до лимита"""
        truncated = LLMContext(
            goal_id=self.goal_id,
            goal_title=self.goal_title,
            goal_type=self.goal_type,
            task_description=self.task_description,
            max_tokens=max_tokens,
            include_history=self.include_history,
            include_patterns=self.include_patterns,
        )
        
        # Add chunks sorted by relevance
        sorted_chunks = sorted(self.chunks, key=lambda c: c.relevance_score, reverse=True)
        
        for chunk in sorted_chunks:
            if truncated.is_within_limit():
                truncated.add_chunk(chunk)
        
        return truncated
    
    def to_prompt_format(self) -> str:
        """Преобразовать в формат для промпта"""
        parts = []
        
        # Goal context
        if self.goal_title:
            parts.append(f"## Goal\n{self.goal_title}\n")
        
        if self.task_description:
            parts.append(f"## Task\n{self.task_description}\n")
        
        # Context chunks grouped by source
        by_source: Dict[ContextSource, List[ContextChunk]] = {}
        for chunk in self.chunks:
            if chunk.source not in by_source:
                by_source[chunk.source] = []
            by_source[chunk.source].append(chunk)
        
        for source, chunks in by_source.items():
            parts.append(f"\n## {source.value.replace('_', ' ').title()}\n")
            for chunk in chunks[:3]:  # Top 3 per source
                parts.append(f"- {chunk.content[:200]}...\n")
        
        return "".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "goal_title": self.goal_title,
            "goal_type": self.goal_type,
            "task_description": self.task_description,
            "chunks": [c.to_dict() for c in self.chunks],
            "token_count": self.token_count,
            "max_tokens": self.max_tokens,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ContextBuilderConfig:
    """Конфигурация для построителя контекста"""
    # Limits
    max_chunks: int = 20
    max_tokens: int = 120000
    
    # Sources
    include_semantic_memory: bool = True
    include_code_graph: bool = True
    include_goal_context: bool = True
    include_execution_history: bool = True
    include_skill_registry: bool = True
    include_patterns: bool = True
    
    # Relevance thresholds
    min_relevance_score: float = 0.3
    
    # RAG settings
    rag_top_k: int = 5


class ContextBuilder:
    """
    Построитель контекста для LLM.
    
    Pipeline:
    1. Get goal context (from database)
    2. RAG search (semantic memory)
    3. Code graph expansion (if coding task)
    4. Execution history (similar goals)
    5. Skill registry (available tools)
    6. Merge and rank by relevance
    7. Truncate to token limit
    """
    
    def __init__(self, config: Optional[ContextBuilderConfig] = None):
        self.config = config or ContextBuilderConfig()
    
    async def build(
        self,
        goal_id: str,
        task_description: str,
        goal_type: str = "",
        goal_title: str = ""
    ) -> LLMContext:
        """
        Построить контекст для LLM вызова.
        """
        context = LLMContext(
            goal_id=goal_id,
            goal_title=goal_title,
            goal_type=goal_type,
            task_description=task_description,
            max_tokens=self.config.max_tokens,
        )
        
        # Step 1: Goal context
        if self.config.include_goal_context:
            await self._add_goal_context(context, goal_id)
        
        # Step 2: RAG search
        if self.config.include_semantic_memory:
            await self._add_rag_context(context, task_description)
        
        # Step 3: Code graph
        if self.config.include_code_graph:
            await self._add_code_graph_context(context, task_description)
        
        # Step 4: Execution history
        if self.config.include_execution_history:
            await self._add_execution_history(context, goal_id, goal_type)
        
        # Step 5: Skill registry
        if self.config.include_skill_registry:
            await self._add_skill_registry(context)
        
        # Step 6: Patterns
        if self.config.include_patterns:
            await self._add_patterns(context, goal_type)
        
        # Step 7: Sort by relevance and truncate
        context.chunks.sort(key=lambda c: c.relevance_score, reverse=True)
        
        # Truncate if needed
        if not context.is_within_limit():
            context = context.get_truncated(self.config.max_tokens)
        
        return context
    
    async def _add_goal_context(self, context: LLMContext, goal_id: str) -> None:
        """Добавить контекст цели"""
        # This would fetch from database
        # For now, add placeholder
        pass
    
    async def _add_rag_context(self, context: LLMContext, task_description: str) -> None:
        """RAG search из semantic memory"""
        # Would call semantic memory service
        # For now, placeholder
        pass
    
    async def _add_code_graph_context(self, context: LLMContext, task_description: str) -> None:
        """Добавить контекст из code graph"""
        # Would call code graph service
        # For coding tasks, this is crucial
        if any(keyword in task_description.lower() for keyword in ["code", "function", "implement", "write"]):
            chunk = ContextChunk(
                source=ContextSource.CODE_GRAPH,
                content="Code graph context will be added here",
                relevance_score=0.8,
                metadata={"type": "code_context"}
            )
            context.add_chunk(chunk)
    
    async def _add_execution_history(self, context: LLMContext, goal_id: str, goal_type: str) -> None:
        """Добавить историю выполнения похожих целей"""
        # Would query execution traces
        pass
    
    async def _add_skill_registry(self, context: LLMContext) -> None:
        """Добавить доступные навыки"""
        chunk = ContextChunk(
            source=ContextSource.SKILL_REGISTRY,
            content="Available skills: write_file, web_research, ask_user, code_execution, data_extraction",
            relevance_score=0.5,
            metadata={"type": "skill_list"}
        )
        context.add_chunk(chunk)
    
    async def _add_patterns(self, context: LLMContext, goal_type: str) -> None:
        """Добавить паттерны для типа цели"""
        # Would query semantic memory for patterns
        pass
