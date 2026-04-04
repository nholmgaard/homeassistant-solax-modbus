"""Unit tests for charge_planner estimation functions."""

import pytest

from custom_components.solax_modbus.charge_planner import estimate_grid_charge_needed, estimate_grid_export_available


# ---------------------------------------------------------------------------
# Basic scenarios
# ---------------------------------------------------------------------------


def test_solar_insufficient_requires_grid_charge() -> None:
    """Battery at 20%, want 80%, 10 kWh capacity, 1 kWh net solar → 5 kWh from grid."""
    # current = 2 kWh, target = 8 kWh, net solar = 3 - 2 = 1 kWh
    # deficit = 8 - 2 - 1 = 5 kWh
    result = estimate_grid_charge_needed(
        current_soc_pct=20,
        battery_capacity_kwh=10,
        target_soc_pct=80,
        projected_solar_kwh=3.0,
        projected_consumption_kwh=2.0,
    )
    assert result == 5.0


def test_solar_sufficient_returns_zero() -> None:
    """Enough solar to cover deficit — no grid charge needed."""
    # current = 2 kWh, target = 8 kWh, gap = 6 kWh, net solar = 9 - 2 = 7 kWh → covered
    result = estimate_grid_charge_needed(
        current_soc_pct=20,
        battery_capacity_kwh=10,
        target_soc_pct=80,
        projected_solar_kwh=9.0,
        projected_consumption_kwh=2.0,
    )
    assert result == 0.0


def test_solar_exactly_covers_deficit() -> None:
    """Net solar exactly equals the gap — result is 0.0, not negative."""
    # current = 2 kWh, target = 8 kWh, gap = 6 kWh, net solar = 8 - 2 = 6 kWh
    result = estimate_grid_charge_needed(
        current_soc_pct=20,
        battery_capacity_kwh=10,
        target_soc_pct=80,
        projected_solar_kwh=8.0,
        projected_consumption_kwh=2.0,
    )
    assert result == 0.0


def test_no_consumption_assumed() -> None:
    """Default projected_consumption_kwh=0 means all solar goes to the battery."""
    # current = 5 kWh, target = 9 kWh, gap = 4 kWh, solar = 2 kWh → 2 kWh from grid
    result = estimate_grid_charge_needed(
        current_soc_pct=50,
        battery_capacity_kwh=10,
        target_soc_pct=90,
        projected_solar_kwh=2.0,
    )
    assert result == 2.0


def test_already_at_or_above_target() -> None:
    """Battery already at target — returns 0.0 even without any solar."""
    result = estimate_grid_charge_needed(
        current_soc_pct=90,
        battery_capacity_kwh=10,
        target_soc_pct=80,
        projected_solar_kwh=0.0,
    )
    assert result == 0.0


def test_result_capped_at_battery_capacity() -> None:
    """Result is capped at battery_capacity_kwh (battery empty, huge consumption)."""
    # current = 0, target = 100%, capacity = 5 kWh
    # solar = 1, consumption = 10 → net solar = -9 kWh
    # raw deficit = 5 - 0 - (-9) = 14 kWh → capped at 5 kWh
    result = estimate_grid_charge_needed(
        current_soc_pct=0,
        battery_capacity_kwh=5,
        target_soc_pct=100,
        projected_solar_kwh=1.0,
        projected_consumption_kwh=10.0,
    )
    assert result == 5.0


def test_fractional_result_rounded_to_two_decimals() -> None:
    """Result is rounded to 2 decimal places."""
    # current = 1/3 * 10 kWh ≈ 3.333, target = 2/3 * 10 ≈ 6.667, solar=0
    result = estimate_grid_charge_needed(
        current_soc_pct=100 / 3,
        battery_capacity_kwh=10,
        target_soc_pct=200 / 3,
        projected_solar_kwh=0.0,
    )
    # deficit ≈ 3.333... → rounded to 3.33
    assert result == round(result, 2)
    assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_zero_solar_full_deficit_from_grid() -> None:
    """No solar at all — entire gap must come from grid."""
    result = estimate_grid_charge_needed(
        current_soc_pct=10,
        battery_capacity_kwh=10,
        target_soc_pct=100,
        projected_solar_kwh=0.0,
    )
    assert result == 9.0


def test_100_percent_current_soc() -> None:
    """Battery full — no grid charge needed regardless of target."""
    result = estimate_grid_charge_needed(
        current_soc_pct=100,
        battery_capacity_kwh=10,
        target_soc_pct=100,
        projected_solar_kwh=0.0,
    )
    assert result == 0.0


def test_target_equals_current_no_solar_returns_zero() -> None:
    """Target equals current — no charge needed."""
    result = estimate_grid_charge_needed(
        current_soc_pct=50,
        battery_capacity_kwh=10,
        target_soc_pct=50,
        projected_solar_kwh=0.0,
    )
    assert result == 0.0


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_raises_on_negative_capacity() -> None:
    with pytest.raises(ValueError, match="battery_capacity_kwh"):
        estimate_grid_charge_needed(50, -1, 80, 0)


def test_raises_on_zero_capacity() -> None:
    with pytest.raises(ValueError, match="battery_capacity_kwh"):
        estimate_grid_charge_needed(50, 0, 80, 0)


def test_raises_on_soc_above_100() -> None:
    with pytest.raises(ValueError, match="current_soc_pct"):
        estimate_grid_charge_needed(101, 10, 80, 0)


def test_raises_on_negative_soc() -> None:
    with pytest.raises(ValueError, match="current_soc_pct"):
        estimate_grid_charge_needed(-1, 10, 80, 0)


def test_raises_on_target_above_100() -> None:
    with pytest.raises(ValueError, match="target_soc_pct"):
        estimate_grid_charge_needed(50, 10, 101, 0)


def test_raises_on_negative_solar() -> None:
    with pytest.raises(ValueError, match="projected_solar_kwh"):
        estimate_grid_charge_needed(50, 10, 80, -1)


def test_raises_on_negative_consumption() -> None:
    with pytest.raises(ValueError, match="projected_consumption_kwh"):
        estimate_grid_charge_needed(50, 10, 80, 0, -1)


# ===========================================================================
# estimate_grid_export_available
# ===========================================================================


def test_export_basic_surplus() -> None:
    """Battery at 80%, floor 20%, net solar fills to 100% → 8 kWh exportable."""
    # current=8 kWh, net=3-1=2 kWh → projected=10 (capped), floor=2 → surplus=8
    result = estimate_grid_export_available(
        current_soc_pct=80,
        battery_capacity_kwh=10,
        min_soc_pct=20,
        projected_solar_kwh=3.0,
        projected_consumption_kwh=1.0,
    )
    assert result == 8.0


def test_export_below_floor_returns_zero() -> None:
    """Battery already below the self-sufficiency floor — no export available."""
    result = estimate_grid_export_available(
        current_soc_pct=50,
        battery_capacity_kwh=10,
        min_soc_pct=60,
        projected_solar_kwh=0.0,
    )
    assert result == 0.0


def test_export_solar_brings_above_floor() -> None:
    """Battery below floor but solar lifts it above — surplus available."""
    # current=3 kWh, floor=5 kWh, net solar=4 kWh → projected=7, surplus=2
    result = estimate_grid_export_available(
        current_soc_pct=30,
        battery_capacity_kwh=10,
        min_soc_pct=50,
        projected_solar_kwh=4.0,
    )
    assert result == 2.0


def test_export_projected_capped_at_capacity() -> None:
    """Overflow solar is capped at battery capacity, not double-counted."""
    # current=9 kWh, net solar=5 kWh → would be 14, capped at 10, floor=2 → surplus=8
    result = estimate_grid_export_available(
        current_soc_pct=90,
        battery_capacity_kwh=10,
        min_soc_pct=20,
        projected_solar_kwh=5.0,
    )
    assert result == 8.0


def test_export_zero_floor_full_projected_capacity() -> None:
    """Floor of 0% — entire projected capacity is available for export."""
    # current=5 kWh, net solar=3 kWh → projected=8, floor=0 → surplus=8
    result = estimate_grid_export_available(
        current_soc_pct=50,
        battery_capacity_kwh=10,
        min_soc_pct=0,
        projected_solar_kwh=3.0,
    )
    assert result == 8.0


def test_export_100_floor_returns_zero() -> None:
    """Floor of 100% — nothing can be exported (must keep battery full)."""
    result = estimate_grid_export_available(
        current_soc_pct=100,
        battery_capacity_kwh=10,
        min_soc_pct=100,
        projected_solar_kwh=5.0,
    )
    assert result == 0.0


def test_export_negative_net_solar_reduces_surplus() -> None:
    """Consumption exceeding solar shrinks the exportable amount."""
    # current=8 kWh, net=-2 kWh → projected=6, floor=2 → surplus=4
    result = estimate_grid_export_available(
        current_soc_pct=80,
        battery_capacity_kwh=10,
        min_soc_pct=20,
        projected_solar_kwh=1.0,
        projected_consumption_kwh=3.0,
    )
    assert result == 4.0


def test_export_consumption_drains_below_floor() -> None:
    """High consumption pulls projected level below floor — no export."""
    # current=5 kWh, net=-4 kWh → projected=1, floor=3 → surplus=-2 → 0
    result = estimate_grid_export_available(
        current_soc_pct=50,
        battery_capacity_kwh=10,
        min_soc_pct=30,
        projected_solar_kwh=1.0,
        projected_consumption_kwh=5.0,
    )
    assert result == 0.0


def test_export_result_rounded_to_two_decimals() -> None:
    result = estimate_grid_export_available(
        current_soc_pct=100 / 3,
        battery_capacity_kwh=10,
        min_soc_pct=0,
        projected_solar_kwh=0.0,
    )
    assert result == round(result, 2)


# Input validation for estimate_grid_export_available


def test_export_raises_on_invalid_min_soc() -> None:
    with pytest.raises(ValueError, match="min_soc_pct"):
        estimate_grid_export_available(50, 10, 101, 0)


def test_export_raises_on_negative_min_soc() -> None:
    with pytest.raises(ValueError, match="min_soc_pct"):
        estimate_grid_export_available(50, 10, -1, 0)


def test_export_raises_on_negative_capacity() -> None:
    with pytest.raises(ValueError, match="battery_capacity_kwh"):
        estimate_grid_export_available(50, -1, 20, 0)


def test_export_raises_on_invalid_current_soc() -> None:
    with pytest.raises(ValueError, match="current_soc_pct"):
        estimate_grid_export_available(110, 10, 20, 0)
