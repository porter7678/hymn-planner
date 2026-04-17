"""Pure scoring logic. No I/O, no Flask imports."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date
from typing import Literal

from data import Hymn, HistoryEntry, last_sung

Pool = Literal["sacrament", "general"]


@dataclass(frozen=True)
class ScoringConfig:
    popularity_weight: float = 0.7
    noise_amplitude: float = 0.15
    cooldown_weeks: int = 8
    recency_cap_weeks: int = 52
    sigmoid_midpoint: float = 7
    sigmoid_slope: float = 2


@dataclass(frozen=True)
class ScoredHymn:
    hymn: Hymn
    weeks_since: int | None
    adj_popularity: int
    popularity_score: float
    recency_score: float
    score: float


def _weeks_since(last: date | None, reference_sunday: date) -> int | None:
    if last is None:
        return None
    return (reference_sunday - last).days // 7


def _in_pool(hymn: Hymn, pool: Pool) -> bool:
    if pool == "sacrament":
        return hymn.is_sacrament
    return hymn.is_general


def score_hymns(
    hymns: list[Hymn],
    history: list[HistoryEntry],
    reference_sunday: date,
    pool: Pool,
    config: ScoringConfig = ScoringConfig(),
    excluded_ids: frozenset[int] = frozenset(),
    rng: random.Random | None = None,
) -> list[ScoredHymn]:
    rng = rng if rng is not None else random.Random()
    results: list[ScoredHymn] = []

    for hymn in hymns:
        if hymn.flagged or hymn.is_holiday:
            continue
        if not _in_pool(hymn, pool):
            continue
        if hymn.id in excluded_ids:
            continue

        weeks_since = _weeks_since(
            last_sung(hymn.id, history, reference_sunday), reference_sunday
        )
        if weeks_since is not None and weeks_since <= config.cooldown_weeks:
            continue

        adj_popularity = hymn.popularity + (hymn.popularity_adjustment or 0)
        popularity_score = 1.0 / (
            1.0
            + math.exp(
                -config.sigmoid_slope * (adj_popularity - config.sigmoid_midpoint)
            )
        )
        effective_weeks = (
            weeks_since if weeks_since is not None else config.recency_cap_weeks
        )
        recency_score = (
            min(effective_weeks, config.recency_cap_weeks) / config.recency_cap_weeks
        )
        noise = rng.uniform(-config.noise_amplitude, config.noise_amplitude)
        score = (
            config.popularity_weight * popularity_score
            + (1 - config.popularity_weight) * recency_score
            + noise
        )

        results.append(
            ScoredHymn(
                hymn=hymn,
                weeks_since=weeks_since,
                adj_popularity=adj_popularity,
                popularity_score=popularity_score,
                recency_score=recency_score,
                score=score,
            )
        )

    results.sort(key=lambda s: s.score, reverse=True)
    return results
