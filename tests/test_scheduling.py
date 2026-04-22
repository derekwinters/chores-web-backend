from datetime import date

import pytest

from app.scheduling import build_schedule, WeeklySchedule, MonthlySchedule, IntervalSchedule


class TestWeeklySchedule:
    def test_next_occurrence_basic(self):
        # Monday (0) schedule, starting from a Sunday
        sunday = date(2024, 1, 7)  # Sunday
        sched = build_schedule({"type": "weekly", "days": [0]})
        assert sched.next_due(sunday) == date(2024, 1, 8)  # Monday

    def test_multiple_days(self):
        # Mon and Thu schedule
        monday = date(2024, 1, 8)
        sched = build_schedule({"type": "weekly", "days": [0, 3]})
        assert sched.next_due(monday) == date(2024, 1, 11)  # Thursday

    def test_every_other_week(self):
        # Biweekly Monday; reference = Jan 8 2024 (a Monday)
        sched = build_schedule({
            "type": "weekly",
            "days": [0],
            "every_other_week": True,
            "reference_date": "2024-01-08",
        })
        monday_1 = date(2024, 1, 8)
        next_occ = sched.next_due(monday_1)
        assert next_occ == date(2024, 1, 22)  # two weeks later

    def test_summary_weekly(self):
        sched = build_schedule({"type": "weekly", "days": [0, 3]})
        assert sched.summary() == "Weekly on Mon, Thu"

    def test_summary_biweekly(self):
        sched = build_schedule({"type": "weekly", "days": [2], "every_other_week": True})
        assert "Every other week on" in sched.summary()


class TestMonthlySchedule:
    def test_fixed_day(self):
        sched = build_schedule({"type": "monthly", "day_of_month": 15})
        assert sched.next_due(date(2024, 1, 15)) == date(2024, 2, 15)
        assert sched.next_due(date(2024, 1, 14)) == date(2024, 1, 15)

    def test_last_day(self):
        sched = build_schedule({"type": "monthly", "day_of_month": -1})
        assert sched.next_due(date(2024, 1, 1)) == date(2024, 1, 31)

    def test_nth_weekday(self):
        # 2nd Tuesday of the month
        sched = build_schedule({
            "type": "monthly",
            "weekday_occurrence": {"week": 2, "weekday": 1},
        })
        # In Jan 2024 the 2nd Tuesday is Jan 9
        assert sched.next_due(date(2024, 1, 1)) == date(2024, 1, 9)

    def test_summary_fixed(self):
        sched = build_schedule({"type": "monthly", "day_of_month": 15})
        assert sched.summary() == "Monthly on the 15th"

    def test_summary_last_day(self):
        sched = build_schedule({"type": "monthly", "day_of_month": -1})
        assert sched.summary() == "Monthly on the last day"


class TestIntervalSchedule:
    def test_basic_interval(self):
        sched = build_schedule({"type": "interval", "days": 7})
        assert sched.next_due(date(2024, 1, 1)) == date(2024, 1, 8)

    def test_single_day(self):
        sched = build_schedule({"type": "interval", "days": 1})
        assert sched.summary() == "Every 1 day"

    def test_plural(self):
        sched = build_schedule({"type": "interval", "days": 3})
        assert sched.summary() == "Every 3 days"


class TestConditions:
    def test_even_days_skip(self):
        # Schedule on Jan 1 (odd), condition: even days only, behavior: skip
        sched = build_schedule({
            "type": "interval",
            "days": 1,
            "conditions": [{"type": "even_days"}],
            "condition_failure": "skip",
        })
        # Jan 1 -> next is Jan 2 (even), valid
        result = sched.next_due(date(2024, 1, 1))
        assert result is not None
        assert result.day % 2 == 0

    def test_odd_days_delay(self):
        sched = build_schedule({
            "type": "interval",
            "days": 1,
            "conditions": [{"type": "odd_days"}],
            "condition_failure": "delay",
        })
        # Jan 2 (even) -> delayed to Jan 3 (odd)
        result = sched.next_due(date(2024, 1, 1))
        assert result is not None
        assert result.day % 2 != 0

    def test_weekdays_condition_skip(self):
        # Every 4 days, only Mon/Thu/Sat (0, 3, 5)
        sched = build_schedule({
            "type": "interval",
            "days": 4,
            "conditions": [{"type": "weekdays", "days": [0, 3, 5]}],
            "condition_failure": "skip",
        })
        result = sched.next_due(date(2024, 1, 1))  # Monday Jan 1
        assert result is not None
        # result must fall on Mon, Thu, or Sat
        assert result.weekday() in (0, 3, 5)

    def test_weekdays_condition_delay(self):
        # Every 5 days, only Mon/Thu/Sat — delay until valid weekday
        sched = build_schedule({
            "type": "interval",
            "days": 5,
            "conditions": [{"type": "weekdays", "days": [0, 3, 5]}],
            "condition_failure": "delay",
        })
        result = sched.next_due(date(2024, 1, 1))
        assert result is not None
        assert result.weekday() in (0, 3, 5)

    def test_weekdays_condition_string_days(self):
        # Days can be specified as strings
        sched = build_schedule({
            "type": "interval",
            "days": 1,
            "conditions": [{"type": "weekdays", "days": ["mon", "wed", "fri"]}],
            "condition_failure": "skip",
        })
        result = sched.next_due(date(2024, 1, 1))
        assert result is not None
        assert result.weekday() in (0, 2, 4)

    def test_weekdays_summary(self):
        sched = build_schedule({
            "type": "interval",
            "days": 4,
            "conditions": [{"type": "weekdays", "days": [0, 3, 5]}],
        })
        # summary() on the condition is tested via WeekdaysCondition directly
        from app.scheduling.schedule import WeekdaysCondition
        cond = WeekdaysCondition([0, 3, 5])
        assert cond.summary() == "on Mon, Thu, Sat only"

    def test_even_days_condition_skip(self):
        sched = build_schedule({
            "type": "interval",
            "days": 1,
            "conditions": [{"type": "even_days"}],
            "condition_failure": "skip",
        })
        result = sched.next_due(date(2024, 1, 1))
        assert result is not None
        assert result.day % 2 == 0

    def test_unknown_schedule_type(self):
        with pytest.raises(ValueError):
            build_schedule({"type": "bogus"})

    def test_unknown_condition_type(self):
        with pytest.raises(ValueError):
            build_schedule({
                "type": "interval",
                "days": 1,
                "conditions": [{"type": "bogus"}],
            })
