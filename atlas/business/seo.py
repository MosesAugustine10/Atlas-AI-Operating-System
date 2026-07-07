"""SEO and AEO analysis."""

from __future__ import annotations

from collections.abc import Callable

from atlas.business.models import SEOResult, _new_id


class SEOManager:
    def __init__(self, analyze_fn: Callable[..., SEOResult] | None = None) -> None:
        self._results: dict[str, SEOResult] = {}
        self._analyze_fn = analyze_fn

    def analyze(self, url: str) -> SEOResult:
        if self._analyze_fn is not None:
            result = self._analyze_fn(url=url)
        else:
            result = self._fallback_analyze(url)
        self._results[result.id] = result
        return result

    def _fallback_analyze(self, url: str) -> SEOResult:
        issues: list[str] = []
        recommendations: list[str] = []
        score = 50.0
        if not url.startswith("https://"):
            issues.append("Not using HTTPS")
            score -= 10
        if len(url) > 100:
            issues.append("URL too long")
            score -= 5
        if not issues:
            recommendations.append("URL structure looks good")
            score += 20
        recommendations.append("Add meta description")
        recommendations.append("Improve page load speed")
        return SEOResult(
            id=_new_id("seo"),
            url=url,
            score=max(0.0, min(100.0, score)),
            issues=tuple(issues),
            recommendations=tuple(recommendations),
        )

    def get(self, rid: str) -> SEOResult | None:
        return self._results.get(rid)

    def list(self) -> list[SEOResult]:
        return list(self._results.values())

    def best_score(self) -> float:
        if not self._results:
            return 0.0
        return max(r.score for r in self._results.values())

    def average_score(self) -> float:
        if not self._results:
            return 0.0
        return sum(r.score for r in self._results.values()) / len(self._results)

    def count(self) -> int:
        return len(self._results)


__all__ = ["SEOManager"]
