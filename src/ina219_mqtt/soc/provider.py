"""State-of-charge lookup via open-circuit voltage linear interpolation."""


class SocOcvProvider:
    def __init__(self, ocv_map: dict) -> None:
        pairs = sorted(ocv_map.items(), key=lambda x: x[1])
        self._soc_vals = [p[0] for p in pairs]
        self._voltage_vals = [p[1] for p in pairs]

    def get_soc_from_voltage(self, cell_voltage: float) -> float:
        if cell_voltage >= self._voltage_vals[-1]:
            return 100.0
        if cell_voltage <= self._voltage_vals[0]:
            return 0.0
        for i in range(len(self._voltage_vals) - 1):
            v0, v1 = self._voltage_vals[i], self._voltage_vals[i + 1]
            if v0 <= cell_voltage <= v1:
                t = (cell_voltage - v0) / (v1 - v0)
                return self._soc_vals[i] + t * (self._soc_vals[i + 1] - self._soc_vals[i])
        return 0.0
