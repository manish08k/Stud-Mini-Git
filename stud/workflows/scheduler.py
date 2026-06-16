import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ..core.exceptions import StudError
from .triggers import TriggerEvent


class SchedulerError(StudError):
    pass


@dataclass
class CronField:
    values: List[int]
    is_wildcard: bool

    @classmethod
    def parse(cls, token: str, min_val: int, max_val: int) -> "CronField":
        if token == "*":
            return cls(values=[], is_wildcard=True)
        values = []
        for part in token.split(","):
            if "/" in part:
                r, _, step_str = part.partition("/")
                step = int(step_str)
                if r == "*":
                    start, end = min_val, max_val
                else:
                    start, end = (int(x) for x in r.split("-"))
                values.extend(range(start, end + 1, step))
            elif "-" in part:
                start, end = (int(x) for x in part.split("-"))
                values.extend(range(start, end + 1))
            else:
                values.append(int(part))

        for v in values:
            if not (min_val <= v <= max_val):
                raise SchedulerError(f"cron value {v} out of range [{min_val},{max_val}]")

        return cls(values=sorted(set(values)), is_wildcard=False)

    def matches(self, value: int) -> bool:
        if self.is_wildcard:
            return True
        return value in self.values


@dataclass
class CronExpression:
    minute: CronField
    hour: CronField
    day_of_month: CronField
    month: CronField
    day_of_week: CronField
    raw: str

    @classmethod
    def parse(cls, expr: str) -> "CronExpression":
        parts = expr.strip().split()
        if len(parts) != 5:
            raise SchedulerError(f"cron expression must have 5 fields: {expr!r}")
        m, h, dom, mon, dow = parts
        return cls(
            minute=CronField.parse(m, 0, 59),
            hour=CronField.parse(h, 0, 23),
            day_of_month=CronField.parse(dom, 1, 31),
            month=CronField.parse(mon, 1, 12),
            day_of_week=CronField.parse(dow, 0, 6),
            raw=expr,
        )

    def matches_time(self, t: time.struct_time) -> bool:
        return (
            self.minute.matches(t.tm_min)
            and self.hour.matches(t.tm_hour)
            and self.day_of_month.matches(t.tm_mday)
            and self.month.matches(t.tm_mon)
            and self.day_of_week.matches(t.tm_wday)
        )


EventCallback = Callable[[TriggerEvent], None]


@dataclass
class ScheduledJob:
    cron: CronExpression
    callback: EventCallback
    name: str = ""


class Scheduler:
    """Cron-like scheduler that fires TriggerEvents."""

    def __init__(self, poll_interval: float = 60.0):
        self.poll_interval = poll_interval
        self._jobs: List[ScheduledJob] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def add(self, cron_expr: str, callback: EventCallback, name: str = "") -> None:
        expr = CronExpression.parse(cron_expr)
        with self._lock:
            self._jobs.append(ScheduledJob(cron=expr, callback=callback, name=name))

    def remove(self, name: str) -> None:
        with self._lock:
            self._jobs = [j for j in self._jobs if j.name != name]

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.poll_interval + 1)
            self._thread = None

    def _loop(self) -> None:
        last_minute = -1
        while self._running:
            now = time.localtime()
            current_minute = (now.tm_hour, now.tm_min)
            if current_minute != last_minute:
                last_minute = current_minute
                self._fire(now)
            time.sleep(1.0)

    def _fire(self, t: time.struct_time) -> None:
        with self._lock:
            jobs = list(self._jobs)
        for job in jobs:
            if job.cron.matches_time(t):
                event = TriggerEvent(type="schedule", payload={"cron": job.cron.raw})
                try:
                    job.callback(event)
                except Exception:
                    pass

    def tick(self, t: Optional[time.struct_time] = None) -> None:
        """Manually fire a tick (for testing)."""
        self._fire(t or time.localtime())
