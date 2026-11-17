"""Turn raw RFI and submittal records into adoption health metrics.

Everything here is pure Python with no network calls, so it can be tested
against sample data. Field names from the Procore API are mapped in one place
(FIELD_CANDIDATES) because the exact keys can differ by endpoint version.
Run `python -m health_check dump` against your sandbox to confirm them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from statistics import mean
from typing import Any, Iterable

FIELD_CANDIDATES = {
    "created": ["initiated_at", "created_at"],
    "closed": ["closed_at", "time_resolved", "date_closed", "closed_date"],
    "due": ["due_date", "required_on_site_date"],
    "status": ["status"],
    "ball_in_court": ["ball_in_court"],
}

CLOSED_WORDS = {"closed", "approved", "approved as noted", "void"}
DRAFT_WORDS = {"draft"}


def _first(record: dict, key: str) -> Any:
    for name in FIELD_CANDIDATES[key]:
        value = record.get(name)
        if value not in (None, "", []):
            return value
    return None


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        # Procore sends timestamps in UTC; convert to local time so an RFI created
        # at 7:30 PM Eastern counts as today, not tomorrow.
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        return parsed.date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _status(record: dict) -> str:
    value = _first(record, "status")
    if isinstance(value, dict):  # submittals return {"name": "Open", ...}
        value = value.get("name") or value.get("status")
    return str(value or "").strip().lower()


def _ball_in_court_names(record: dict) -> list[str]:
    value = _first(record, "ball_in_court")
    if not value:
        return []
    items = value if isinstance(value, list) else [value]
    names = []
    for item in items:
        if isinstance(item, dict):
            names.append(item.get("name") or item.get("login") or "Unknown")
        else:
            names.append(str(item))
    return names


@dataclass
class ItemStats:
    label: str
    total: int = 0
    open: int = 0
    overdue: int = 0
    missing_due: int = 0
    avg_days_to_close: float | None = None
    oldest_open_days: int | None = None
    open_by_owner: dict[str, int] = field(default_factory=dict)
    overdue_by_owner: dict[str, int] = field(default_factory=dict)

    @property
    def overdue_rate(self) -> float:
        return self.overdue / self.open if self.open else 0.0

    @property
    def missing_due_rate(self) -> float:
        return self.missing_due / self.open if self.open else 0.0


def summarize(records: Iterable[dict], label: str, today: date) -> ItemStats:
    stats = ItemStats(label=label)
    close_times: list[int] = []
    open_ages: list[int] = []

    for record in records:
        status = _status(record)
        if status in DRAFT_WORDS:
            continue
        stats.total += 1
        created = _to_date(_first(record, "created"))
        closed = _to_date(_first(record, "closed"))
        due = _to_date(_first(record, "due"))
        is_closed = status in CLOSED_WORDS or closed is not None

        if is_closed:
            if created and closed and closed >= created:
                close_times.append((closed - created).days)
            continue

        stats.open += 1
        if created:
            open_ages.append((today - created).days)
        overdue = due is not None and due < today
        if due is None:
            stats.missing_due += 1
        elif overdue:
            stats.overdue += 1
        for name in _ball_in_court_names(record):
            stats.open_by_owner[name] = stats.open_by_owner.get(name, 0) + 1
            if overdue:
                stats.overdue_by_owner[name] = stats.overdue_by_owner.get(name, 0) + 1

    stats.avg_days_to_close = round(mean(close_times), 1) if close_times else None
    stats.oldest_open_days = max(open_ages) if open_ages else None
    return stats


@dataclass
class HealthResult:
    score: int
    grade: str
    deductions: list[tuple[str, int]]


def health_score(rfis: ItemStats, submittals: ItemStats, target_rfi_days: int = 7) -> HealthResult:
    """Simple, explainable score out of 100. Each deduction is listed so a
    customer can see exactly why the score is what it is."""
    deductions: list[tuple[str, int]] = []

    def take(reason: str, points: float) -> None:
        points = round(points)
        if points > 0:
            deductions.append((reason, points))

    take("Overdue RFIs", rfis.overdue_rate * 35)
    take("Overdue submittals", submittals.overdue_rate * 30)
    if rfis.avg_days_to_close is not None and rfis.avg_days_to_close > target_rfi_days:
        take("Slow RFI turnaround", min(20, (rfis.avg_days_to_close - target_rfi_days) * 2))
    missing = (rfis.missing_due + submittals.missing_due) / max(1, rfis.open + submittals.open)
    take("Open items without due dates", missing * 15)

    score = max(0, 100 - sum(p for _, p in deductions))
    grade = "Healthy" if score >= 80 else "Watch" if score >= 60 else "At Risk"
    return HealthResult(score=score, grade=grade, deductions=sorted(deductions, key=lambda d: -d[1]))


def recommendations(rfis: ItemStats, submittals: ItemStats, target_rfi_days: int = 7) -> list[str]:
    """Rule based advice, written the way a CSE would say it to a small GC."""
    recs: list[tuple[int, str]] = []

    if rfis.overdue:
        top = max(rfis.overdue_by_owner.items(), key=lambda kv: kv[1], default=None)
        who = f" {top[1]} of them sit with {top[0]}." if top and top[1] > 1 else ""
        recs.append((rfis.overdue * 3,
            f"{rfis.overdue} RFIs are past due.{who} Set up a weekly RFI review in the OAC meeting "
            "and turn on overdue email reminders so the ball in court is visible to everyone."))
    if submittals.overdue:
        recs.append((submittals.overdue * 3,
            f"{submittals.overdue} submittals are past due. Build the submittal register from the spec "
            "book early and add required on site dates so procurement risk shows up before it hits the schedule."))
    if rfis.avg_days_to_close is not None and rfis.avg_days_to_close > target_rfi_days:
        recs.append((int(rfis.avg_days_to_close),
            f"RFIs take {rfis.avg_days_to_close} days on average to close, against a {target_rfi_days} day target. "
            "Agree on a standard response window with the design team and use default distribution lists "
            "so the right reviewers are on every RFI from day one."))
    if submittals.total == 0 and rfis.total > 0:
        recs.append((6,
            "No submittals are logged in Procore yet, even though RFIs are active. Build the submittal "
            "register from the spec book now, with required on site dates, so long lead items like "
            "storefront, roofing, and the elevator are tracked before they hit the schedule."))
    missing = rfis.missing_due + submittals.missing_due
    if missing:
        recs.append((missing * 2,
            f"{missing} open items have no due date, so they can never show as late. "
            "Make due date a required field in the project configuration."))
    if not recs:
        recs.append((0, "RFIs and submittals are moving well. The next step is expanding adoption to "
                        "daily logs and observations so field data lives in the same place."))
    return [text for _, text in sorted(recs, key=lambda r: -r[0])[:3]]


def adoption_plan(rfis: ItemStats, submittals: ItemStats) -> list[tuple[str, str]]:
    first = "Clean up overdue RFIs and submittals with the PM, set due date rules, and turn on reminders."
    if not (rfis.overdue or submittals.overdue):
        first = "Confirm current workflows with the PM and document what is working so it can be repeated."
    return [
        ("First 30 days", first),
        ("Days 31 to 60", "Run a short training for the superintendent and key subs on responding inside Procore, "
                          "then review RFI turnaround weekly in the OAC meeting."),
        ("Days 61 to 90", "Rerun this health check, compare against the baseline, and expand to the next tool "
                          "the team is not using yet, such as daily logs or observations."),
    ]
