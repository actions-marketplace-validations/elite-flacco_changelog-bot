"""Utility functions for the changelog generator."""

import re
from datetime import datetime
from typing import Optional


def validate_webhook_url(url: str) -> bool:
    """
    Validate that a URL is a valid Slack webhook URL.

    Args:
        url: The URL to validate

    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False

    pattern = r'^https://hooks\.slack\.com/services/[A-Z0-9]+/[A-Z0-9]+/[a-zA-Z0-9]+'
    return bool(re.match(pattern, url))


def format_commit_hash(commit_hash: str, length: int = 7) -> str:
    """
    Format a commit hash to a specified length.

    Args:
        commit_hash: The full commit hash
        length: Desired length (default: 7)

    Returns:
        Shortened commit hash
    """
    return commit_hash[:length]


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format a datetime object to a string.

    Args:
        dt: The datetime to format
        format_str: The format string (default: "%Y-%m-%d %H:%M:%S")

    Returns:
        Formatted datetime string
    """
    return dt.strftime(format_str)


def format_date_range(start_date: datetime, end_date: datetime) -> str:
    """
    Format a date range for display.

    Args:
        start_date: Start of the range
        end_date: End of the range

    Returns:
        Formatted date range string (e.g., "Nov 26 - Dec 3, 2025")
    """
    if start_date.year == end_date.year:
        if start_date.month == end_date.month:
            return f"{start_date.strftime('%b %d')} - {end_date.strftime('%d, %Y')}"
        else:
            return f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    else:
        return f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.

    Args:
        text: The text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated (default: "...")

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def sanitize_for_slack(text: str) -> str:
    """
    Sanitize text for Slack message formatting.
    Escapes special characters that could break Slack's markdown.

    Args:
        text: The text to sanitize

    Returns:
        Sanitized text
    """
    # Escape Slack markdown special characters
    replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
    }

    for char, replacement in replacements.items():
        text = text.replace(char, replacement)

    return text


def parse_conventional_commit(message: str) -> Optional[dict]:
    """
    Parse a conventional commit message.

    Format: [emoji] <type>[optional scope]: <description>
    Supports emojis at the beginning (e.g., "✨ feat: add feature")

    Args:
        message: The commit message to parse

    Returns:
        Dictionary with type, scope, and description, or None if not conventional
    """
    # Get first line only
    first_line = message.split("\n")[0].strip()

    # Remove leading emojis and whitespace
    # Pattern matches any non-ASCII characters (emojis) and spaces at the start
    cleaned_line = re.sub(r"^[^\x00-\x7F\s]*\s*", "", first_line)

    # Pattern for conventional commits: type(scope): description or type: description
    pattern = r"^(\w+)(?:\(([^)]+)\))?: (.+)$"
    match = re.match(pattern, cleaned_line)

    if not match:
        return None

    commit_type, scope, description = match.groups()

    return {"type": commit_type.lower(), "scope": scope, "description": description.strip()}


def generate_commit_url(repository: str, commit_hash: str, base_url: str = "https://github.com") -> Optional[str]:
    """
    Generate a URL for a commit based on the repository slug.

    Supports GitHub, GitLab, and Bitbucket URL formats.

    Args:
        repository: Repository slug (e.g., "owner/repo")
        commit_hash: Full commit hash
        base_url: Base URL for the Git hosting service (default: GitHub)

    Returns:
        Full URL to the commit, or None if repository is not provided
    """
    if not repository:
        return None

    repository = repository.strip()
    if not repository:
        return None

    # Determine hosting service from base URL
    if "gitlab" in base_url.lower():
        return f"{base_url}/{repository}/-/commit/{commit_hash}"
    elif "bitbucket" in base_url.lower():
        return f"{base_url}/{repository}/commits/{commit_hash}"
    else:
        # Default to GitHub format
        return f"{base_url}/{repository}/commit/{commit_hash}"


def should_skip_commit(message: str) -> bool:
    """
    Check if a commit should be skipped based on its message.

    Args:
        message: The commit message

    Returns:
        True if commit should be skipped, False otherwise
    """
    skip_patterns = ["[skip changelog]", "[skip ci]", "[ci skip]"]

    message_lower = message.lower()
    return any(pattern.lower() in message_lower for pattern in skip_patterns)
