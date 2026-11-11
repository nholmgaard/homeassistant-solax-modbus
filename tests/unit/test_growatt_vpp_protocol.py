import pytest

from custom_components.solax_modbus.const import REG_HOLDING, REG_INPUT, REGISTER_S16, REGISTER_S32, REGISTER_U16
from custom_components.solax_modbus.plugin_growatt import BUTTON_TYPES, SENSOR_TYPES, plugin_instance, value_function_vpp_protocol_version


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [(200, "V2.00"), (201, "V2.01"), (205, "V2.05")],
)
def test_vpp_protocol_version_format(raw_value: int, expected: str) -> None:
    assert value_function_vpp_protocol_version(raw_value, None, {}) == expected


def test_vpp_protocol_version_sensor_register() -> None:
    description = next(description for description in SENSOR_TYPES if description.key == "vpp_protocol_version")

    assert description.name == "VPP Protocol Version"
    assert description.register == 30099
    assert description.register_type == REG_HOLDING
    assert description.register_data_type == REGISTER_U16


def test_vpp_phase_and_meter_sensors_registers() -> None:
    expected = {
        "grid_voltage_ab_vpp": (31106, REG_INPUT, REGISTER_U16),
        "grid_voltage_bc_vpp": (31107, REG_INPUT, REGISTER_U16),
        "grid_voltage_ca_vpp": (31108, REG_INPUT, REGISTER_U16),
        "grid_current_l1_vpp": (31109, REG_INPUT, REGISTER_S16),
        "grid_current_l2_vpp": (31110, REG_INPUT, REGISTER_S16),
        "grid_current_l3_vpp": (31111, REG_INPUT, REGISTER_S16),
        "meter_power_vpp": (31112, REG_INPUT, REGISTER_S32),
    }

    descriptions = {description.key: description for description in SENSOR_TYPES}
    for key, (register, register_type, data_type) in expected.items():
        description = descriptions[key]
        assert description.register == register
        assert description.register_type == register_type
        assert description.register_data_type == data_type
        assert description.scale == 0.1


def test_vpp_battery_wakeup_button() -> None:
    button = next(button for button in BUTTON_TYPES if button.key == "battery_wakeup")

    assert button.name == "Battery Wake Up"
    assert button.register == 30495
    assert button.command == 1
    assert plugin_instance.wakeupButton() == "battery_wakeup"
