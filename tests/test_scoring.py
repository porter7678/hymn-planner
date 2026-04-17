"""Tests for scoring.py."""

from __future__ import annotations

import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from data import HistoryEntry, Hymn
from scoring import ScoredHymn, ScoringConfig, score_hymns


REF_SUNDAY = date(2026, 4, 19)
ZERO_NOISE = ScoringConfig(noise_amplitude=0.0)


def _hymn(
    id: int,
    *,
    name: str = "",
    popularity: int = 7,
    popularity_adjustment: int | None = None,
    flagged: bool = False,
    is_sacrament: bool = False,
    is_general: bool = True,
    is_holiday: bool = False,
    length: str = "3:00",
) -> Hymn:
    return Hymn(
        id=id,
        name=name or f"Hymn {id}",
        length=length,
        popularity=popularity,
        popularity_adjustment=popularity_adjustment,
        flagged=flagged,
        is_sacrament=is_sacrament,
        is_general=is_general,
        is_holiday=is_holiday,
    )


def _entry(hymn: Hymn, when: date, slot: str = "opening") -> HistoryEntry:
    return HistoryEntry(date=when, slot=slot, hymn_id=hymn.id, name=hymn.name)


def _weeks_before(ref: date, weeks: int) -> date:
    return ref - timedelta(weeks=weeks)


class TestFilters:
    def test_flagged_hymn_excluded(self) -> None:
        flagged = _hymn(1, flagged=True)
        ok = _hymn(2)

        result = score_hymns([flagged, ok], [], REF_SUNDAY, "general", ZERO_NOISE)

        assert [s.hymn.id for s in result] == [2]

    def test_holiday_hymn_excluded(self) -> None:
        holiday = _hymn(1, is_holiday=True, is_general=True)
        ok = _hymn(2)

        result = score_hymns([holiday, ok], [], REF_SUNDAY, "general", ZERO_NOISE)

        assert [s.hymn.id for s in result] == [2]

    def test_sacrament_pool_excludes_general_only(self) -> None:
        sacrament = _hymn(1, is_sacrament=True, is_general=False)
        general = _hymn(2, is_sacrament=False, is_general=True)

        result = score_hymns(
            [sacrament, general], [], REF_SUNDAY, "sacrament", ZERO_NOISE
        )

        assert [s.hymn.id for s in result] == [1]

    def test_general_pool_excludes_sacrament_only(self) -> None:
        sacrament = _hymn(1, is_sacrament=True, is_general=False)
        general = _hymn(2, is_sacrament=False, is_general=True)

        result = score_hymns(
            [sacrament, general], [], REF_SUNDAY, "general", ZERO_NOISE
        )

        assert [s.hymn.id for s in result] == [2]

    def test_dual_pool_hymn_appears_in_both(self) -> None:
        both = _hymn(1, is_sacrament=True, is_general=True)

        sac_result = score_hymns([both], [], REF_SUNDAY, "sacrament", ZERO_NOISE)
        gen_result = score_hymns([both], [], REF_SUNDAY, "general", ZERO_NOISE)

        assert [s.hymn.id for s in sac_result] == [1]
        assert [s.hymn.id for s in gen_result] == [1]

    def test_excluded_ids_filtered(self) -> None:
        a = _hymn(1)
        b = _hymn(2)

        result = score_hymns(
            [a, b], [], REF_SUNDAY, "general", ZERO_NOISE, excluded_ids=frozenset({1})
        )

        assert [s.hymn.id for s in result] == [2]

    def test_cooldown_excludes_exactly_at_boundary(self) -> None:
        hymn = _hymn(1)
        history = [_entry(hymn, _weeks_before(REF_SUNDAY, 8))]

        result = score_hymns([hymn], history, REF_SUNDAY, "general", ZERO_NOISE)

        assert result == []

    def test_cooldown_includes_just_past_boundary(self) -> None:
        hymn = _hymn(1)
        history = [_entry(hymn, _weeks_before(REF_SUNDAY, 9))]

        result = score_hymns([hymn], history, REF_SUNDAY, "general", ZERO_NOISE)

        assert [s.hymn.id for s in result] == [1]
        assert result[0].weeks_since == 9

    def test_never_sung_passes_cooldown(self) -> None:
        hymn = _hymn(1)

        result = score_hymns([hymn], [], REF_SUNDAY, "general", ZERO_NOISE)

        assert [s.hymn.id for s in result] == [1]
        assert result[0].weeks_since is None


class TestSigmoidShape:
    def _popularity_score(self, adj_pop: int) -> float:
        hymn = _hymn(1, popularity=adj_pop)
        [result] = score_hymns([hymn], [], REF_SUNDAY, "general", ZERO_NOISE)
        return result.popularity_score

    def test_midpoint_scores_half(self) -> None:
        assert self._popularity_score(7) == pytest.approx(0.5)

    def test_two_above_midpoint(self) -> None:
        # 1 / (1 + exp(-2 * 2)) ≈ 0.9820
        assert self._popularity_score(9) == pytest.approx(0.9820137900)

    def test_two_below_midpoint(self) -> None:
        # 1 / (1 + exp(-2 * -2)) ≈ 0.0180
        assert self._popularity_score(5) == pytest.approx(0.0179862100)

    def test_popularity_adjustment_is_applied(self) -> None:
        with_adj = _hymn(1, popularity=5, popularity_adjustment=2)
        baseline = _hymn(2, popularity=7, popularity_adjustment=None)

        results = score_hymns(
            [with_adj, baseline], [], REF_SUNDAY, "general", ZERO_NOISE
        )
        by_id = {s.hymn.id: s for s in results}

        assert by_id[1].adj_popularity == 7
        assert by_id[1].popularity_score == pytest.approx(by_id[2].popularity_score)

    def test_blank_popularity_adjustment_contributes_zero(self) -> None:
        hymn = _hymn(1, popularity=7, popularity_adjustment=None)

        [result] = score_hymns([hymn], [], REF_SUNDAY, "general", ZERO_NOISE)

        assert result.adj_popularity == 7


class TestRecencyNormalization:
    def test_at_cap_scores_one(self) -> None:
        hymn = _hymn(1)
        history = [_entry(hymn, _weeks_before(REF_SUNDAY, 52))]

        [result] = score_hymns([hymn], history, REF_SUNDAY, "general", ZERO_NOISE)

        assert result.weeks_since == 52
        assert result.recency_score == pytest.approx(1.0)

    def test_beyond_cap_is_capped(self) -> None:
        hymn = _hymn(1)
        history = [_entry(hymn, _weeks_before(REF_SUNDAY, 100))]

        [result] = score_hymns([hymn], history, REF_SUNDAY, "general", ZERO_NOISE)

        assert result.weeks_since == 100
        assert result.recency_score == pytest.approx(1.0)

    def test_half_cap_scores_half(self) -> None:
        hymn = _hymn(1)
        history = [_entry(hymn, _weeks_before(REF_SUNDAY, 26))]

        [result] = score_hymns([hymn], history, REF_SUNDAY, "general", ZERO_NOISE)

        assert result.recency_score == pytest.approx(0.5)

    def test_never_sung_scores_one_with_none_weeks(self) -> None:
        hymn = _hymn(1)

        [result] = score_hymns([hymn], [], REF_SUNDAY, "general", ZERO_NOISE)

        assert result.weeks_since is None
        assert result.recency_score == pytest.approx(1.0)


class TestNoiseBound:
    def test_noise_stays_within_amplitude(self) -> None:
        hymn = _hymn(1, popularity=7)
        history = [_entry(hymn, _weeks_before(REF_SUNDAY, 26))]
        config = ScoringConfig(noise_amplitude=0.15)
        base = (
            config.popularity_weight * 0.5
            + (1 - config.popularity_weight) * 0.5
        )

        rng = random.Random(42)
        for _ in range(500):
            [result] = score_hymns(
                [hymn], history, REF_SUNDAY, "general", config, rng=rng
            )
            assert abs(result.score - base) <= config.noise_amplitude + 1e-9

    def test_zero_noise_is_deterministic(self) -> None:
        hymn = _hymn(1, popularity=7)
        history = [_entry(hymn, _weeks_before(REF_SUNDAY, 26))]

        a = score_hymns([hymn], history, REF_SUNDAY, "general", ZERO_NOISE)
        b = score_hymns([hymn], history, REF_SUNDAY, "general", ZERO_NOISE)

        assert a[0].score == b[0].score


class TestReferenceDateEdgeCases:
    def test_sung_only_on_reference_sunday_treated_as_never(self) -> None:
        hymn = _hymn(1)
        history = [_entry(hymn, REF_SUNDAY)]

        [result] = score_hymns([hymn], history, REF_SUNDAY, "general", ZERO_NOISE)

        assert result.weeks_since is None
        assert result.recency_score == pytest.approx(1.0)

    def test_uses_earlier_date_when_also_sung_on_reference(self) -> None:
        hymn = _hymn(1)
        history = [
            _entry(hymn, _weeks_before(REF_SUNDAY, 20)),
            _entry(hymn, REF_SUNDAY),
        ]

        [result] = score_hymns([hymn], history, REF_SUNDAY, "general", ZERO_NOISE)

        assert result.weeks_since == 20


class TestRanking:
    def test_sorted_descending_by_score(self) -> None:
        low = _hymn(1, popularity=5)
        high = _hymn(2, popularity=10)
        mid = _hymn(3, popularity=7)

        result = score_hymns(
            [low, high, mid], [], REF_SUNDAY, "general", ZERO_NOISE
        )

        scores = [s.score for s in result]
        assert scores == sorted(scores, reverse=True)
        assert result[0].hymn.id == 2

    def test_result_length_matches_eligible_count(self) -> None:
        hymns = [
            _hymn(1),
            _hymn(2, flagged=True),
            _hymn(3, is_holiday=True, is_general=True),
            _hymn(4, is_general=False, is_sacrament=True),
            _hymn(5),
        ]

        result = score_hymns(hymns, [], REF_SUNDAY, "general", ZERO_NOISE)

        assert {s.hymn.id for s in result} == {1, 5}

    def test_scored_hymn_embeds_full_hymn(self) -> None:
        hymn = _hymn(1, name="Test Hymn", length="2:34")

        [result] = score_hymns([hymn], [], REF_SUNDAY, "general", ZERO_NOISE)

        assert isinstance(result, ScoredHymn)
        assert result.hymn is hymn
        assert result.hymn.name == "Test Hymn"
        assert result.hymn.length == "2:34"


class TestConfigOverride:
    def test_zero_cooldown_admits_recent_hymns(self) -> None:
        hymn = _hymn(1)
        history = [_entry(hymn, _weeks_before(REF_SUNDAY, 1))]
        config = ScoringConfig(cooldown_weeks=0, noise_amplitude=0.0)

        result = score_hymns([hymn], history, REF_SUNDAY, "general", config)

        assert [s.hymn.id for s in result] == [1]
        assert result[0].weeks_since == 1

    def test_custom_weight_shifts_balance(self) -> None:
        # Popularity-only: weight=1 means recency is ignored.
        old = _hymn(1, popularity=5)
        history = [_entry(old, _weeks_before(REF_SUNDAY, 52))]
        config = ScoringConfig(popularity_weight=1.0, noise_amplitude=0.0)

        [result] = score_hymns([old], history, REF_SUNDAY, "general", config)

        assert result.score == pytest.approx(result.popularity_score)
