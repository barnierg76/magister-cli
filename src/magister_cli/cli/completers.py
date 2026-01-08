"""Custom shell completers for CLI commands."""

from pathlib import Path
from typing import Iterator

import yaml


def _load_subjects_cache() -> list[str]:
    """Load cached subjects from previous API calls."""
    cache_file = Path.home() / ".config" / "magister-cli" / "subjects_cache.yaml"
    if not cache_file.exists():
        return []
    try:
        with open(cache_file) as f:
            data = yaml.safe_load(f)
            return data.get("subjects", []) if data else []
    except (yaml.YAMLError, OSError):
        return []


def save_subjects_cache(subjects: list[str]) -> None:
    """Save subjects to cache for completion."""
    cache_file = Path.home() / ".config" / "magister-cli" / "subjects_cache.yaml"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w") as f:
        yaml.dump({"subjects": sorted(set(subjects))}, f)


def complete_school(incomplete: str) -> Iterator[str]:
    """Complete school codes from config or recent logins."""
    # Get schools from config file
    config_file = Path.home() / ".config" / "magister-cli" / "config.yaml"
    schools = []

    if config_file.exists():
        try:
            with open(config_file) as f:
                data = yaml.safe_load(f)
                if data and "school" in data:
                    schools.append(data["school"])
        except yaml.YAMLError:
            pass

    # Return schools starting with incomplete
    for school in schools:
        if school and school.startswith(incomplete.lower()):
            yield school


def complete_subject(incomplete: str) -> Iterator[str]:
    """Complete subject names from cached grades data."""
    subjects = _load_subjects_cache()
    incomplete_lower = incomplete.lower()

    for subject in subjects:
        if subject.lower().startswith(incomplete_lower):
            yield subject
