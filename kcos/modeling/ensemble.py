from ..domain import Forecast


class ForecastEnsemble:
    def __init__(self, weights=None):
        self.weights = weights or {"kronos": .4, "momentum": .2, "reversal": .1, "regime": .2, "cross_asset": .1}

    def combine(self, instrument, horizon, components, calibration_haircut=1.0, include=None):
        include = set(include) if include else None
        total = weight = conf = 0.0
        used = {}
        for name, item in components.items():
            if include is not None and name not in include:
                continue
            w = float(self.weights.get(name, 0))
            if not item or w <= 0:
                continue
            total += w * float(item.get("expected_return", 0))
            conf += w * float(item.get("confidence", .5))
            weight += w
            used[name] = item
        if weight == 0:
            return Forecast(instrument, horizon, 0, .5, 0, source="ensemble")
        expected = total / weight
        confidence = max(.01, min(.99, conf / weight * calibration_haircut))
        direction_probability = max(.01, min(.99, .5 + expected * 10))
        return Forecast(instrument, horizon, expected, direction_probability, confidence, source="ensemble", metadata={"components": used})
