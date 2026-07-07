"""Forecast engine — revenue, customers, growth, cost predictions."""

from __future__ import annotations

from collections.abc import Callable

from atlas.enterprise.models import (
    Forecast,
    ForecastResult,
    ForecastType,
    _new_id,
)


class ForecastEngine:
    """Generates forecasts using linear extrapolation or injected callbacks."""

    def __init__(
        self, forecast_fn: Callable[..., ForecastResult] | None = None
    ) -> None:
        self._forecasts: dict[str, Forecast] = {}
        self._results: dict[str, ForecastResult] = {}
        self._forecast_fn = forecast_fn

    def create(
        self,
        type: str = ForecastType.REVENUE.value,
        period: str = "",
        horizon_days: int = 30,
        method: str = "linear",
    ) -> Forecast:
        f = Forecast(
            id=_new_id("fc"),
            type=type,
            period=period,
            horizon_days=horizon_days,
            method=method,
        )
        self._forecasts[f.id] = f
        return f

    def run(
        self, forecast_id: str, historical_data: list[float] | None = None
    ) -> ForecastResult:
        f = self._forecasts.get(forecast_id)
        if f is None:
            raise KeyError(f"forecast {forecast_id} not found")
        if self._forecast_fn is not None:
            result = self._forecast_fn(
                forecast=f, historical_data=historical_data or []
            )
        else:
            result = self._linear_forecast(f, historical_data or [])
        self._results[result.id] = result
        return result

    def _linear_forecast(self, forecast: Forecast, data: list[float]) -> ForecastResult:
        if not data:
            return ForecastResult(
                id=_new_id("fres"),
                forecast_id=forecast.id,
                predicted_value=0.0,
                confidence=0.0,
            )
        # Simple linear extrapolation: average growth rate * last value
        if len(data) < 2:
            predicted = data[-1]
            confidence = 0.3
        else:
            growth_rates = [
                (data[i] - data[i - 1]) / max(abs(data[i - 1]), 1.0)
                for i in range(1, len(data))
            ]
            avg_growth = sum(growth_rates) / len(growth_rates)
            predicted = data[-1] * (1 + avg_growth * forecast.horizon_days / 30)
            confidence = min(0.95, 0.5 + 0.1 * len(data))
        lower = predicted * (1 - (1 - confidence))
        upper = predicted * (1 + (1 - confidence))
        return ForecastResult(
            id=_new_id("fres"),
            forecast_id=forecast.id,
            predicted_value=round(predicted, 2),
            confidence=round(confidence, 4),
            lower_bound=round(lower, 2),
            upper_bound=round(upper, 2),
        )

    def get(self, fid: str) -> Forecast | None:
        return self._forecasts.get(fid)

    def get_result(self, rid: str) -> ForecastResult | None:
        return self._results.get(rid)

    def list_forecasts(self, type: str | None = None) -> list[Forecast]:
        fs = list(self._forecasts.values())
        if type is not None:
            fs = [f for f in fs if f.type == type]
        return fs

    def list_results(self, forecast_id: str | None = None) -> list[ForecastResult]:
        rs = list(self._results.values())
        if forecast_id is not None:
            rs = [r for r in rs if r.forecast_id == forecast_id]
        return rs

    def count(self) -> int:
        return len(self._forecasts)


__all__ = ["ForecastEngine"]
