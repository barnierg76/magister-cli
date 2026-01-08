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
    """
    from magister_cli.auth import get_current_token

    try:
        validated_school = validate_school_code(school_code)
        token = get_current_token(validated_school)

        if token is None:
            return {
                "success": True,
                "is_authenticated": False,
                "school": validated_school,
                "resolution": {
                    "action": "login_required",
                    "user_instruction": f"Run: magister login --school {validated_school}",
                },
            }

        return {
            "success": True,
            "is_authenticated": True,
            "school": validated_school,
            "student_name": token.person_name,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
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
