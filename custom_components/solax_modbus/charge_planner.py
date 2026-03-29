"""
Grid charge estimation for hybrid inverters.

Answers: given the battery's current state and projected solar/load between
now and a target time, how many kWh need to be imported from the grid to
reach the desired state-of-charge?
"""

from __future__ import annotations


def estimate_grid_charge_needed(
    current_soc_pct: float,
    battery_capacity_kwh: float,
    target_soc_pct: float,
    projected_solar_kwh: float,
    projected_consumption_kwh: float = 0.0,
) -> float:
    """Estimate kWh that must be charged from the grid to hit target SoC.

    Args:
        current_soc_pct:        Current battery state-of-charge in percent (0–100).
        battery_capacity_kwh:   Usable battery capacity in kWh.
        target_soc_pct:         Desired SoC at the target time, in percent (0–100).
        projected_solar_kwh:    Expected solar (and other renewable) generation
                                between now and the target time, in kWh.
        projected_consumption_kwh:
                                Expected house load between now and the target
                                time, in kWh.  Defaults to 0 (conservative —
                                all solar goes to the battery).

    Returns:
        kWh that must be imported from the grid, or 0.0 if solar is sufficient.
        The result is clamped to [0, battery_capacity_kwh] and rounded to 2
        decimal places.

    Notes:
        * Charging/inverter losses are not modelled; callers may scale
          ``projected_solar_kwh`` down or the result up to account for them.
        * The function is pure and free of HA dependencies so it is easy to
          unit-test and reuse outside of Home Assistant.

    Examples:
        Battery at 20 %, 10 kWh capacity, want 80 % by tonight.
        Expecting 3 kWh of solar, 2 kWh of consumption (net solar = 1 kWh)::

            >>> estimate_grid_charge_needed(20, 10, 80, 3, 2)
            5.0   # need 6 kWh gap, 1 kWh from solar, so 5 kWh from grid

        Same scenario but 7 kWh of solar forecast — grid not needed::

            >>> estimate_grid_charge_needed(20, 10, 80, 7, 2)
            0.0
    """
    if battery_capacity_kwh <= 0:
        raise ValueError(f"battery_capacity_kwh must be positive, got {battery_capacity_kwh}")
    if not (0.0 <= current_soc_pct <= 100.0):
        raise ValueError(f"current_soc_pct must be 0–100, got {current_soc_pct}")
    if not (0.0 <= target_soc_pct <= 100.0):
        raise ValueError(f"target_soc_pct must be 0–100, got {target_soc_pct}")
    if projected_solar_kwh < 0:
        raise ValueError(f"projected_solar_kwh must be >= 0, got {projected_solar_kwh}")
    if projected_consumption_kwh < 0:
        raise ValueError(f"projected_consumption_kwh must be >= 0, got {projected_consumption_kwh}")

    current_kwh = current_soc_pct / 100.0 * battery_capacity_kwh
    target_kwh = target_soc_pct / 100.0 * battery_capacity_kwh
    net_solar_kwh = projected_solar_kwh - projected_consumption_kwh
    deficit_kwh = target_kwh - current_kwh - net_solar_kwh
    return round(max(0.0, min(deficit_kwh, battery_capacity_kwh)), 2)
