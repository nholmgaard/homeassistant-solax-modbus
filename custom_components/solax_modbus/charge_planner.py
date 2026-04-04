"""
Grid charge/export estimation for hybrid inverters.

Two complementary planning functions:

* ``estimate_grid_charge_needed`` — how many kWh to import from the grid to
  reach a target SoC given projected solar and consumption.

* ``estimate_grid_export_available`` — how many kWh can be exported (sold) to
  the grid without the battery falling below a self-sufficiency floor.
"""

from __future__ import annotations


def _validate_common(
    current_soc_pct: float,
    battery_capacity_kwh: float,
    projected_solar_kwh: float,
    projected_consumption_kwh: float,
) -> None:
    if battery_capacity_kwh <= 0:
        raise ValueError(f"battery_capacity_kwh must be positive, got {battery_capacity_kwh}")
    if not (0.0 <= current_soc_pct <= 100.0):
        raise ValueError(f"current_soc_pct must be 0–100, got {current_soc_pct}")
    if projected_solar_kwh < 0:
        raise ValueError(f"projected_solar_kwh must be >= 0, got {projected_solar_kwh}")
    if projected_consumption_kwh < 0:
        raise ValueError(f"projected_consumption_kwh must be >= 0, got {projected_consumption_kwh}")


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

        Same scenario but 9 kWh of solar forecast — grid not needed::

            >>> estimate_grid_charge_needed(20, 10, 80, 9, 2)
            0.0
    """
    _validate_common(current_soc_pct, battery_capacity_kwh, projected_solar_kwh, projected_consumption_kwh)
    if not (0.0 <= target_soc_pct <= 100.0):
        raise ValueError(f"target_soc_pct must be 0–100, got {target_soc_pct}")

    current_kwh = current_soc_pct / 100.0 * battery_capacity_kwh
    target_kwh = target_soc_pct / 100.0 * battery_capacity_kwh
    net_solar_kwh = projected_solar_kwh - projected_consumption_kwh
    deficit_kwh = target_kwh - current_kwh - net_solar_kwh
    return round(max(0.0, min(deficit_kwh, battery_capacity_kwh)), 2)


def estimate_grid_export_available(
    current_soc_pct: float,
    battery_capacity_kwh: float,
    min_soc_pct: float,
    projected_solar_kwh: float,
    projected_consumption_kwh: float = 0.0,
) -> float:
    """Estimate kWh that can be exported to the grid without compromising self-sufficiency.

    Computes the energy headroom above ``min_soc_pct`` after absorbing the net
    solar surplus (solar minus consumption).  Any headroom above the floor can
    be actively discharged and sold to the grid.

    Args:
        current_soc_pct:        Current battery state-of-charge in percent (0–100).
        battery_capacity_kwh:   Usable battery capacity in kWh.
        min_soc_pct:            Minimum SoC to preserve for self-sufficiency,
                                in percent (0–100).  Energy below this floor is
                                not available for export.
        projected_solar_kwh:    Expected solar (and other renewable) generation
                                between now and the target time, in kWh.
        projected_consumption_kwh:
                                Expected house load between now and the target
                                time, in kWh.  Defaults to 0 (conservative —
                                all solar charges the battery first).

    Returns:
        kWh available for grid export, or 0.0 if the battery will be at or
        below the self-sufficiency floor.  The result is clamped to
        [0, battery_capacity_kwh] and rounded to 2 decimal places.

    Notes:
        * Battery charge capacity is respected: if ``current_kwh + net_solar``
          would exceed full capacity, the projected level is capped there.
          Solar that overflows the battery is already exported passively and
          is not double-counted here.
        * Inverter/round-trip losses are not modelled; scale
          ``projected_solar_kwh`` down or raise ``min_soc_pct`` to add a margin.
        * The function is pure and free of HA dependencies.

    Examples:
        Battery at 80 %, 10 kWh capacity, self-sufficiency floor 20 %.
        Expecting 3 kWh solar, 1 kWh consumption (net = 2 kWh)::

            >>> estimate_grid_export_available(80, 10, 20, 3, 1)
            8.0  # current=8 kWh, +net 2 kWh → 10 (capped), floor=2 kWh → 8 kWh

        Battery at 50 %, floor 60 % — already below floor, no export::

            >>> estimate_grid_export_available(50, 10, 60, 0)
            0.0
    """
    _validate_common(current_soc_pct, battery_capacity_kwh, projected_solar_kwh, projected_consumption_kwh)
    if not (0.0 <= min_soc_pct <= 100.0):
        raise ValueError(f"min_soc_pct must be 0–100, got {min_soc_pct}")

    current_kwh = current_soc_pct / 100.0 * battery_capacity_kwh
    floor_kwh = min_soc_pct / 100.0 * battery_capacity_kwh
    net_solar_kwh = projected_solar_kwh - projected_consumption_kwh
    # Cap at full capacity — overflow solar is already exported passively
    projected_kwh = min(current_kwh + net_solar_kwh, battery_capacity_kwh)
    surplus_kwh = projected_kwh - floor_kwh
    return round(max(0.0, min(surplus_kwh, battery_capacity_kwh)), 2)
