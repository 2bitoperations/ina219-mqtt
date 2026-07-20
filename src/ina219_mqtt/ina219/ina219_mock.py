import logging
import random

from .ina219_interface import INA219Interface

_LOGGER = logging.getLogger(__name__)


class MockINA219(INA219Interface):
    def __init__(self, i2c_bus=1, addr=0x40):
        _LOGGER.debug("MockINA219 started for bus=%d, addr=%d", i2c_bus, addr)

    def getShuntVoltage_mV(self):
        return random.randint(20, 200)

    def getBusVoltage_V(self):
        return random.randint(900, 1243) * 0.01

    def getCurrent_mA(self):
        return random.randint(-500, 1500)

    def getPower_W(self):
        return random.randint(-4, 15)

    def close(self) -> None:
        pass
