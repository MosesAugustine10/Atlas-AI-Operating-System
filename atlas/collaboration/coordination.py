"""Coordination engine — multi-agent coordination patterns.

The :class:`CoordinationEngine` builds and executes coordination
patterns (pipeline, fan-out, fan-in, round-robin, debate,
hierarchical, peer-to-peer). Each pattern is expressed as a
:class:`Pipeline` of :class:`PipelineStep` instances.

The engine never imports Brain or Workforce directly — it receives a
``think_fn`` callback that each step calls to produce its output.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from atlas.collaboration.models import (
    AgentRole,
    Pipeline,
    PipelineStep,
    _new_id,
    _utcnow,
)


class CoordinationError(RuntimeError):
    """Raised when a coordination operation fails."""


class CoordinationEngine:
    """Builds and executes coordination patterns.

    Parameters:
        think_fn: Optional callback invoked by each pipeline step with
            ``(step, context, **kwargs)`` and returning a result string.
            When omitted, steps return a placeholder.
    """

    def __init__(
        self,
        think_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._pipelines: dict[str, Pipeline] = {}
        self._think_fn = think_fn

    # ------------------------------------------------------------------
    # Pattern builders
    # ------------------------------------------------------------------

    def build_pipeline(
        self,
        session_id: str,
        steps: list[tuple[str, str]],  # (agent_id, role) pairs
        name: str = "",
    ) -> Pipeline:
        """Build a sequential pipeline pattern.

        ``steps`` is a list of ``(agent_id, role)`` tuples. The
        pipeline executes steps in order, passing each step's output
        as the next step's input.
        """
        step_objs: list[PipelineStep] = []
        for i, (agent_id, role) in enumerate(steps):
            step = PipelineStep(
                id=_new_id("step"),
                pipeline_id="",  # filled in below
                agent_id=agent_id,
                role=role,
                order=i,
            )
            step_objs.append(step)
        pipeline = Pipeline(
            id=_new_id("pipeline"),
            session_id=session_id,
            name=name or "pipeline",
            steps=(),
        )
        # Wire up pipeline_id on each step
        wired_steps = tuple(
            dataclasses.replace(s, pipeline_id=pipeline.id) for s in step_objs
        )
        pipeline = dataclasses.replace(pipeline, steps=wired_steps)
        self._pipelines[pipeline.id] = pipeline
        return pipeline

    def build_fan_out(
        self,
        session_id: str,
        initiator_id: str,
        worker_ids: list[str],
        name: str = "",
    ) -> Pipeline:
        """Build a fan-out pattern: initiator → many parallel workers."""
        steps: list[tuple[str, str]] = [(initiator_id, AgentRole.COORDINATOR.value)]
        for wid in worker_ids:
            steps.append((wid, AgentRole.CODER.value))
        return self.build_pipeline(session_id, steps, name=name or "fan_out")

    def build_fan_in(
        self,
        session_id: str,
        worker_ids: list[str],
        aggregator_id: str,
        name: str = "",
    ) -> Pipeline:
        """Build a fan-in pattern: many workers → one aggregator."""
        steps: list[tuple[str, str]] = []
        for wid in worker_ids:
            steps.append((wid, AgentRole.CODER.value))
        steps.append((aggregator_id, AgentRole.COORDINATOR.value))
        return self.build_pipeline(session_id, steps, name=name or "fan_in")

    def build_round_robin(
        self,
        session_id: str,
        agent_ids: list[str],
        rounds: int = 1,
        name: str = "",
    ) -> Pipeline:
        """Build a round-robin pattern."""
        steps: list[tuple[str, str]] = []
        for _ in range(rounds):
            for aid in agent_ids:
                steps.append((aid, AgentRole.OBSERVER.value))
        return self.build_pipeline(session_id, steps, name=name or "round_robin")

    def build_debate(
        self,
        session_id: str,
        proposer_ids: list[str],
        voter_ids: list[str],
        name: str = "",
    ) -> Pipeline:
        """Build a debate pattern: proposers debate, then voters vote."""
        steps: list[tuple[str, str]] = []
        for pid in proposer_ids:
            steps.append((pid, AgentRole.REVIEWER.value))
        for vid in voter_ids:
            steps.append((vid, AgentRole.OBSERVER.value))
        return self.build_pipeline(session_id, steps, name=name or "debate")

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        pipeline_id: str,
        initial_input: str = "",
    ) -> Pipeline:
        """Execute a pipeline sequentially.

        Each step's result is passed as input to the next step. The
        pipeline's status is updated as steps complete.
        """
        pipeline = self._require(pipeline_id)
        current_input = initial_input
        new_steps: list[PipelineStep] = []
        for step in pipeline.steps:
            started = _utcnow()
            updated_step = dataclasses.replace(
                step,
                status="in_progress",
                started_at=started,
            )
            try:
                result = self._execute_step(updated_step, current_input)
                completed = _utcnow()
                updated_step = dataclasses.replace(
                    updated_step,
                    status="completed",
                    completed_at=completed,
                    result=result,
                )
                current_input = result
            except Exception as exc:  # noqa: BLE001 — surface any error
                updated_step = dataclasses.replace(
                    updated_step,
                    status="failed",
                    completed_at=_utcnow(),
                    result=str(exc),
                )
                new_steps.append(updated_step)
                self._update_pipeline(
                    pipeline_id,
                    steps=tuple(new_steps + list(pipeline.steps[len(new_steps) :])),
                    status="failed",
                )
                return self._pipelines[pipeline_id]
            new_steps.append(updated_step)
        return self._update_pipeline(
            pipeline_id,
            steps=tuple(new_steps),
            status="completed",
            completed_at=_utcnow(),
        )

    def _execute_step(self, step: PipelineStep, input_text: str) -> str:
        """Execute a single pipeline step."""
        if self._think_fn is None:
            return f"[{step.role}] step {step.order} done"
        try:
            result = self._think_fn(
                step=step,
                input_text=input_text,
                agent_id=step.agent_id,
                role=step.role,
            )
            return str(result) if result is not None else ""
        except Exception as exc:  # noqa: BLE001 — surface any error
            raise CoordinationError(f"step {step.id} failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, pipeline_id: str) -> Pipeline | None:
        """Return the pipeline with ``pipeline_id`` or ``None``."""
        return self._pipelines.get(pipeline_id)

    def list_pipelines(
        self,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[Pipeline]:
        """List pipelines with optional filters."""
        pipelines = list(self._pipelines.values())
        if session_id is not None:
            pipelines = [p for p in pipelines if p.session_id == session_id]
        if status is not None:
            pipelines = [p for p in pipelines if p.status == status]
        return pipelines

    def step_count(self, pipeline_id: str) -> int:
        """Return the number of steps in a pipeline."""
        p = self._require(pipeline_id)
        return len(p.steps)

    def completed_steps(self, pipeline_id: str) -> int:
        """Return the number of completed steps in a pipeline."""
        p = self._require(pipeline_id)
        return sum(1 for s in p.steps if s.status == "completed")

    def progress(self, pipeline_id: str) -> float:
        """Return the completion fraction (0.0 to 1.0) of a pipeline."""
        p = self._require(pipeline_id)
        if not p.steps:
            return 0.0
        return self.completed_steps(pipeline_id) / len(p.steps)

    def count(self) -> int:
        """Return the total number of pipelines."""
        return len(self._pipelines)

    def count_by_status(self) -> dict[str, int]:
        """Return a dict of pipeline counts by status."""
        counts: dict[str, int] = {}
        for p in self._pipelines.values():
            counts[p.status] = counts.get(p.status, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require(self, pipeline_id: str) -> Pipeline:
        p = self._pipelines.get(pipeline_id)
        if p is None:
            raise CoordinationError(f"pipeline {pipeline_id} not found")
        return p

    def _update_pipeline(self, pipeline_id: str, **changes: Any) -> Pipeline:
        p = self._pipelines[pipeline_id]
        updated = dataclasses.replace(p, **changes)
        self._pipelines[pipeline_id] = updated
        return updated


__all__ = ["CoordinationEngine", "CoordinationError"]
