import pytest

from backend.cpm.schedule import PaceProfile
from backend.db.pace_profile import compute_pace_profile_update


def test_complete_event_updates_pace_coefficient_via_ema():
    profile = PaceProfile(pace_coefficient=1.0, skip_rate_by_category={})

    updated = compute_pace_profile_update(
        profile,
        category="実装",
        event_type="complete",
        actual_duration_hours=4.0,
        original_estimated_duration_hours=2.0,
    )

    # 0.3 * (4.0/2.0) + 0.7 * 1.0 = 1.3
    assert updated.pace_coefficient == pytest.approx(1.3)
    # completeはスキップではないので指標は0
    assert updated.skip_rate_by_category["実装"] == 0.0


def test_skip_event_does_not_change_pace_coefficient():
    profile = PaceProfile(pace_coefficient=0.8, skip_rate_by_category={})

    updated = compute_pace_profile_update(
        profile,
        category="調査",
        event_type="skip",
        actual_duration_hours=None,
        original_estimated_duration_hours=3.0,
    )

    assert updated.pace_coefficient == 0.8
    # 0.3 * 1(skip) + 0.7 * 0.0 = 0.3
    assert updated.skip_rate_by_category["調査"] == 0.3


def test_skip_rate_moves_toward_zero_after_repeated_completions():
    profile = PaceProfile(pace_coefficient=1.0, skip_rate_by_category={"調査": 0.6})

    updated = compute_pace_profile_update(
        profile,
        category="調査",
        event_type="complete",
        actual_duration_hours=2.0,
        original_estimated_duration_hours=2.0,
    )

    # 0.3 * 0(not skip) + 0.7 * 0.6 = 0.42
    assert updated.skip_rate_by_category["調査"] == 0.42


def test_zero_original_estimate_does_not_divide_by_zero():
    profile = PaceProfile(pace_coefficient=1.0, skip_rate_by_category={})

    updated = compute_pace_profile_update(
        profile,
        category="実装",
        event_type="complete",
        actual_duration_hours=1.0,
        original_estimated_duration_hours=0.0,
    )

    assert updated.pace_coefficient == 1.0


def test_other_categories_are_preserved():
    profile = PaceProfile(pace_coefficient=1.0, skip_rate_by_category={"設計": 0.5})

    updated = compute_pace_profile_update(
        profile,
        category="実装",
        event_type="skip",
        actual_duration_hours=None,
        original_estimated_duration_hours=2.0,
    )

    assert updated.skip_rate_by_category["設計"] == 0.5
    assert updated.skip_rate_by_category["実装"] == 0.3
