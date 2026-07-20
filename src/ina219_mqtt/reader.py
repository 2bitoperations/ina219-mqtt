"""Read INA219 and compute UPS state."""

from .ina219.config import get_ina219_class
from .ina219_wrapper import INA219Wrapper
from .soc.provider import SocOcvProvider

DEFAULT_OCV = {0: 2.5, 10: 3.0, 20: 3.2, 30: 3.4, 40: 3.5, 50: 3.6,
               60: 3.7, 70: 3.8, 80: 3.9, 90: 4.0, 100: 4.2}


class INA219Reader:
    def __init__(
        self,
        bus: int,
        addr: int,
        batteries_count: int = 3,
        battery_capacity: int = 3000,
        max_soc: int = 91,
        sma_samples: int = 5,
        min_online_current: float = -100,
        min_charging_current: float = 55,
    ) -> None:
        INA219 = get_ina219_class()
        ina219 = INA219(i2c_bus=bus, addr=addr)
        self._wrapper = INA219Wrapper(ina219, sma_samples)
        self._soc_provider = SocOcvProvider(DEFAULT_OCV)
        self._batteries_count = batteries_count
        self._battery_capacity = battery_capacity
        self._max_soc = max_soc
        self._min_online_current = min_online_current
        self._min_charging_current = min_charging_current

    def read(self) -> dict:
        w = self._wrapper
        w.measureINAValues()

        bus_voltage = w.getBusVoltageSMA_V()
        shunt_voltage = w.getShuntVoltageSMA_mV() / 1000
        total_voltage = bus_voltage + shunt_voltage
        current_ma = w.getCurrentSMA_mA()

        smooth_bus_voltage = w.getBusVoltageSMAx2_V()
        smooth_current_ma = w.getCurrentSMAx2_mA()

        cell_voltage = smooth_bus_voltage / self._batteries_count
        soc = min(self._soc_provider.get_soc_from_voltage(cell_voltage), self._max_soc)

        power = bus_voltage * (current_ma / 1000)
        current_ma_rounded = round(current_ma, 1)
        online = current_ma_rounded > self._min_online_current
        charging = current_ma_rounded > self._min_charging_current

        remaining_capacity_wh = None
        remaining_time_h = None
        remaining_capacity_mah = (self._battery_capacity / 100.0) * soc
        remaining_capacity_wh = round((remaining_capacity_mah * total_voltage) / 1000, 2)
        if not online and smooth_current_ma != 0:
            smooth_power = smooth_bus_voltage * (smooth_current_ma / 1000)
            if smooth_power < 0:
                remaining_time_h = round(remaining_capacity_wh / (-smooth_power), 1)

        return {
            "voltage": round(total_voltage, 2),
            "current": round(current_ma / 1000, 3),
            "power": round(power, 2),
            "soc": round(soc, 1),
            "remaining_capacity": remaining_capacity_wh,
            "remaining_time": remaining_time_h,
            "online": online,
            "charging": charging,
        }

    def close(self) -> None:
        self._wrapper._ina219.close()
