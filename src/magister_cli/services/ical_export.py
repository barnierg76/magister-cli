"""iCal export service for schedule and homework."""

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event, vText

from magister_cli.api.models import Afspraak
from magister_cli.services.homework import HomeworkItem

# Netherlands timezone
NL_TZ = ZoneInfo("Europe/Amsterdam")


def _generate_uid(prefix: str, id: int, date: datetime) -> str:
    """Generate a stable UID for calendar events."""
    date_str = date.strftime("%Y%m%d")
    return f"{prefix}-{id}-{date_str}@magister-cli"


def create_calendar(name: str = "Magister") -> Calendar:
    """Create a new iCalendar object with proper headers."""
    cal = Calendar()
    cal.add("prodid", "-//Magister CLI//magister-cli//NL")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", name)
    cal.add("x-wr-timezone", "Europe/Amsterdam")
    return cal


def appointment_to_event(afspraak: Afspraak) -> Event:
    """Convert a Magister appointment to an iCal event."""
    event = Event()

    # Use stable UID based on appointment ID and date
    uid = _generate_uid("appointment", afspraak.id, afspraak.start)
    event.add("uid", uid)

    # Title: subject name with status indicators
    title_parts = [afspraak.vak_naam or afspraak.omschrijving or "Onbekend"]

    if afspraak.is_vervallen:
        title_parts.insert(0, "[UITVAL]")
    elif afspraak.is_gewijzigd:
        title_parts.insert(0, "[WIJZIGING]")

    if afspraak.is_test_or_exam():
        title_parts.append("(TOETS)")

    event.add("summary", " ".join(title_parts))

    # Time
    event.add("dtstart", afspraak.start.replace(tzinfo=NL_TZ))
    event.add("dtend", afspraak.einde.replace(tzinfo=NL_TZ))

    # Location
    if afspraak.lokaal_naam:
        event.add("location", vText(afspraak.lokaal_naam))

    # Description with details
    description_parts = []

    if afspraak.les_uur:
        description_parts.append(f"Les {afspraak.les_uur}")

    if afspraak.docent_naam:
        description_parts.append(f"Docent: {afspraak.docent_naam}")

    if afspraak.heeft_huiswerk:
        description_parts.append("")
        description_parts.append("--- Huiswerk ---")
        description_parts.append(afspraak.huiswerk_tekst)

    if description_parts:
        event.add("description", "\n".join(description_parts))

    # Categories
    categories = []
    if afspraak.is_test_or_exam():
        categories.append("Toets")
    if afspraak.heeft_huiswerk:
        categories.append("Huiswerk")
    if afspraak.is_vervallen:
        categories.append("Uitval")

    if categories:
        event.add("categories", categories)

    # Status
    if afspraak.is_vervallen:
        event.add("status", "CANCELLED")
    else:
        event.add("status", "CONFIRMED")

    return event


def homework_to_event(item: HomeworkItem) -> Event:
    """Convert a homework item to an all-day event."""
    event = Event()

    # Use stable UID
    uid = _generate_uid("homework", item.raw.id if item.raw else hash(item.description), item.deadline)
    event.add("uid", uid)

    # Title with test indicator
    title = f"HW: {item.subject}"
    if item.is_test:
        title = f"TOETS: {item.subject}"

    event.add("summary", title)

    # All-day event on the deadline date
    event.add("dtstart", item.deadline.date())
    event.add("dtend", item.deadline.date() + timedelta(days=1))

    # Description
    description_parts = []
    if item.description:
        description_parts.append(item.description)

    if item.teacher:
        description_parts.append(f"\nDocent: {item.teacher}")

    if item.location:
        description_parts.append(f"Lokaal: {item.location}")

    if description_parts:
        event.add("description", "\n".join(description_parts))

    # Categories
    if item.is_test:
        event.add("categories", ["Toets", "Huiswerk"])
    else:
        event.add("categories", ["Huiswerk"])

    return event


def export_schedule_to_ical(
    appointments: list[Afspraak],
    output_path: Path,
    calendar_name: str = "Magister Rooster",
) -> None:
    """Export appointments to an iCal file.

    Args:
        appointments: List of appointments to export
        output_path: Path to write the .ics file
        calendar_name: Name for the calendar
    """
    cal = create_calendar(calendar_name)

    for afspraak in appointments:
        event = appointment_to_event(afspraak)
        cal.add_component(event)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(cal.to_ical())


def export_homework_to_ical(
    items: list[HomeworkItem],
    output_path: Path,
    calendar_name: str = "Magister Huiswerk",
) -> None:
    """Export homework to an iCal file as all-day events.

    Args:
        items: List of homework items to export
        output_path: Path to write the .ics file
        calendar_name: Name for the calendar
    """
    cal = create_calendar(calendar_name)

    for item in items:
        event = homework_to_event(item)
        cal.add_component(event)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(cal.to_ical())
