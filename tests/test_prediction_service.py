from datetime import date

import pytest

from kronos_app.backend.services import prediction_service as ps_module

pd = ps_module.pd

from kronos_app.backend.schemas import PredictionRequest
class DummyRunner:
    def predict_returns(self, history, horizons, **kwargs):
        return {
            1: {"returns": [0.02], "probability": [0.8]},
            3: {"returns": [0.01, -0.02, 0.03], "probability": [0.6, 0.4, 0.7]},
        }


def test_prediction_service_formats_predictions_and_evaluations(monkeypatch):
    history_index = pd.bdate_range("2025-09-29", periods=10)
    history = pd.DataFrame({"close": [10 + i * 0.1 for i in range(len(history_index))]}, index=history_index)

    future_map = {
        1: pd.Series([0.03], index=pd.bdate_range("2025-10-13", periods=1)),
        3: pd.Series([0.02, -0.01, 0.04], index=pd.bdate_range("2025-10-13", periods=3)),
    }

    def fake_initialize(cls):
        return DummyRunner()

    monkeypatch.setattr(ps_module.KronosRunner, "initialize", classmethod(fake_initialize))
    monkeypatch.setattr(ps_module, "fetch_daily_bars", lambda *_, **__: history)
    monkeypatch.setattr(ps_module, "slice_history", lambda *_args, horizon, **_kwargs: (history, future_map[horizon]))

    request = PredictionRequest(
        ticker="600519.SH",
        horizons=[1, 3],
        evaluation_anchor=date(2025, 10, 10),
        run_evaluation=True,
    )

    service = ps_module.PredictionService()
    prediction = service.predict(request)

    assert prediction.metadata["history_rows"] == len(history)
    assert prediction.daily_changes["2025-10-13"]["return"] == pytest.approx(0.02)
    assert prediction.daily_changes["2025-10-14"]["return"] == pytest.approx(-0.02)
    assert prediction.horizon_returns[1]["2025-10-13"] == pytest.approx(0.02)
    assert prediction.horizon_returns[3]["2025-10-14"] == pytest.approx(-0.02)

    evaluation = service.evaluate(request, prediction)
    accuracy_map = {item.horizon_days: item.accuracy for item in evaluation}
    total_map = {item.horizon_days: item.total_cases for item in evaluation}

    assert accuracy_map[1] == pytest.approx(1.0)
    assert accuracy_map[3] == pytest.approx(1.0)
    assert total_map[3] == 3
