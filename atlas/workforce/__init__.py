"""Atlas Autonomous Workforce — orchestration layer for autonomous AI employees.

The Workforce Layer sits ABOVE the Brain in the Atlas stack:

    User
      ↓
    Workforce  ← this package
      ↓
    Brain
      ↓
    Execution
      ↓
    Runtime
      ↓
    Providers / MCP / Workflows

Workers are autonomous AI employees that collaborate on shared goals.
Each worker has a role (CEO, CTO, Software Engineer, etc.), skills,
personal memory, and a lifecycle (offline → idle → busy → stopped).
Workers communicate through a :class:`CommunicationChannel`,
delegate via :class:`DelegationEngine`, escalate to a
:class:`Supervisor`, and are coordinated by the
:class:`WorkforceOrchestrator`.

**Dependency injection everywhere.** Workers never import Brain,
Execution, Providers, or any Atlas subsystem directly. They receive a
``think_fn`` callable (typically ``Brain.think``) at construction
time. This keeps the workforce package fully decoupled from every
concrete subsystem.

**No backend duplication.** The workforce reuses the existing Brain,
Execution Engine, Runtime, Providers, Workflows, MCP, Memory and
Knowledge systems via injected callbacks — it does not reimplement
any of their functionality.

Modules:

* :mod:`atlas.workforce.models` — frozen dataclasses and enums (leaf).
* :mod:`atlas.workforce.roles` — role definitions, skills, chain of command.
* :mod:`atlas.workforce.worker` — the :class:`Worker` class.
* :mod:`atlas.workforce.team` — the :class:`TeamManager` for team lifecycle.
* :mod:`atlas.workforce.manager` — the :class:`WorkforceManager` facade.
* :mod:`atlas.workforce.orchestrator` — the :class:`WorkforceOrchestrator` entry point.
* :mod:`atlas.workforce.communication` — inter-worker messaging.
* :mod:`atlas.workforce.delegation` — autonomous task delegation.
* :mod:`atlas.workforce.planning` — goal → task decomposition.
* :mod:`atlas.workforce.coordination` — shared workspace + handoffs.
* :mod:`atlas.workforce.review` — quality review + approvals.
* :mod:`atlas.workforce.learning` — worker skill improvement.
* :mod:`atlas.workforce.supervisor` — oversight + conflict resolution.
* :mod:`atlas.workforce.scheduler` — shifts + load balancing.
* :mod:`atlas.workforce.metrics` — productivity metrics.
* :mod:`atlas.workforce.reports` — workforce-wide reports.

Usage:

    from atlas.workforce import WorkforceOrchestrator

    # Wire in the Brain (or any callable with (goal_description=...) signature)
    from atlas.intelligence.brain import Brain
    brain = Brain()
    orchestrator = WorkforceOrchestrator(think_fn=brain.think)

    # Hire the default workforce (17 roles)
    orchestrator.hire_default_workforce()

    # Execute a goal end-to-end
    report = orchestrator.execute_goal("Build a hello world app")
    print(report.completion_rate)
"""

from __future__ import annotations

__version__ = "1.0.0"


def has_brain() -> bool:
    """Return ``True`` if :mod:`atlas.intelligence.brain` is importable.

    This is a convenience helper for callers that want to check whether
    the Brain is available before wiring it into the workforce. The
    workforce package itself never imports Brain — this function does
    a lazy import check.
    """
    try:
        from atlas.intelligence.brain import (
            Brain,
        )  # noqa: F401  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001 — optional dependency
        return False
    return True


# Re-export models (pure Python, always available)
# Re-export engines and facades (pure Python, always available)
from atlas.workforce.communication import CommunicationChannel  # noqa: E402
from atlas.workforce.coordination import CoordinationEngine  # noqa: E402
from atlas.workforce.delegation import DelegationEngine, DelegationError  # noqa: E402
from atlas.workforce.learning import LearningEngine, Lesson  # noqa: E402
from atlas.workforce.manager import WorkforceManager  # noqa: E402
from atlas.workforce.metrics import MetricsCollector  # noqa: E402
from atlas.workforce.models import (  # noqa: E402
    Approval,
    Conflict,
    ConflictKind,
    ConflictResolution,
    Delegation,
    Escalation,
    EscalationLevel,
    ExecuteFn,
    GenerateFn,
    Message,
    MessageKind,
    Review,
    ReviewVerdict,
    Shift,
    ShiftStatus,
    Task,
    TaskArtifact,
    TaskPriority,
    TaskStatus,
    Team,
    TeamMetrics,
    ThinkFn,
    WorkerKind,
    WorkerMemory,
    WorkerMetrics,
    WorkerRole,
    WorkerSkill,
    WorkerState,
    WorkerStatus,
    WorkforceReport,
    priority_rank,
)
from atlas.workforce.orchestrator import WorkforceOrchestrator  # noqa: E402
from atlas.workforce.planning import PlanningEngine  # noqa: E402
from atlas.workforce.reports import ReportGenerator  # noqa: E402
from atlas.workforce.review import ReviewEngine  # noqa: E402

# Re-export roles helpers
from atlas.workforce.roles import (  # noqa: E402
    all_roles,
    can_approve,
    can_delegate,
    can_lead_team,
    can_review,
    chain_of_command_rank,
    default_skills,
    display_name,
    is_agent,
    is_executive,
    is_specialist,
)
from atlas.workforce.scheduler import Scheduler  # noqa: E402
from atlas.workforce.supervisor import Supervisor  # noqa: E402
from atlas.workforce.team import TeamError, TeamManager  # noqa: E402
from atlas.workforce.worker import Worker, WorkerError  # noqa: E402

__all__ = [
    "__version__",
    "has_brain",
    # Models
    "Approval",
    "Conflict",
    "ConflictKind",
    "ConflictResolution",
    "Delegation",
    "Escalation",
    "EscalationLevel",
    "ExecuteFn",
    "GenerateFn",
    "Message",
    "MessageKind",
    "Review",
    "ReviewVerdict",
    "Shift",
    "ShiftStatus",
    "Task",
    "TaskArtifact",
    "TaskPriority",
    "TaskStatus",
    "Team",
    "TeamMetrics",
    "ThinkFn",
    "WorkerKind",
    "WorkerMemory",
    "WorkerMetrics",
    "WorkerRole",
    "WorkerSkill",
    "WorkerState",
    "WorkerStatus",
    "WorkforceReport",
    "priority_rank",
    # Roles
    "all_roles",
    "can_approve",
    "can_delegate",
    "can_lead_team",
    "can_review",
    "chain_of_command_rank",
    "default_skills",
    "display_name",
    "is_agent",
    "is_executive",
    "is_specialist",
    # Engines
    "CommunicationChannel",
    "CoordinationEngine",
    "DelegationEngine",
    "DelegationError",
    "LearningEngine",
    "Lesson",
    "MetricsCollector",
    "PlanningEngine",
    "ReportGenerator",
    "ReviewEngine",
    "Scheduler",
    "Supervisor",
    # Facades
    "TeamError",
    "TeamManager",
    "Worker",
    "WorkerError",
    "WorkforceManager",
    "WorkforceOrchestrator",
]
