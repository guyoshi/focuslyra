from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from .calendar_service import (
    CalendarIntegrationError,
    get_calendar_status,
    smart_schedule,
    upcoming_focuslyra_events,
)
from .runtime import current_user_id, user_private_dir
from .session_planner import build_daily_plan


class PlanCalendarError(RuntimeError):
    pass


def _settings_path(user_id: str | None = None):
    return user_private_dir(user_id) / 'calendar' / 'planner.json'


def load_settings(user_id: str | None = None) -> dict[str, Any]:
    path = _settings_path(user_id)
    defaults = {
        'auto_schedule': False,
        'window_start': '08:00',
        'window_end': '19:00',
        'mode': 'normal',
        'days_ahead': 1,
    }
    if not path.exists():
        return defaults
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return defaults
    if not isinstance(value, dict):
        return defaults
    return {**defaults, **value}


def save_settings(payload: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    clean = load_settings(user_id)
    if 'auto_schedule' in payload:
        clean['auto_schedule'] = bool(payload['auto_schedule'])
    if 'window_start' in payload:
        clean['window_start'] = str(payload['window_start'])[:5]
    if 'window_end' in payload:
        clean['window_end'] = str(payload['window_end'])[:5]
    if 'mode' in payload:
        clean['mode'] = 'minimum' if payload['mode'] == 'minimum' else 'normal'
    if 'days_ahead' in payload:
        try:
            clean['days_ahead'] = max(0, min(7, int(payload['days_ahead'])))
        except (TypeError, ValueError):
            pass
    path = _settings_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding='utf-8')
    return clean


def _summary(target_date: str) -> str:
    return f'🌍 Focuslyra · Study plan · {target_date}'


def schedule_adaptive_plan(
    target_date: str,
    mode: str = 'normal',
    window_start: str | None = None,
    window_end: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    uid = user_id or current_user_id()
    status = get_calendar_status()
    if not status.get('connected'):
        raise PlanCalendarError('Google Calendar is not connected.')
    settings = load_settings(uid)
    plan = build_daily_plan('minimum' if mode == 'minimum' else 'normal', uid)
    if not plan.get('activities'):
        raise PlanCalendarError('The planner produced no study activities.')
    summary = _summary(target_date)
    try:
        upcoming = upcoming_focuslyra_events(max_results=50)
    except CalendarIntegrationError as exc:
        raise PlanCalendarError(str(exc)) from exc
    existing = next((event for event in upcoming if event.get('summary') == summary), None)
    if existing:
        return {'scheduled': False, 'existing': True, 'event': existing, 'plan': plan}
    try:
        scheduled = smart_schedule(
            target_date,
            duration_minutes=int(plan['total_minutes']),
            window_start=window_start or settings['window_start'],
            window_end=window_end or settings['window_end'],
            summary=summary,
        )
    except CalendarIntegrationError as exc:
        raise PlanCalendarError(str(exc)) from exc
    return {'scheduled': True, 'existing': False, 'plan': plan, **scheduled}


def auto_schedule_if_enabled(user_id: str | None = None) -> dict[str, Any]:
    uid = user_id or current_user_id()
    settings = load_settings(uid)
    if not settings.get('auto_schedule'):
        return {'enabled': False, 'scheduled': []}
    start = date.today()
    results = []
    for offset in range(int(settings.get('days_ahead', 1)) + 1):
        target = (start + timedelta(days=offset)).isoformat()
        try:
            results.append(schedule_adaptive_plan(target, settings.get('mode', 'normal'), user_id=uid))
        except PlanCalendarError as exc:
            results.append({'date': target, 'error': str(exc)})
    return {'enabled': True, 'scheduled': results}
