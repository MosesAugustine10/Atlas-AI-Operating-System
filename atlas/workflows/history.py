"""Workflow run history tracking.

The :class:`WorkflowHistory` records every :class:`WorkflowRun` snapshot the
engine produces. Because runs are immutable, each snapshot is a distinct
object — the history is therefore an append-only log of run states rather
than a mutable store.

Lookups are supported by run id and by workflow definition id. The history
also exposes ``latest`` for retrieving the most recent run of a given
workflow, which is useful for retry and observability flows.

The default implementation is in-memory; a future persistence backend can
subclass the same contract and swap in transparently.
"""

from __future__ import annotations

from collections.abc import Iterator

from atlas.core.logger import get_logger
from atlas.workflows.models import WorkflowRun


class WorkflowHistory:
    """Append-only history of workflow run snapshots.

    The history stores *every* recorded snapshot of a run, keyed by run id.
    Callers that want only the latest snapshot should use :meth:`get`; callers
    that want the full trajectory (for audit / replay) should use
    :meth:`trajectory`.
    """

    def __init__(self) -> None:
        # Latest snapshot per run id.
        self._latest: dict[str, WorkflowRun] = {}
        # Full trajectory per run id (chronological order).
        self._trajectory: dict[str, list[WorkflowRun]] = {}
        # Insertion order of run ids (for stable listing).
        self._order: list[str] = []
        self.logger = get_logger("workflow.history")

    def record(self, run: WorkflowRun) -> WorkflowRun:
        """Record ``run`` as a new snapshot.

        Returns the run unchanged so the method composes nicely with the
        engine's ``replace``-based update flow.
        """
        if run.id not in self._latest:
            self._order.append(run.id)
            self._trajectory[run.id] = []
        self._latest[run.id] = run
        self._trajectory[run.id].append(run)
        self.logger.debug(
            "Recorded run snapshot: %s (state=%s)", run.id, run.state.value
        )
        return run

    def get(self, run_id: str) -> WorkflowRun | None:
        """Return the latest snapshot for ``run_id`` or ``None``."""
        return self._latest.get(run_id)

    def trajectory(self, run_id: str) -> list[WorkflowRun]:
        """Return every recorded snapshot for ``run_id`` in chronological order.

        Returns an empty list if the run is unknown.
        """
        return list(self._trajectory.get(run_id, []))

    def list_runs(
        self,
        workflow_id: str | None = None,
        limit: int = 100,
    ) -> list[WorkflowRun]:
        """Return the latest snapshot of every recorded run.

        Args:
            workflow_id: If given, restrict results to runs of this workflow
                definition. ``None`` returns runs of any workflow.
            limit: Maximum number of results to return. Runs are returned in
                insertion order; pass through :meth:`latest` if you need
                recency-based ordering.
        """
        runs: list[WorkflowRun] = []
        for run_id in self._order:
            run = self._latest[run_id]
            if workflow_id is None or run.definition_id == workflow_id:
                runs.append(run)
                if len(runs) >= limit:
                    break
        return runs

    def latest(self, workflow_id: str) -> WorkflowRun | None:
        """Return the most recently recorded run for ``workflow_id``.

        Returns ``None`` if no run exists for the workflow.
        """
        for run_id in reversed(self._order):
            run = self._latest[run_id]
            if run.definition_id == workflow_id:
                return run
        return None

    def count(self, workflow_id: str | None = None) -> int:
        """Return the number of recorded runs, optionally filtered by workflow."""
        if workflow_id is None:
            return len(self._latest)
        return sum(
            1 for run in self._latest.values() if run.definition_id == workflow_id
        )

    def clear(self) -> None:
        """Remove all recorded runs."""
        self._latest.clear()
        self._trajectory.clear()
        self._order.clear()

    def __iter__(self) -> Iterator[WorkflowRun]:
        for run_id in self._order:
            yield self._latest[run_id]

    def __len__(self) -> int:
        return len(self._latest)

    def __contains__(self, run_id: object) -> bool:
        return run_id in self._latest

    def __repr__(self) -> str:
        return f"<WorkflowHistory runs={len(self)}>"


__all__ = ["WorkflowHistory"]
