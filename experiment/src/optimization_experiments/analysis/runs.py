from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import pandas as pd


@dataclass(frozen=True, slots=True)
class RunDataset:
    frame: pd.DataFrame

    @classmethod
    def from_parquet(cls, path: str) -> "RunDataset":
        return cls(pd.read_parquet(path))

    def aggregate(
        self,
        group_by: Sequence[str],
        *,
        metrics: Sequence[str] = (
            "objective.best_value",
            "function_evaluations",
            "iterations",
            "timing.cpu_seconds",
        ),
    ) -> pd.DataFrame:
        existing = [metric for metric in metrics if metric in self.frame.columns]
        if not existing:
            raise ValueError("None of the requested metrics exist in the dataset.")
        return aggregate_runs(self.frame, group_by=group_by, metrics=existing)


def aggregate_runs(
    frame: pd.DataFrame,
    *,
    group_by: Sequence[str],
    metrics: Sequence[str],
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()

    missing_groups = [column for column in group_by if column not in frame.columns]
    if missing_groups:
        raise KeyError(f"Missing grouping columns: {missing_groups}.")

    missing_metrics = [column for column in metrics if column not in frame.columns]
    if missing_metrics:
        raise KeyError(f"Missing metric columns: {missing_metrics}.")

    aggregation = {}
    for metric in metrics:
        aggregation[metric] = ["min", "max", "mean", "std"]

    result = frame.groupby(list(group_by), dropna=False).agg(aggregation)
    result.columns = [
        f"{metric}__{statistic}"
        for metric, statistic in result.columns.to_flat_index()
    ]
    return result.reset_index()
