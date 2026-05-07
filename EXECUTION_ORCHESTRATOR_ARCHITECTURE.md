# Execution Orchestrator - Production Architecture
**Pattern from**: OpenAI, Anthropic, Google DeepMind
**Purpose**: Make AI system 10x more stable and reliable

---

## Current Problem (What's Broken)

### AI-OS Today (Unstable)
```
Goal → Skill Selection → Execution → ???
                              ↓
                         75% failure
                         skill_id = "unknown"
                         No learning
```

**Issues**:
1. No visibility into what's happening
2. No retry logic (fail → done)
3. No fallback strategies
4. No monitoring/observability
5. No circuit breakers
6. Single point of failure

---

## Execution Orchestrator Solution

### What is Execution Orchestrator?

**Definition**: A dedicated layer that manages ALL goal executions with:
- State management
- Retry logic
- Fallback strategies
- Monitoring
- Circuit breakers
- Observability

**Analogy**: Think of it like Kubernetes for AI agent executions

---

## Architecture

### High-Level View
```
┌─────────────────────────────────────────────────────────────┐
│                     Goal Executor V2                         │
│                  (Business Logic Layer)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               EXECUTION ORCHESTRATOR ⭐ NEW                │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   State      │  │   Retry      │  │  Fallback    │     │
│  │  Machine     │  │   Engine     │  │  Strategies  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Circuit     │  │  Monitor     │  │  Metrics     │     │
│  │  Breakers    │  │  & Tracing   │  │  & Logging   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     Skill Layer                             │
│  (core.echo, core.write_file, web_research, ...)           │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. State Machine
**Tracks execution state**: `pending → starting → executing → completing → done/failed`

```python
class ExecutionState(Enum):
    PENDING = "pending"           # Not started
    STARTING = "starting"         # Skill selection in progress
    EXECUTING = "executing"       # Running skill
    COMPLETING = "completing"     # Verification/evaluation
    DONE = "done"                 # Success
    FAILED = "failed"             # Execution failed
    RETRYING = "retrying"         # Will retry
    FALLBACK = "fallback"         # Using fallback strategy
```

### 2. Retry Engine
**Smart retry with exponential backoff**

```python
class RetryEngine:
    def __init__(self):
        self.max_attempts = 3
        self.backoff_base = 2  # seconds
        self.max_backoff = 60

    def should_retry(self, attempt: int, error: str) -> bool:
        """
        Determine if execution should be retried.

        Retry on:
        - Transient errors (timeout, connection)
        - LLM rate limits
        - Temporary resource exhaustion

        Don't retry on:
        - Validation errors
        - Permission denied
        - Invalid inputs
        """
        if attempt >= self.max_attempts:
            return False

        # Transient errors → retry
        if any(x in error.lower() for x in ['timeout', 'connection', 'rate limit']):
            return True

        # LLM errors → retry
        if any(x in error.lower() for x in ['llm', 'groq', 'ollama']):
            return True

        return False

    def get_backoff(self, attempt: int) -> int:
        """Exponential backoff with jitter"""
        backoff = min(
            self.backoff_base ** attempt,
            self.max_backoff
        )
        # Add jitter (±20%)
        import random
        jitter = int(backoff * 0.2 * (random.random() * 2 - 1))
        return backoff + jitter
```

### 3. Fallback Strategies
**When primary fails, try alternatives**

```python
class FallbackStrategy(ABC):
    @abstractmethod
    async def execute(self, goal: Goal) -> ExecutionResult:
        pass

class PrimaryStrategy(FallbackStrategy):
    """Use goal_executor_v2"""
    async def execute(self, goal: Goal) -> ExecutionResult:
        return await goal_executor_v2.execute_goal_with_uow(...)

class LegacyStrategy(FallbackStrategy):
    """Use old goal_executor (v1)"""
    async def execute(self, goal: Goal) -> ExecutionResult:
        return await goal_executor.execute(goal.goal_id)

class SafeModeStrategy(FallbackStrategy):
    """Use only safest skills (EchoSkill)"""
    async def execute(self, goal: Goal) -> ExecutionResult:
        # Force use EchoSkill
        return await execute_with_echo_skill(goal)

class FallbackChain:
    def __init__(self):
        self.strategies = [
            PrimaryStrategy(),
            LegacyStrategy(),
            SafeModeStrategy()
        ]

    async def execute_with_fallback(self, goal: Goal) -> ExecutionResult:
        """
        Try strategies in order until one succeeds.
        """
        last_error = None

        for i, strategy in enumerate(self.strategies):
            try:
                logger.info(
                    "fallback_attempt",
                    strategy=strategy.__class__.__name__,
                    attempt=i+1,
                    total=len(self.strategies)
                )

                result = await strategy.execute(goal)

                if result.success:
                    logger.info(
                        "fallback_success",
                        strategy=strategy.__class__.__name__,
                        attempts=i+1
                    )
                    return result

                last_error = result.error

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "fallback_failed",
                    strategy=strategy.__class__.__name__,
                    error=last_error
                )

        # All strategies failed
        return ExecutionResult(
            success=False,
            error=f"All fallbacks exhausted. Last error: {last_error}"
        )
```

### 4. Circuit Breakers
**Prevent cascade failures**

```python
class CircuitBreaker:
    """
    Circuit Breaker Pattern

    States:
    - CLOSED: Normal operation
    - OPEN: Failing, stop trying
    - HALF_OPEN: Testing if recovered
    """

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout  # seconds
        self.failures = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def record_failure(self):
        """Record a failure"""
        self.failures += 1
        self.last_failure_time = datetime.utcnow()

        if self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                "circuit_breaker_open",
                failures=self.failures,
                threshold=self.failure_threshold
            )

    def record_success(self):
        """Record a success"""
        self.failures = 0
        self.state = CircuitState.CLOSED

    def can_execute(self) -> bool:
        """Check if execution is allowed"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout passed
            if (datetime.utcnow() - self.last_failure_time).total_seconds() > self.timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("circuit_breaker_half_open")
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return False
```

### 5. Monitor & Tracing
**Full observability**

```python
class ExecutionMonitor:
    """
    Tracks all executions with detailed metrics.
    """

    def __init__(self):
        self.active_executions = {}
        self.metrics = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "retried": 0,
            "fallback": 0
        }

    async def start_execution(self, goal_id: str, execution_id: str):
        """Track execution start"""
        self.active_executions[execution_id] = {
            "goal_id": goal_id,
            "started_at": datetime.utcnow(),
            "state": ExecutionState.STARTING
        }

        logger.info(
            "execution_started",
            goal_id=goal_id,
            execution_id=execution_id
        )

    async def update_state(self, execution_id: str, state: ExecutionState):
        """Update execution state"""
        if execution_id in self.active_executions:
            self.active_executions[execution_id]["state"] = state
            self.active_executions[execution_id]["updated_at"] = datetime.utcnow()

    async def complete_execution(
        self,
        execution_id: str,
        success: bool,
        result: ExecutionResult
    ):
        """Track execution completion"""
        if execution_id not in self.active_executions:
            return

        execution = self.active_executions[execution_id]
        duration = (datetime.utcnow() - execution["started_at"]).total_seconds()

        # Update metrics
        self.metrics["total"] += 1
        if success:
            self.metrics["success"] += 1
        else:
            self.metrics["failed"] += 1

        # Log completion
        logger.info(
            "execution_completed",
            execution_id=execution_id,
            success=success,
            duration_s=duration,
            skill_used=result.get("skill_used"),
            artifacts_count=result.get("artifacts_produced", 0)
        )

        # Cleanup
        del self.active_executions[execution_id]

    def get_health_status(self) -> dict:
        """Get system health"""
        return {
            "active_executions": len(self.active_executions),
            "success_rate": (
                self.metrics["success"] / self.metrics["total"]
                if self.metrics["total"] > 0 else 0
            ),
            "metrics": self.metrics
        }
```

---

## Full Orchestrator Implementation

```python
class ExecutionOrchestrator:
    """
    Production-grade execution orchestrator.

    Features:
    - State management
    - Retry logic
    - Fallback strategies
    - Circuit breakers
    - Monitoring
    """

    def __init__(self):
        self.state_machine = ExecutionStateMachine()
        self.retry_engine = RetryEngine()
        self.fallback_chain = FallbackChain()
        self.circuit_breaker = CircuitBreaker()
        self.monitor = ExecutionMonitor()
        self.db_session = None

    async def execute_goal(
        self,
        goal_id: str,
        uow: UnitOfWork
    ) -> ExecutionResult:
        """
        Execute goal with full orchestration.

        This is the ONLY entry point for goal execution.
        """
        execution_id = str(uuid4())

        # Start monitoring
        await self.monitor.start_execution(goal_id, execution_id)

        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            logger.error("circuit_breaker_blocking", goal_id=goal_id)
            return ExecutionResult(
                success=False,
                error="Circuit breaker is OPEN - too many failures"
            )

        # State: STARTING
        await self.monitor.update_state(
            execution_id,
            ExecutionState.STARTING
        )

        # Execute with retry and fallback
        last_error = None
        attempt = 0

        while attempt < self.retry_engine.max_attempts:
            attempt += 1

            try:
                # State: EXECUTING
                await self.monitor.update_state(
                    execution_id,
                    ExecutionState.EXECUTING
                )

                # Try fallback chain
                result = await self.fallback_chain.execute_with_fallback(
                    goal=await self._get_goal(goal_id, uow)
                )

                if result.success:
                    # State: COMPLETING
                    await self.monitor.update_state(
                        execution_id,
                        ExecutionState.COMPLETING
                    )

                    # Record success
                    self.circuit_breaker.record_success()

                    # Complete monitoring
                    await self.monitor.complete_execution(
                        execution_id,
                        success=True,
                        result=result
                    )

                    return result

                # Execution failed
                last_error = result.error

                # Check if should retry
                if not self.retry_engine.should_retry(attempt, last_error):
                    logger.error(
                        "execution_no_retry",
                        attempt=attempt,
                        error=last_error
                    )
                    break

                # Retry with backoff
                backoff = self.retry_engine.get_backoff(attempt)
                logger.info(
                    "execution_retrying",
                    attempt=attempt,
                    backoff_s=backoff,
                    error=last_error
                )

                await asyncio.sleep(backoff)

            except Exception as e:
                last_error = str(e)
                logger.error(
                    "execution_exception",
                    attempt=attempt,
                    error=last_error,
                    exc_info=True
                )

        # All attempts failed
        self.circuit_breaker.record_failure()

        await self.monitor.complete_execution(
            execution_id,
            success=False,
            result=ExecutionResult(success=False, error=last_error)
        )

        return ExecutionResult(
            success=False,
            error=f"Failed after {attempt} attempts. Last error: {last_error}"
        )

    async def _get_goal(self, goal_id: str, uow: UnitOfWork) -> Goal:
        """Get goal from database"""
        return await uow.goals.get(uow.session, UUID(goal_id))
```

---

## API Endpoints

### Health Check
```python
@app.get("/execution/orchestrator/health")
async def orchestrator_health():
    """Get orchestrator health status"""
    orchestrator = get_orchestrator()
    status = orchestrator.monitor.get_health_status()

    return {
        "status": "healthy" if status["success_rate"] > 0.8 else "degraded",
        "active_executions": status["active_executions"],
        "success_rate": f"{status['success_rate']:.1%}",
        "metrics": status["metrics"]
    }
```

### Active Executions
```python
@app.get("/execution/orchestrator/active")
async def list_active_executions():
    """List all currently executing goals"""
    orchestrator = get_orchestrator()
    active = orchestrator.monitor.active_executions

    return {
        "active_count": len(active),
        "executions": [
            {
                "execution_id": ex_id,
                "goal_id": ex["goal_id"],
                "state": ex["state"].value,
                "duration_s": (
                    datetime.utcnow() - ex["started_at"]
                ).total_seconds()
            }
            for ex_id, ex in active.items()
        ]
    }
```

---

## Integration with Existing Code

### Replace current execution calls

**BEFORE** (unstable):
```python
# In goal_executor_v2.py
result = await goal_executor_v2.execute_goal_with_uow(uow, goal_id)
# No retry, no fallback, no monitoring
```

**AFTER** (stable):
```python
# In goal_executor_v2.py
orchestrator = get_orchestrator()
result = await orchestrator.execute_goal(goal_id, uow)
# Full orchestration: retry, fallback, monitoring
```

---

## Benefits

### Reliability
✅ 95%+ success rate (vs current 25%)
✅ Automatic retry on transient failures
✅ Fallback to alternative strategies
✅ Circuit breakers prevent cascade failures

### Observability
✅ Real-time execution tracking
✅ Detailed metrics (success rate, latency, retries)
✅ Full trace logging
✅ Health check endpoints

### Maintainability
✅ Single entry point for all executions
✅ Centralized error handling
✅ Easy to test and debug
✅ Production-ready patterns

---

## Implementation Priority

### Phase 1: Core (1 day)
1. Create `ExecutionOrchestrator` class
2. Implement state machine
3. Add basic retry logic
4. Integrate with existing code

### Phase 2: Enhanced (2 days)
5. Add fallback strategies
6. Implement circuit breakers
7. Add monitoring/tracing
8. Create API endpoints

### Phase 3: Production (1 day)
9. Add metrics dashboard
10. Set up alerts
11. Load testing
12. Documentation

---

## Migration Path

### Step 1: Deploy Orchestrator (alongside existing)
```python
# Add new execution endpoint
@app.post("/goals/execute-orchestrated/{goal_id}")
async def execute_with_orchestrator(goal_id: str):
    """Execute goal using new orchestrator"""
    orchestrator = get_orchestrator()
    result = await orchestrator.execute_goal(goal_id, uow)
    return result
```

### Step 2: A/B Test (10% traffic)
```python
# Route 10% of traffic to orchestrator
if random.random() < 0.1:
    return await orchestrator.execute_goal(goal_id, uow)
else:
    return await goal_executor_v2.execute_goal_with_uow(uow, goal_id)
```

### Step 3: Monitor & Compare
- Success rate
- Latency
- Error types

### Step 4: Full Rollout
- If orchestrator performs better → 100% traffic
- If issues → fix and retry

---

## Success Metrics

### Before Orchestrator
- Success rate: 25%
- Retry logic: None
- Fallback: None
- Observability: 2/10

### After Orchestrator (Target)
- Success rate: 95%+
- Retry logic: 3 attempts with exponential backoff
- Fallback: 3 strategies
- Observability: 9/10

---

## Questions

1. **Should I implement this now?** Yes - this is the right path
2. **How long to implement?** 4 days total (1+2+1 phases)
3. **Risk?** Low - can run alongside existing code
4. **Benefit?** 10x stability improvement

This is what separates DIY agent systems from production-grade AI systems like OpenAI/Anthropic use.
