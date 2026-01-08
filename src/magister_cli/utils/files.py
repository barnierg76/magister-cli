"""File utility functions."""


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks.

    Removes directory separators, parent directory references, and
    non-printable characters to ensure the filename is safe to use.

    Args:
        filename: The filename to sanitize

    Returns:
        Safe filename with dangerous characters removed
    """
    # Remove directory separators and parent directory references
    safe_name = filename.replace("/", "_").replace("\\", "_").replace("..", "_")

    # Remove non-printable characters
    safe_name = "".join(c for c in safe_name if c.isprintable())

    # Limit length to filesystem maximum
    if len(safe_name) > 255:
        safe_name = safe_name[:255]

    return safe_name or "unnamed_file"
