"""MCP server for Magister CLI.

This server exposes Magister operations as MCP tools for Claude and other AI agents.
Tools are designed as workflows (combining multiple operations) rather than
individual API calls, following MCP best practices.

Usage:
    # Run the server
    python -m magister_cli.mcp

    # Or via entry point
    magister-mcp

    # Test with MCP dev tools
    mcp dev magister_cli/mcp/server.py
"""

import logging
from functools import wraps
from pathlib import Path
from typing import Callable, Optional, TypeVar

from mcp.server.fastmcp import FastMCP

from magister_cli.config import validate_school_code
from magister_cli.services.async_magister import MagisterAsyncService

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)


def mcp_error_handler(f: F) -> F:
    """Decorator to handle common errors in MCP tools.

    Catches RuntimeError (auth issues), ValueError (input validation),
    and generic exceptions, returning structured error responses.
    """

    @wraps(f)
    async def wrapper(*args, **kwargs):
        # Extract school_code from kwargs for error messages
        school_code = kwargs.get("school_code", "unknown")

        try:
            return await f(*args, **kwargs)
        except ValueError as e:
            return {
                "success": False,
                "error_type": "validation_error",
                "message": str(e),
                "resolution": {
                    "action": "fix_input",
                    "user_instruction": "Check the input parameters and try again.",
                },
            }
        except RuntimeError as e:
            error_msg = str(e)
            if "Not authenticated" in error_msg:
                return {
                    "success": False,
                    "error_type": "auth_error",
                    "message": "Authentication required",
                    "resolution": {
                        "action": "login_required",
                        "user_instruction": f"Run: magister login --school {school_code}",
                    },
                }
            return {
                "success": False,
                "error_type": "runtime_error",
                "message": error_msg,
            }
        except Exception as e:
            logger.exception(f"MCP tool error in {f.__name__}")
            return {
                "success": False,
                "error_type": "internal_error",
                "message": "An unexpected error occurred",
            }

    return wrapper  # type: ignore

# Initialize MCP server
mcp = FastMCP(
    name="magister",
    instructions="Magister CLI - Access Dutch student information system data. Use these tools to fetch homework, grades, schedule, and tests from the Magister student information system.",
)


# -----------------------------------------------------------------------------
# MCP Tools - Workflow-focused operations
# -----------------------------------------------------------------------------


@mcp.tool()
@mcp_error_handler
async def get_student_summary(
    school_code: str,
    days_ahead: int = 7,
) -> dict:
    """
    Get a complete daily summary for a student.

    This workflow tool fetches homework, grades, and schedule in a single operation,
    providing a comprehensive overview of the student's academic situation.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        days_ahead: Number of days to look ahead for homework (default: 7)

    Returns:
        Complete student summary including:
        - Student info (name, school)
        - Upcoming homework with details
        - Recent grades with average
        - Today's schedule
        - Summary statistics
    """
    async with MagisterAsyncService(school_code) as service:
        result = await service.get_student_summary(days=days_ahead)
        result["success"] = True
        return result


@mcp.tool()
@mcp_error_handler
async def get_homework(
    school_code: str,
    days_ahead: int = 7,
    subject_filter: Optional[str] = None,
    include_completed: bool = False,
) -> dict:
    """
    Get upcoming homework assignments.

    Fetches homework for the specified time period with optional filtering.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        days_ahead: Number of days to look ahead (default: 7)
        subject_filter: Optional subject name to filter (partial match, case-insensitive)
        include_completed: Include already completed homework (default: False)

    Returns:
        Homework items grouped by day with:
        - Subject, description, deadline
        - Teacher and location
        - Test indicators
        - Attachment information
    """
    async with MagisterAsyncService(school_code) as service:
        homework_days = await service.get_homework_grouped(
            days=days_ahead,
            subject=subject_filter,
            include_completed=include_completed,
        )

        return {
            "success": True,
            "days": [day.to_dict() for day in homework_days],
            "total_items": sum(len(day.items) for day in homework_days),
            "total_days": len(homework_days),
        }


@mcp.tool()
@mcp_error_handler
async def get_upcoming_tests(
    school_code: str,
    days_ahead: int = 14,
) -> dict:
    """
    Get upcoming tests and exams.

    Filters homework to show only tests/exams for easy study planning.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        days_ahead: Number of days to look ahead (default: 14)

    Returns:
        List of upcoming tests with:
        - Subject and description
        - Date and time
        - Study materials (attachments)
    """
    async with MagisterAsyncService(school_code) as service:
        tests = await service.get_upcoming_tests(days=days_ahead)

        return {
            "success": True,
            "tests": [t.to_dict() for t in tests],
            "total": len(tests),
            "period_days": days_ahead,
        }


@mcp.tool()
@mcp_error_handler
async def get_recent_grades(
    school_code: str,
    limit: int = 10,
) -> dict:
    """
    Get recent grades.

    Fetches the most recent grades with calculated average.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        limit: Maximum number of grades to return (default: 10)

    Returns:
        Recent grades with:
        - Subject and grade value
        - Weight and date
        - Description
        - Calculated weighted average
    """
    async with MagisterAsyncService(school_code) as service:
        grades = await service.get_recent_grades(limit=limit)
        average = service.core.calculate_average(grades)

        return {
            "success": True,
            "grades": [g.to_dict() for g in grades],
            "total": len(grades),
            "average": average,
        }


@mcp.tool()
@mcp_error_handler
async def get_today_schedule(
    school_code: str,
) -> dict:
    """
    Get today's schedule.

    Fetches all lessons and appointments for today.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')

    Returns:
        Today's schedule with:
        - Lesson times and subjects
        - Teachers and locations
        - Homework indicators
        - Cancellation status
    """
    async with MagisterAsyncService(school_code) as service:
        schedule = await service.get_today_schedule()

        return {
            "success": True,
            "lessons": [s.to_dict() for s in schedule],
            "total": len(schedule),
            "cancelled": sum(1 for s in schedule if s.is_cancelled),
        }


@mcp.tool()
@mcp_error_handler
async def download_homework_materials(
    school_code: str,
    days_ahead: int = 7,
    output_directory: str = "./magister_materials",
    subject_filter: Optional[str] = None,
) -> dict:
    """
    Download all homework attachments.

    Downloads materials attached to upcoming homework assignments,
    organized by subject in subdirectories.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        days_ahead: Number of days to look ahead (default: 7)
        output_directory: Where to save downloaded files (default: './magister_materials')
        subject_filter: Optional subject name to filter (partial match)

    Returns:
        Download results with:
        - List of downloaded files with paths
        - Success/failure status per file
        - Total file count
    """
    async with MagisterAsyncService(school_code) as service:
        downloads = await service.download_all_attachments(
            days=days_ahead,
            output_dir=Path(output_directory),
            subject=subject_filter,
        )

        successful = [d for d in downloads if d.get("success")]
        failed = [d for d in downloads if not d.get("success")]

        return {
            "success": True,
            "downloads": downloads,
            "total": len(downloads),
            "successful": len(successful),
            "failed": len(failed),
            "output_directory": output_directory,
        }


@mcp.tool()
async def get_schedule(
    school_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    Get schedule for a date range.

    Fetches lessons and appointments for a flexible date range.
    If no dates specified, defaults to today.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        start_date: Start date in ISO format (YYYY-MM-DD), defaults to today
        end_date: End date in ISO format (YYYY-MM-DD), defaults to start_date

    Returns:
        Schedule with:
        - Lesson times and subjects
        - Teachers and locations
        - Homework indicators
        - Cancellation status
    """
    from datetime import date, datetime, timedelta

    try:
        # Parse dates
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
        else:
            start = date.today()

        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        else:
            end = start

        async with MagisterAsyncService(school_code) as service:
            # Get schedule for each day in range
            all_lessons = []
            current = start
            while current <= end:
                day_schedule = await service.get_schedule(target_date=current)
                for lesson in day_schedule:
                    all_lessons.append(lesson.to_dict())
                current = current + timedelta(days=1)

            return {
                "success": True,
                "lessons": all_lessons,
                "total": len(all_lessons),
                "cancelled": sum(1 for s in all_lessons if s.get("is_cancelled")),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            }
    except ValueError as e:
        return {
            "success": False,
            "error_type": "invalid_date",
            "message": f"Invalid date format: {e}",
            "resolution": {
                "action": "fix_input",
                "user_instruction": "Use ISO format: YYYY-MM-DD",
            },
        }
    except RuntimeError as e:
        return {
            "success": False,
            "error_type": "auth_error",
            "message": str(e),
            "resolution": {
                "action": "login_required",
                "user_instruction": f"Run: magister login --school {school_code}",
            },
        }
    except Exception as e:
        logger.exception("Failed to fetch schedule")
        return {
            "success": False,
            "error_type": "internal_error",
            "message": "Failed to fetch schedule",
        }


@mcp.tool()
@mcp_error_handler
async def get_grade_overview(school_code: str) -> dict:
    """
    Get an overview of grades with per-subject averages.

    Analyzes all recent grades and provides statistics per subject including
    average, count, minimum, and maximum grades.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')

    Returns:
        Overview with:
        - Per-subject statistics (average, count, min, max)
        - Total grade count
        - Overall weighted average
    """
    async with MagisterAsyncService(school_code) as service:
        grades = await service.get_recent_grades(limit=100)

        # Group by subject
        by_subject = {}
        for grade in grades:
            subject = grade.subject
            if subject not in by_subject:
                by_subject[subject] = []
            try:
                # Parse grade as float (Dutch uses comma as decimal)
                value = float(grade.grade.replace(",", "."))
                by_subject[subject].append(value)
            except (ValueError, AttributeError):
                pass  # Skip non-numeric grades like "V" or "G"

        # Calculate statistics per subject
        overview = {}
        for subject, values in by_subject.items():
            if values:
                overview[subject] = {
                    "average": round(sum(values) / len(values), 2),
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                }

        # Calculate overall average
        overall_average = service.core.calculate_average(grades)

        return {
            "success": True,
            "subjects": overview,
            "total_grades": sum(len(v) for v in by_subject.values()),
            "overall_average": overall_average,
        }


@mcp.tool()
@mcp_error_handler
async def get_grade_trends(
    school_code: str,
    period_days: int = 90,
) -> dict:
    """
    Identify improving or declining subjects based on grade trends.

    Analyzes grade patterns over time to identify which subjects are
    improving, declining, or remaining stable. Uses a simple trend
    analysis comparing early vs recent grades.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        period_days: Number of days to analyze (default: 90)

    Returns:
        Trends with:
        - Improving subjects with change magnitude
        - Declining subjects with change magnitude
        - Stable subjects
        - Period analyzed
    """
    async with MagisterAsyncService(school_code) as service:
        grades = await service.get_recent_grades(limit=200)

        # Group grades by subject
        by_subject = {}
        for grade in grades:
            subject = grade.subject
            if subject not in by_subject:
                by_subject[subject] = []
            try:
                value = float(grade.grade.replace(",", "."))
                by_subject[subject].append(value)
            except (ValueError, AttributeError):
                pass

        # Analyze trends (compare first half vs second half)
        improving = []
        declining = []
        stable = []

        for subject, values in by_subject.items():
            if len(values) >= 4:  # Need at least 4 grades for trend
                mid = len(values) // 2
                first_half_avg = sum(values[:mid]) / mid
                second_half_avg = sum(values[mid:]) / (len(values) - mid)
                diff = second_half_avg - first_half_avg

                if diff > 0.5:
                    improving.append({"subject": subject, "change": round(diff, 2)})
                elif diff < -0.5:
                    declining.append({"subject": subject, "change": round(diff, 2)})
                else:
                    stable.append({"subject": subject, "change": round(diff, 2)})

        return {
            "success": True,
            "improving": improving,
            "declining": declining,
            "stable": stable,
            "period_days": period_days,
            "total_subjects_analyzed": len(improving) + len(declining) + len(stable),
        }


@mcp.tool()
@mcp_error_handler
async def get_grades_by_subject(
    school_code: str,
    subject: str,
) -> dict:
    """
    Get all grades for a specific subject.

    Filters grades by subject name and provides detailed statistics
    for that subject alone.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        subject: Subject name to filter by (case-insensitive partial match)

    Returns:
        Subject grades with:
        - List of matching grades
        - Statistics (average, count, min, max)
        - Subject filter used
    """
    async with MagisterAsyncService(school_code) as service:
        all_grades = await service.get_recent_grades(limit=200)

        # Filter by subject (case-insensitive partial match)
        subject_lower = subject.lower()
        matching = [
            g for g in all_grades
            if subject_lower in g.subject.lower()
        ]

        # Calculate stats
        numeric_values = []
        for g in matching:
            try:
                value = float(g.grade.replace(",", "."))
                numeric_values.append(value)
            except (ValueError, AttributeError):
                pass

        stats = {}
        if numeric_values:
            stats = {
                "average": round(sum(numeric_values) / len(numeric_values), 2),
                "count": len(numeric_values),
                "min": min(numeric_values),
                "max": max(numeric_values),
            }

        return {
            "success": True,
            "subject_filter": subject,
            "grades": [g.to_dict() for g in matching],
            "statistics": stats,
            "total_grades": len(matching),
        }


@mcp.tool()
@mcp_error_handler
async def get_messages(
    school_code: str,
    folder: str = "inbox",
    limit: int = 25,
    unread_only: bool = False,
) -> dict:
    """
    Get messages from the student's mailbox.

    Fetches messages from inbox, sent folder, or deleted items with optional filtering.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        folder: Which folder to read - 'inbox', 'sent', or 'deleted' (default: 'inbox')
        limit: Maximum number of messages to return (default: 25)
        unread_only: If True, only return unread messages (default: False)

    Returns:
        Messages list with:
        - Message ID, subject, sender information
        - Sent date and read status
        - Priority and attachment indicators
        - Total count of messages returned
    """
    async with MagisterAsyncService(school_code) as service:
        messages = await service.get_messages(
            folder=folder,
            limit=limit,
            unread_only=unread_only,
        )

        return {
            "success": True,
            "messages": messages,
            "folder": folder,
            "count": len(messages),
            "unread_only": unread_only,
        }


@mcp.tool()
@mcp_error_handler
async def read_message(
    school_code: str,
    message_id: int,
) -> dict:
    """
    Read the full content of a specific message.

    Retrieves complete message details including body text, recipients, and attachments.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        message_id: The ID of the message to read

    Returns:
        Full message with:
        - Complete message body (HTML content)
        - Sender and all recipient information
        - List of attachments with names and sizes
        - Message metadata (date, priority, read status)
    """
    async with MagisterAsyncService(school_code) as service:
        message = await service.get_message(message_id)

        return {
            "success": True,
            "message": message,
        }


@mcp.tool()
@mcp_error_handler
async def get_unread_count(
    school_code: str,
) -> dict:
    """
    Get the count of unread messages.

    Quickly check how many unread messages are in the inbox without fetching full message list.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')

    Returns:
        Unread message count with:
        - unread_count: Number of unread messages in inbox
    """
    async with MagisterAsyncService(school_code) as service:
        count = await service.get_unread_message_count()

        return {
            "success": True,
            "unread_count": count,
        }


@mcp.tool()
@mcp_error_handler
async def mark_message_read(
    school_code: str,
    message_id: int,
) -> dict:
    """
    Mark a message as read.

    Updates the read status of a message in the Magister system.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        message_id: The ID of the message to mark as read

    Returns:
        Success confirmation with:
        - message_id: The ID of the message that was marked as read
        - marked_read: True if operation succeeded
    """
    async with MagisterAsyncService(school_code) as service:
        await service.mark_message_as_read(message_id)

        return {
            "success": True,
            "message_id": message_id,
            "marked_read": True,
        }


@mcp.tool()
async def check_auth_status(
    school_code: str,
) -> dict:
    """
    Check authentication status for a school.

    Returns structured auth status information that agents can use
    to determine if authentication is required before other operations.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')

    Returns:
        Authentication status with:
        - is_authenticated: boolean
        - student_name: Name if authenticated
        - expires_at: Token expiration time
        - school: School code
        - needs_refresh: True if token expires within 15 minutes
        - can_browser_auth: True if GUI is available for browser auth
    """
    from magister_cli.auth import get_current_token
    from magister_cli.auth.async_browser_auth import is_gui_available
    from magister_cli.auth.token_manager import get_token_manager

    try:
        validated_school = validate_school_code(school_code)
        token = get_current_token(validated_school)
        can_browser = is_gui_available()

        if token is None:
            return {
                "success": True,
                "is_authenticated": False,
                "school": validated_school,
                "can_browser_auth": can_browser,
                "resolution": {
                    "action": "login_required",
                    "user_instruction": (
                        "Use the 'authenticate' tool to open a browser for login"
                        if can_browser
                        else f"Run: magister login --school {validated_school}"
                    ),
                },
            }

        # Check if token needs refresh soon
        token_manager = get_token_manager(validated_school)
        needs_refresh = token_manager.is_token_expiring_soon(minutes=15)
        time_until_expiry = token_manager.get_time_until_expiry()
        has_refresh_token = token_manager.has_refresh_token()

        return {
            "success": True,
            "is_authenticated": True,
            "school": validated_school,
            "student_name": token.person_name,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
            "needs_refresh": needs_refresh,
            "minutes_until_expiry": (
                int(time_until_expiry.total_seconds() / 60)
                if time_until_expiry
                else None
            ),
            "can_browser_auth": can_browser,
            "has_refresh_token": has_refresh_token,
            "can_silent_refresh": has_refresh_token,
        }
    except ValueError as e:
        return {
            "success": False,
            "error_type": "invalid_school",
            "message": str(e),
        }
    except Exception as e:
        logger.exception("Failed to check auth status")
        return {
            "success": False,
            "error_type": "internal_error",
            "message": "Failed to check auth status",
        }


@mcp.tool()
async def authenticate(
    school_code: str,
    timeout_seconds: int = 300,
) -> dict:
    """
    Launch browser authentication for Magister.

    Opens a browser window for the user to complete login to Magister.
    The user must complete the login in the browser window that opens.
    Once login is complete, the token is automatically stored.

    This tool requires a GUI environment (desktop with display).
    If no GUI is available, it will return instructions for CLI login.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        timeout_seconds: Maximum time to wait for login (default: 300, max: 600)

    Returns:
        Authentication result with:
        - success: True if authenticated
        - student_name: Name of authenticated student
        - expires_at: When the token expires
        - school: School code used
    """
    from magister_cli.auth.async_browser_auth import async_login, is_gui_available

    try:
        validated_school = validate_school_code(school_code)

        # Check if GUI is available
        if not is_gui_available():
            return {
                "success": False,
                "error_type": "no_gui",
                "message": "No GUI environment available for browser authentication",
                "resolution": {
                    "action": "use_cli",
                    "user_instruction": f"Run in terminal: magister login --school {validated_school}",
                },
            }

        # Clamp timeout to reasonable bounds
        timeout = max(60, min(timeout_seconds, 600))

        # Perform browser authentication
        token_data = await async_login(
            school=validated_school,
            headless=False,  # Must be visible for user to interact
            timeout_seconds=timeout,
        )

        return {
            "success": True,
            "message": "Authentication successful",
            "school": validated_school,
            "student_name": token_data.person_name,
            "expires_at": (
                token_data.expires_at.isoformat() if token_data.expires_at else None
            ),
        }

    except ValueError as e:
        return {
            "success": False,
            "error_type": "validation_error",
            "message": str(e),
        }
    except RuntimeError as e:
        error_msg = str(e)
        return {
            "success": False,
            "error_type": "auth_error",
            "message": error_msg,
            "resolution": {
                "action": "retry_or_cli",
                "user_instruction": (
                    "Try again or run in terminal: "
                    f"magister login --school {school_code}"
                ),
            },
        }
    except Exception as e:
        logger.exception("Failed to authenticate")
        return {
            "success": False,
            "error_type": "internal_error",
            "message": "An unexpected error occurred during authentication",
        }


@mcp.tool()
async def refresh_token(
    school_code: str,
) -> dict:
    """
    Refresh the access token using the stored refresh token.

    This silently refreshes the access token without requiring browser interaction.
    Only works if a refresh token was captured during the initial login.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')

    Returns:
        Refresh result with:
        - success: True if token was refreshed
        - expires_at: New token expiration time
        - has_refresh_token: Whether refresh token is available for future refreshes
    """
    from magister_cli.auth import refresh_access_token
    from magister_cli.auth.token_manager import get_token_manager

    try:
        validated_school = validate_school_code(school_code)
        token_manager = get_token_manager(validated_school)

        # Check if we have a refresh token
        if not token_manager.has_refresh_token():
            return {
                "success": False,
                "error_type": "no_refresh_token",
                "message": "No refresh token available",
                "resolution": {
                    "action": "login_required",
                    "user_instruction": f"Run: magister login --school {validated_school}",
                },
            }

        # Perform token refresh
        new_token = await refresh_access_token(validated_school)

        return {
            "success": True,
            "message": "Token refreshed successfully",
            "school": validated_school,
            "student_name": new_token.person_name,
            "expires_at": (
                new_token.expires_at.isoformat() if new_token.expires_at else None
            ),
            "has_refresh_token": new_token.has_refresh_token(),
        }

    except ValueError as e:
        return {
            "success": False,
            "error_type": "validation_error",
            "message": str(e),
        }
    except RuntimeError as e:
        error_msg = str(e)
        return {
            "success": False,
            "error_type": "refresh_failed",
            "message": error_msg,
            "resolution": {
                "action": "login_required",
                "user_instruction": f"Refresh failed. Run: magister login --school {school_code}",
            },
        }
    except Exception as e:
        logger.exception("Failed to refresh token")
        return {
            "success": False,
            "error_type": "internal_error",
            "message": "An unexpected error occurred",
        }


@mcp.tool()
async def refresh_authentication(
    school_code: str,
    timeout_seconds: int = 300,
) -> dict:
    """
    Refresh authentication - tries silent refresh first, falls back to browser.

    First attempts to refresh using the stored refresh token (silent, no browser).
    If that fails or no refresh token is available, falls back to browser authentication.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        timeout_seconds: Maximum time to wait for browser login if needed (default: 300)

    Returns:
        Refresh result with:
        - success: True if token is valid (refreshed or still good)
        - refreshed: True if token was refreshed
        - method: 'none', 'refresh_token', or 'browser'
        - expires_at: New token expiration time
    """
    from magister_cli.auth import get_current_token, refresh_access_token
    from magister_cli.auth.async_browser_auth import async_login, is_gui_available
    from magister_cli.auth.token_manager import get_token_manager

    try:
        validated_school = validate_school_code(school_code)
        token_manager = get_token_manager(validated_school)
        token = get_current_token(validated_school)

        # Check if we need to refresh
        if token and not token_manager.is_token_expiring_soon(minutes=15):
            time_remaining = token_manager.get_time_until_expiry()
            return {
                "success": True,
                "refreshed": False,
                "method": "none",
                "message": "Token is still valid, no refresh needed",
                "school": validated_school,
                "student_name": token.person_name,
                "expires_at": (
                    token.expires_at.isoformat() if token.expires_at else None
                ),
                "minutes_until_expiry": (
                    int(time_remaining.total_seconds() / 60) if time_remaining else None
                ),
                "has_refresh_token": token.has_refresh_token(),
            }

        # Try silent refresh first if we have a refresh token
        if token_manager.has_refresh_token():
            try:
                new_token = await refresh_access_token(validated_school)
                return {
                    "success": True,
                    "refreshed": True,
                    "method": "refresh_token",
                    "message": "Token refreshed silently using refresh token",
                    "school": validated_school,
                    "student_name": new_token.person_name,
                    "expires_at": (
                        new_token.expires_at.isoformat() if new_token.expires_at else None
                    ),
                    "has_refresh_token": new_token.has_refresh_token(),
                }
            except RuntimeError as e:
                logger.warning(f"Silent refresh failed, trying browser: {e}")
                # Fall through to browser auth

        # Need browser auth - check GUI availability
        if not is_gui_available():
            return {
                "success": False,
                "error_type": "no_gui",
                "message": "Token needs refresh but no GUI available and no valid refresh token",
                "resolution": {
                    "action": "use_cli",
                    "user_instruction": f"Run in terminal: magister login --school {validated_school}",
                },
            }

        # Perform browser re-authentication
        timeout = max(60, min(timeout_seconds, 600))
        token_data = await async_login(
            school=validated_school,
            headless=False,
            timeout_seconds=timeout,
        )

        return {
            "success": True,
            "refreshed": True,
            "method": "browser",
            "message": "Token refreshed via browser authentication",
            "school": validated_school,
            "student_name": token_data.person_name,
            "expires_at": (
                token_data.expires_at.isoformat() if token_data.expires_at else None
            ),
            "has_refresh_token": token_data.has_refresh_token(),
        }

    except ValueError as e:
        return {
            "success": False,
            "error_type": "validation_error",
            "message": str(e),
        }
    except RuntimeError as e:
        return {
            "success": False,
            "error_type": "auth_error",
            "message": str(e),
        }
    except Exception as e:
        logger.exception("Failed to refresh authentication")
        return {
            "success": False,
            "error_type": "internal_error",
            "message": "An unexpected error occurred",
        }


# -----------------------------------------------------------------------------
# Study Materials Tools
# -----------------------------------------------------------------------------


@mcp.tool()
@mcp_error_handler
async def get_study_guides(
    school_code: str,
) -> dict:
    """
    Get all study guides (studiewijzers) for the student.

    Study guides contain learning objectives, materials, and deadlines
    organized by subject or topic.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')

    Returns:
        List of study guides with:
        - Title and date range
        - Subject codes
        - Visibility status
    """
    async with MagisterAsyncService(school_code) as service:
        guides = await service.get_study_guides()

        return {
            "success": True,
            "study_guides": guides,
            "total": len(guides),
        }


@mcp.tool()
@mcp_error_handler
async def get_study_guide_details(
    school_code: str,
    guide_id: int,
) -> dict:
    """
    Get full details of a study guide including all sections and resources.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        guide_id: The ID of the study guide to retrieve

    Returns:
        Full study guide with:
        - Title and date range
        - Sections (onderdelen) with descriptions
        - Resources/attachments per section
    """
    async with MagisterAsyncService(school_code) as service:
        guide = await service.get_study_guide(guide_id)

        return {
            "success": True,
            "study_guide": guide,
        }


@mcp.tool()
@mcp_error_handler
async def get_learning_materials(
    school_code: str,
) -> dict:
    """
    Get all digital learning materials (textbooks, online resources).

    Returns the list of digital materials (like textbooks and online learning
    platforms) that the student has access to.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')

    Returns:
        List of learning materials with:
        - Title and publisher
        - EAN/ISBN number
        - Subject information
        - Access dates
    """
    async with MagisterAsyncService(school_code) as service:
        materials = await service.get_learning_materials()

        return {
            "success": True,
            "learning_materials": materials,
            "total": len(materials),
        }


@mcp.tool()
@mcp_error_handler
async def get_assignments(
    school_code: str,
    open_only: bool = False,
) -> dict:
    """
    Get ELO assignments that students can submit.

    These are digital assignments that require submission through the
    Magister ELO (Electronic Learning Environment).

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        open_only: If True, only return assignments that haven't been submitted yet

    Returns:
        List of assignments with:
        - Title and description
        - Subject and deadline
        - Submission status
        - Grade (if graded)
        - Attachments
    """
    async with MagisterAsyncService(school_code) as service:
        assignments = await service.get_assignments()

        if open_only:
            assignments = [
                a for a in assignments
                if not a.get("is_submitted") and not a.get("is_closed")
            ]

        # Count statistics
        submitted = sum(1 for a in assignments if a.get("is_submitted"))
        graded = sum(1 for a in assignments if a.get("is_graded"))
        open_count = sum(1 for a in assignments if not a.get("is_submitted") and not a.get("is_closed"))

        return {
            "success": True,
            "assignments": assignments,
            "total": len(assignments),
            "statistics": {
                "submitted": submitted,
                "graded": graded,
                "open": open_count,
            },
        }


@mcp.tool()
@mcp_error_handler
async def get_assignment_details(
    school_code: str,
    assignment_id: int,
) -> dict:
    """
    Get full details of a single ELO assignment.

    Args:
        school_code: The Magister school code (e.g., 'vsvonh')
        assignment_id: The ID of the assignment to retrieve

    Returns:
        Full assignment details with:
        - Title and full description
        - Subject and deadline
        - Submission status and grade
        - All attachments
    """
    async with MagisterAsyncService(school_code) as service:
        assignment = await service.get_assignment(assignment_id)

        return {
            "success": True,
            "assignment": assignment,
        }


# -----------------------------------------------------------------------------
# MCP Resources - Dynamic context for prompts
# -----------------------------------------------------------------------------


@mcp.resource("magister://status")
def get_auth_status() -> str:
    """
    Get authentication status for all configured schools.

    This resource provides information about which schools are currently
    authenticated, helping the agent understand what operations are possible.
    """
    from magister_cli.auth import get_current_token
    from magister_cli.config import get_settings

    settings = get_settings()
    school = settings.school

    if not school:
        return "No school configured. Use 'magister login --school <code>' to authenticate."

    token = get_current_token(school)
    if token is None:
        return f"Not authenticated for school: {school}. Run 'magister login --school {school}'."

    expires = token.expires_at.strftime("%Y-%m-%d %H:%M") if token.expires_at else "unknown"
    name = token.person_name or "Unknown"

    return f"Authenticated as {name} at {school}.magister.net (expires: {expires})"


# -----------------------------------------------------------------------------
# Server Entry Point
# -----------------------------------------------------------------------------


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
