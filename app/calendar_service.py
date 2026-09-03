from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIR = ROOT / "private" / "google_calendar"
CLIENT_FILE = PRIVATE_DIR / "credentials.json"
TOKEN_FILE = PRIVATE_DIR / "token.json"
CONFIG_FILE = PRIVATE_DIR / "config.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.freebusy",
    "https://www.googleapis.com/auth/calendar.app.created",
]

DEFAULT_TIMEZONE = os.getenv("FOCUSLYRA_TIMEZONE", "Europe/Lisbon")
FOCUSLYRA_CALENDAR_NAME = "Focuslyra"


class CalendarIntegrationError(RuntimeError):
    pass


def _ensure_private_dir() -> None:
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_config(config: dict[str, Any]) -> None:
    _ensure_private_dir()
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def save_client_credentials(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CalendarIntegrationError("The uploaded file is not valid Google OAuth JSON.") from exc

    installed = payload.get("installed")
    if not isinstance(installed, dict):
        raise CalendarIntegrationError(
            "Use a Google OAuth Client ID of type Desktop app. The downloaded JSON must contain an 'installed' section."
        )

    if not installed.get("client_id") or not installed.get("client_secret"):
        raise CalendarIntegrationError("The Google OAuth JSON is missing client_id/client_secret.")

    _ensure_private_dir()
    CLIENT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()

    return {"configured": True, "client_id_suffix": installed["client_id"][-18:]}


def _credentials() -> Credentials | None:
    if not TOKEN_FILE.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    except Exception:
        return None

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except RefreshError:
            try:
                TOKEN_FILE.unlink()
            except OSError:
                pass
            return None

    return None


def _service():
    creds = _credentials()
    if creds is None:
        raise CalendarIntegrationError("Google Calendar is not connected yet.")
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def connect_google_calendar() -> dict[str, Any]:
    if not CLIENT_FILE.exists():
        raise CalendarIntegrationError("Upload your Google Desktop OAuth credentials JSON first.")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    try:
        creds = flow.run_local_server(
            host="127.0.0.1",
            port=0,
            open_browser=True,
            access_type="offline",
            prompt="consent",
            authorization_prompt_message="Focuslyra opened Google authorization in your browser.",
            success_message="Focuslyra is connected to Google Calendar. You can close this tab and return to Focuslyra.",
        )
    except Exception as exc:
        raise CalendarIntegrationError(f"Google authorization did not complete: {exc}") from exc

    _ensure_private_dir()
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    calendar = ensure_focuslyra_calendar(service)
    return {"connected": True, "calendar": calendar}


def disconnect_google_calendar() -> None:
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


def _calendar_list(service) -> list[dict[str, Any]]:
    calendars: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = service.calendarList().list(pageToken=page_token).execute()
        calendars.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return calendars


def _account_timezone(service) -> str:
    try:
        for item in _calendar_list(service):
            if item.get("primary"):
                return item.get("timeZone") or DEFAULT_TIMEZONE
    except HttpError:
        pass
    return DEFAULT_TIMEZONE


def ensure_focuslyra_calendar(service=None) -> dict[str, Any]:
    service = service or _service()
    config = _load_config()
    calendar_id = config.get("focuslyra_calendar_id")

    if calendar_id:
        try:
            calendar = service.calendars().get(calendarId=calendar_id).execute()
            return {
                "id": calendar["id"],
                "summary": calendar.get("summary", FOCUSLYRA_CALENDAR_NAME),
                "timeZone": calendar.get("timeZone", DEFAULT_TIMEZONE),
            }
        except HttpError:
            config.pop("focuslyra_calendar_id", None)
            _save_config(config)

    timezone_name = _account_timezone(service)
    body = {
        "summary": FOCUSLYRA_CALENDAR_NAME,
        "description": "Language-study sessions scheduled by Focuslyra. Focuslyra writes only to this calendar.",
        "timeZone": timezone_name,
    }
    try:
        calendar = service.calendars().insert(body=body).execute()
    except HttpError as exc:
        raise CalendarIntegrationError(f"Could not create the Focuslyra calendar: {exc}") from exc

    config["focuslyra_calendar_id"] = calendar["id"]
    config["timezone"] = calendar.get("timeZone", timezone_name)
    _save_config(config)
    return {
        "id": calendar["id"],
        "summary": calendar.get("summary", FOCUSLYRA_CALENDAR_NAME),
        "timeZone": calendar.get("timeZone", timezone_name),
    }


def get_calendar_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "credentials_configured": CLIENT_FILE.exists(),
        "connected": False,
        "focuslyra_calendar": None,
        "timezone": DEFAULT_TIMEZONE,
        "scopes": SCOPES,
    }
    creds = _credentials()
    if creds is None:
        return status

    status["connected"] = True
    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        calendar = ensure_focuslyra_calendar(service)
        status["focuslyra_calendar"] = calendar
        status["timezone"] = calendar.get("timeZone") or _account_timezone(service)
    except Exception as exc:
        status["warning"] = str(exc)
    return status


def list_calendars() -> list[dict[str, Any]]:
    service = _service()
    focuslyra_id = _load_config().get("focuslyra_calendar_id")
    result = []
    for item in _calendar_list(service):
        result.append(
            {
                "id": item.get("id"),
                "summary": item.get("summary", "Untitled calendar"),
                "primary": bool(item.get("primary")),
                "selected": bool(item.get("selected", True)),
                "timeZone": item.get("timeZone"),
                "accessRole": item.get("accessRole"),
                "focuslyra": item.get("id") == focuslyra_id,
            }
        )
    return result


def _availability_calendar_ids(service) -> list[str]:
    config = _load_config()
    configured = config.get("availability_calendar_ids")
    available = _calendar_list(service)
    valid_ids = {item.get("id") for item in available if item.get("id")}

    if configured:
        selected = [calendar_id for calendar_id in configured if calendar_id in valid_ids]
        if selected:
            return selected[:50]

    defaults = [
        item["id"]
        for item in available
        if item.get("id") and (item.get("selected", True) or item.get("primary"))
    ]
    return defaults[:50]


def set_availability_calendars(calendar_ids: list[str]) -> list[str]:
    service = _service()
    valid_ids = {item.get("id") for item in _calendar_list(service) if item.get("id")}
    chosen = [calendar_id for calendar_id in calendar_ids if calendar_id in valid_ids][:50]
    if not chosen:
        raise CalendarIntegrationError("Choose at least one calendar for availability checks.")
    config = _load_config()
    config["availability_calendar_ids"] = chosen
    _save_config(config)
    return chosen


def _parse_clock(value: str) -> time:
    try:
        hour, minute = value.split(":", 1)
        return time(hour=int(hour), minute=int(minute))
    except Exception as exc:
        raise CalendarIntegrationError(f"Invalid clock time: {value}") from exc


def _round_up(dt: datetime, minutes: int = 15) -> datetime:
    discard = timedelta(minutes=dt.minute % minutes, seconds=dt.second, microseconds=dt.microsecond)
    if discard == timedelta(0):
        return dt
    return dt - discard + timedelta(minutes=minutes)


def find_free_slots(
    target_date: str,
    duration_minutes: int = 45,
    window_start: str = "08:00",
    window_end: str = "19:00",
    limit: int = 8,
) -> dict[str, Any]:
    if duration_minutes < 5 or duration_minutes > 240:
        raise CalendarIntegrationError("Study duration must be between 5 and 240 minutes.")

    try:
        day = date.fromisoformat(target_date)
    except ValueError as exc:
        raise CalendarIntegrationError("Date must use YYYY-MM-DD.") from exc

    service = _service()
    focus_calendar = ensure_focuslyra_calendar(service)
    timezone_name = focus_calendar.get("timeZone") or _account_timezone(service)
    tz = ZoneInfo(timezone_name)
    start_dt = datetime.combine(day, _parse_clock(window_start), tzinfo=tz)
    end_dt = datetime.combine(day, _parse_clock(window_end), tzinfo=tz)
    if end_dt <= start_dt:
        raise CalendarIntegrationError("The end of the study window must be after the start.")

    calendar_ids = _availability_calendar_ids(service)
    body = {
        "timeMin": start_dt.isoformat(),
        "timeMax": end_dt.isoformat(),
        "timeZone": timezone_name,
        "items": [{"id": calendar_id} for calendar_id in calendar_ids],
    }
    try:
        response = service.freebusy().query(body=body).execute()
    except HttpError as exc:
        raise CalendarIntegrationError(f"Could not read Google Calendar availability: {exc}") from exc

    busy: list[tuple[datetime, datetime]] = []
    for calendar_data in response.get("calendars", {}).values():
        for interval in calendar_data.get("busy", []):
            busy_start = datetime.fromisoformat(interval["start"].replace("Z", "+00:00")).astimezone(tz)
            busy_end = datetime.fromisoformat(interval["end"].replace("Z", "+00:00")).astimezone(tz)
            busy.append((max(busy_start, start_dt), min(busy_end, end_dt)))

    busy = sorted((a, b) for a, b in busy if a < b)
    merged: list[list[datetime]] = []
    for busy_start, busy_end in busy:
        if not merged or busy_start > merged[-1][1]:
            merged.append([busy_start, busy_end])
        else:
            merged[-1][1] = max(merged[-1][1], busy_end)

    gaps: list[tuple[datetime, datetime]] = []
    cursor = start_dt
    for busy_start, busy_end in merged:
        if cursor < busy_start:
            gaps.append((cursor, busy_start))
        cursor = max(cursor, busy_end)
    if cursor < end_dt:
        gaps.append((cursor, end_dt))

    duration = timedelta(minutes=duration_minutes)
    slots: list[dict[str, str]] = []
    for gap_start, gap_end in gaps:
        candidate = _round_up(gap_start)
        while candidate + duration <= gap_end and len(slots) < limit:
            slots.append({"start": candidate.isoformat(), "end": (candidate + duration).isoformat()})
            candidate += timedelta(minutes=15)
        if len(slots) >= limit:
            break

    return {
        "date": target_date,
        "timezone": timezone_name,
        "duration_minutes": duration_minutes,
        "calendar_ids_checked": calendar_ids,
        "slots": slots,
    }


def create_study_event(
    start_iso: str,
    duration_minutes: int = 45,
    summary: str = "🌍 Focuslyra — Language study",
    description: str = "Adaptive language-study session scheduled by Focuslyra.",
) -> dict[str, Any]:
    service = _service()
    focus_calendar = ensure_focuslyra_calendar(service)
    timezone_name = focus_calendar.get("timeZone") or DEFAULT_TIMEZONE
    tz = ZoneInfo(timezone_name)

    try:
        start_dt = datetime.fromisoformat(start_iso)
    except ValueError as exc:
        raise CalendarIntegrationError("Invalid event start date/time.") from exc
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=tz)
    else:
        start_dt = start_dt.astimezone(tz)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone_name},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 10},
                {"method": "popup", "minutes": 0},
            ],
        },
        "extendedProperties": {
            "private": {
                "focuslyra": "true",
                "focuslyra_type": "study",
            }
        },
    }

    try:
        created = service.events().insert(calendarId=focus_calendar["id"], body=event).execute()
    except HttpError as exc:
        raise CalendarIntegrationError(f"Could not create the Focuslyra study event: {exc}") from exc

    return {
        "id": created.get("id"),
        "summary": created.get("summary"),
        "start": created.get("start"),
        "end": created.get("end"),
        "htmlLink": created.get("htmlLink"),
        "calendar_id": focus_calendar["id"],
    }


def smart_schedule(
    target_date: str,
    duration_minutes: int = 45,
    window_start: str = "08:00",
    window_end: str = "19:00",
    summary: str = "🌍 Focuslyra — Language study",
) -> dict[str, Any]:
    free = find_free_slots(target_date, duration_minutes, window_start, window_end, limit=1)
    if not free["slots"]:
        raise CalendarIntegrationError("No free slot was found in that time window.")
    slot = free["slots"][0]
    event = create_study_event(slot["start"], duration_minutes=duration_minutes, summary=summary)
    return {"slot": slot, "event": event, "timezone": free["timezone"]}


def upcoming_focuslyra_events(max_results: int = 10) -> list[dict[str, Any]]:
    service = _service()
    focus_calendar = ensure_focuslyra_calendar(service)
    now = datetime.now(tz=ZoneInfo(focus_calendar.get("timeZone") or DEFAULT_TIMEZONE)).isoformat()
    try:
        response = service.events().list(
            calendarId=focus_calendar["id"],
            timeMin=now,
            maxResults=max(1, min(max_results, 50)),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except HttpError as exc:
        raise CalendarIntegrationError(f"Could not read Focuslyra sessions: {exc}") from exc

    events = []
    for item in response.get("items", []):
        events.append(
            {
                "id": item.get("id"),
                "summary": item.get("summary", "Focuslyra"),
                "start": item.get("start"),
                "end": item.get("end"),
                "htmlLink": item.get("htmlLink"),
            }
        )
    return events
