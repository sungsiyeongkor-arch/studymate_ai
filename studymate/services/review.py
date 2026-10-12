"""Transparent baseline scheduler, not a fitted human forgetting curve."""

from datetime import timedelta


def schedule(state, grade, hint, timestamp):
    grade = min(grade, 1) if hint else grade
    interval, ease = state.interval, state.ease
    if grade == 0:
        interval = 10 / 1440
        ease = max(1.3, ease - 0.2)
        successes, lapses = 0, state.lapses + 1
    elif grade == 1:
        interval = max(1, min(interval * 1.2, 7))
        ease = max(1.3, ease - 0.1)
        successes, lapses = state.successes, state.lapses
    else:
        interval = (
            1
            if state.successes == 0
            else (3 if state.successes == 1 else max(3, interval * ease))
        )
        if grade == 3:
            interval *= 1.3
            ease = min(3, ease + 0.1)
        successes, lapses = state.successes + 1, state.lapses
    interval = min(interval, 180)
    return dict(
        interval=interval,
        ease=ease,
        successes=successes,
        lapses=lapses,
        due=timestamp + timedelta(days=interval),
        version=state.version + 1,
    )
