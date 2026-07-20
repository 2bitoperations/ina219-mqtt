"""Wrapper for ina219 lib — simple-moving-average smoothing over a ring buffer."""

from collections import deque

from .ina219.ina219_interface import INA219Interface

COEF_SMAx2 = 2


def _mean(values) -> float:
    lst = list(values)
    return sum(lst) / len(lst) if lst else 0.0


class INA219Wrapper:
    def __init__(self, ina219: INA219Interface, samples_cnt: int) -> None:
        self._ina219 = ina219
        self._bus_voltage_buf: deque[float] = deque(maxlen=samples_cnt * COEF_SMAx2)
        self._shunt_voltage_buf: deque[float] = deque(maxlen=samples_cnt)
        self._current_buf: deque[float] = deque(maxlen=samples_cnt * COEF_SMAx2)

    def measureINAValues(self) -> None:
        self._current_buf.append(self._ina219.getCurrent_mA())
        self._bus_voltage_buf.append(self._ina219.getBusVoltage_V())
        self._shunt_voltage_buf.append(self._ina219.getShuntVoltage_mV())

    def getCurrentSMA_mA(self) -> float:
        return _mean(self._current_buf)

    def getBusVoltageSMA_V(self) -> float:
        return _mean(self._bus_voltage_buf)

    def getShuntVoltageSMA_mV(self) -> float:
        return _mean(self._shunt_voltage_buf)

    def getCurrentSMAx2_mA(self) -> float:
        return _mean(self._getBufTail(self._current_buf))

    def getBusVoltageSMAx2_V(self) -> float:
        return _mean(self._getBufTail(self._bus_voltage_buf))

    def _getBufTail(self, buf: deque) -> list:
        """Return the most-recent half of the buffer (the SMAx2 window)."""
        lst = list(buf)
        slice_start = len(lst) - len(lst) // COEF_SMAx2
        return lst[slice_start:]
