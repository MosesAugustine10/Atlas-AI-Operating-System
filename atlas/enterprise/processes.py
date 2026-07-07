"""Business process engine — reusable processes with pipeline stages."""

from __future__ import annotations

import dataclasses

from atlas.enterprise.models import (
    BusinessProcess,
    Pipeline,
    PipelineStage,
    ProcessStatus,
    _new_id,
    _utcnow,
)


class ProcessEngine:
    """Manages reusable business processes and their pipelines."""

    def __init__(self) -> None:
        self._processes: dict[str, BusinessProcess] = {}
        self._pipelines: dict[str, Pipeline] = {}

    def create_process(
        self,
        name: str,
        description: str = "",
        stages: tuple[str, ...] = (),
        department_id: str = "",
    ) -> BusinessProcess:
        p = BusinessProcess(
            id=_new_id("proc"),
            name=name,
            description=description,
            stages=stages,
            department_id=department_id,
        )
        self._processes[p.id] = p
        return p

    def get_process(self, pid: str) -> BusinessProcess | None:
        return self._processes.get(pid)

    def list_processes(self, status: str | None = None) -> list[BusinessProcess]:
        ps = list(self._processes.values())
        if status is not None:
            ps = [p for p in ps if p.status == status]
        return ps

    def activate_process(self, pid: str) -> BusinessProcess | None:
        p = self._processes.get(pid)
        if p is None:
            return None
        updated = dataclasses.replace(
            p, status=ProcessStatus.ACTIVE.value, updated_at=_utcnow()
        )
        self._processes[pid] = updated
        return updated

    def create_pipeline(self, process_id: str, name: str = "") -> Pipeline:
        process = self._processes.get(process_id)
        stage_names = process.stages if process else ()
        stages = tuple(
            PipelineStage(id=_new_id("stage"), pipeline_id="", name=sname, order=i)
            for i, sname in enumerate(stage_names)
        )
        pipeline = Pipeline(
            id=_new_id("pipe"), name=name, process_id=process_id, stages=()
        )
        # Fix pipeline_id on stages
        wired = tuple(dataclasses.replace(s, pipeline_id=pipeline.id) for s in stages)
        pipeline = dataclasses.replace(pipeline, stages=wired)
        self._pipelines[pipeline.id] = pipeline
        return pipeline

    def get_pipeline(self, pid: str) -> Pipeline | None:
        return self._pipelines.get(pid)

    def list_pipelines(self, process_id: str | None = None) -> list[Pipeline]:
        ps = list(self._pipelines.values())
        if process_id is not None:
            ps = [p for p in ps if p.process_id == process_id]
        return ps

    def advance_stage(self, pipeline_id: str) -> Pipeline | None:
        p = self._pipelines.get(pipeline_id)
        if p is None:
            return None
        new_stages: list[PipelineStage] = []
        advanced = False
        for s in p.stages:
            if not advanced and s.status != ProcessStatus.COMPLETED.value:
                new_stages.append(
                    dataclasses.replace(
                        s, status=ProcessStatus.COMPLETED.value, completed_at=_utcnow()
                    )
                )
                advanced = True
            elif not advanced and s.status == ProcessStatus.COMPLETED.value:
                new_stages.append(s)
            elif not advanced:
                # Start this stage
                new_stages.append(
                    dataclasses.replace(
                        s, status=ProcessStatus.ACTIVE.value, started_at=_utcnow()
                    )
                )
                advanced = True
            else:
                new_stages.append(s)
        # If all stages completed, complete the pipeline
        all_done = all(s.status == ProcessStatus.COMPLETED.value for s in new_stages)
        updated = dataclasses.replace(
            p,
            stages=tuple(new_stages),
            status=ProcessStatus.COMPLETED.value if all_done else p.status,
            completed_at=_utcnow() if all_done else None,
        )
        self._pipelines[pipeline_id] = updated
        return updated

    def pipeline_progress(self, pipeline_id: str) -> float:
        p = self._pipelines.get(pipeline_id)
        if p is None or not p.stages:
            return 0.0
        completed = sum(
            1 for s in p.stages if s.status == ProcessStatus.COMPLETED.value
        )
        return completed / len(p.stages)

    def count(self) -> int:
        return len(self._processes)

    def pipeline_count(self) -> int:
        return len(self._pipelines)


__all__ = ["ProcessEngine"]
