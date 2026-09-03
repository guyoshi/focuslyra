# Google Calendar Integration

Focuslyra uses Google Calendar to fit language study around the learner's real schedule and to rely on Google Calendar notifications on the phone.

## Design rules

- Focuslyra reads availability from calendars selected by the learner.
- Focuslyra does not edit existing personal/work/family calendars.
- Focuslyra creates one secondary calendar named `Focuslyra` and writes study events only there.
- Study events use popup reminders 10 minutes before and at the event start.
- Google OAuth credentials and tokens remain local under `private/google_calendar/` and are excluded from Git.
- Disconnecting Focuslyra removes the local OAuth token but does not delete the Google calendar or its events.

## OAuth scopes

Focuslyra deliberately avoids the broad full-calendar scope. It requests:

- `calendar.calendarlist.readonly` — list calendars so the learner can choose which calendars count as busy.
- `calendar.freebusy` — read only availability/busy periods.
- `calendar.app.created` — create a secondary Focuslyra calendar and manage events on calendars created by Focuslyra.

If the scope set changes, the local OAuth token must be renewed.

## One-time Google setup for development/personal use

1. Open Google Cloud Console and create/select a project named `Focuslyra`.
2. Enable **Google Calendar API** for the project.
3. Open **Google Auth Platform** and configure Branding/Audience.
4. For a personal Google account, use **External** audience, keep the app in **Testing**, and add your own Google account under **Test users**.
5. Open **Google Auth Platform → Clients**.
6. Create a new OAuth client with application type **Desktop app**.
7. Download the client JSON file. Do not commit it to Git.
8. In Focuslyra open **Calendar**.
9. Upload the downloaded JSON using **Upload credentials locally**.
10. Click **Connect Google Calendar** and approve the requested permissions in the Google browser page.

The Google client JSON and resulting refresh/access token are stored only on the local PC.

## User flow

```text
Calendar page
   |
   +-- upload Desktop OAuth credentials JSON (one time)
   |
   +-- Connect Google Calendar
   |      |
   |      +-- browser opens Google OAuth
   |      +-- local token saved
   |      +-- Focuslyra secondary calendar created/located
   |
   +-- choose calendars used for availability
   |
   +-- find free slots
   |      +-- Google FreeBusy API
   |
   +-- schedule chosen/earliest slot
          +-- event written only to Focuslyra calendar
          +-- popup reminders: -10 min and 0 min
```

## Smart scheduling

The current MVP can:

- query a date and time window;
- merge busy periods from the selected calendars;
- propose study slots in 15-minute increments;
- create a study event in a selected slot;
- automatically choose the earliest available slot.

Later the Learning Engine should supply the desired duration automatically. Examples:

- normal day: 40–60 minutes;
- minimum day: 10–15 minutes;
- Sunday English call: optional warm-up immediately before the call;
- high-priority languages receive more scheduled minutes.

The calendar scheduler must never create or move study events silently unless the learner has explicitly enabled an automatic-scheduling policy.

## Phone reminders

Creating reminder overrides through the Calendar API is not enough by itself to guarantee a sound on the phone. The Google Calendar app must also have notification permission enabled in Android/iOS, and the calendar must be visible/synchronised on the device.
