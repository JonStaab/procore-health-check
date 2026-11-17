import json
from datetime import date
from pathlib import Path

from health_check import metrics

TODAY = date(2026, 11, 16)
DATA = Path(__file__).resolve().parent.parent / "sample_data"


def load(name):
    return json.loads((DATA / name).read_text())


def test_rfi_summary_on_sample_data():
    s = metrics.summarize(load("rfis.json"), "RFIs", TODAY)
    assert s.total == 15          # draft excluded
    assert s.open == 7
    assert s.overdue == 4         # due dates in the past, still open
    assert s.missing_due == 1
    assert s.avg_days_to_close == 10.0   # (5+12+9+15+6+11+8+14) / 8
    assert s.oldest_open_days == 30
    assert s.open_by_owner["Harbor Design Group (Architect)"] == 4
    assert s.overdue_by_owner["Harbor Design Group (Architect)"] == 3
    assert s.overdue_by_owner["Tidewater MEP Engineers"] == 1


def test_submittal_status_objects_and_resubmits():
    s = metrics.summarize(load("submittals.json"), "Submittals", TODAY)
    assert s.total == 9           # draft excluded
    assert s.open == 5            # revise and resubmit counts as open
    assert s.overdue == 3
    assert s.missing_due == 1


def test_score_is_explainable_and_bounded():
    rfis = metrics.summarize(load("rfis.json"), "RFIs", TODAY)
    subs = metrics.summarize(load("submittals.json"), "Submittals", TODAY)
    h = metrics.health_score(rfis, subs)
    assert 0 <= h.score <= 100
    assert h.score == 100 - sum(p for _, p in h.deductions)
    assert h.grade in {"Healthy", "Watch", "At Risk"}


def test_clean_project_scores_healthy():
    clean = [{"status": "closed", "initiated_at": "2026-11-01", "closed_at": "2026-11-04"}]
    s = metrics.summarize(clean, "RFIs", TODAY)
    h = metrics.health_score(s, metrics.summarize([], "Submittals", TODAY))
    assert h.score == 100 and h.grade == "Healthy"
    assert "moving well" in metrics.recommendations(s, metrics.summarize([], "S", TODAY))[0]


def test_recommendations_capped_at_three():
    rfis = metrics.summarize(load("rfis.json"), "RFIs", TODAY)
    subs = metrics.summarize(load("submittals.json"), "Submittals", TODAY)
    recs = metrics.recommendations(rfis, subs)
    assert 1 <= len(recs) <= 3
    assert "past due" in recs[0]
    assert "3 of them sit with Harbor Design Group" in recs[0]
