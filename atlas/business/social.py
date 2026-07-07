"""Social media planning and publishing."""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.business.models import (
    PostStatus,
    SocialPlatform,
    SocialPost,
    _new_id,
    _utcnow,
)


class SocialManager:
    def __init__(self) -> None:
        self._posts: dict[str, SocialPost] = {}

    def create(
        self,
        platform: str = SocialPlatform.TWITTER.value,
        content: str = "",
        campaign_id: str = "",
    ) -> SocialPost:
        p = SocialPost(
            id=_new_id("post"),
            platform=platform,
            content=content,
            campaign_id=campaign_id,
        )
        self._posts[p.id] = p
        return p

    def get(self, pid: str) -> SocialPost | None:
        return self._posts.get(pid)

    def list(
        self,
        platform: str | None = None,
        status: str | None = None,
        campaign_id: str | None = None,
    ) -> list[SocialPost]:
        ps = list(self._posts.values())
        if platform is not None:
            ps = [p for p in ps if p.platform == platform]
        if status is not None:
            ps = [p for p in ps if p.status == status]
        if campaign_id is not None:
            ps = [p for p in ps if p.campaign_id == campaign_id]
        return sorted(ps, key=lambda p: p.created_at, reverse=True)

    def schedule(self, pid: str, when: Any) -> SocialPost | None:
        p = self._posts.get(pid)
        if p is None:
            return None
        updated = dataclasses.replace(
            p, status=PostStatus.SCHEDULED.value, scheduled_at=when
        )
        self._posts[pid] = updated
        return updated

    def publish(self, pid: str) -> SocialPost | None:
        p = self._posts.get(pid)
        if p is None:
            return None
        updated = dataclasses.replace(
            p, status=PostStatus.PUBLISHED.value, published_at=_utcnow()
        )
        self._posts[pid] = updated
        return updated

    def fail(self, pid: str) -> SocialPost | None:
        p = self._posts.get(pid)
        if p is None:
            return None
        updated = dataclasses.replace(p, status=PostStatus.FAILED.value)
        self._posts[pid] = updated
        return updated

    def scheduled_posts(self) -> list[SocialPost]:
        now = _utcnow()
        return sorted(
            [
                p
                for p in self._posts.values()
                if p.status == PostStatus.SCHEDULED.value
                and p.scheduled_at
                and p.scheduled_at >= now
            ],
            key=lambda p: p.scheduled_at or _utcnow(),
        )

    def published_count(self) -> int:
        return sum(
            1 for p in self._posts.values() if p.status == PostStatus.PUBLISHED.value
        )

    def count(self) -> int:
        return len(self._posts)

    def count_by_platform(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in self._posts.values():
            counts[p.platform] = counts.get(p.platform, 0) + 1
        return counts


__all__ = ["SocialManager"]
