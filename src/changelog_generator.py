"""Changelog generation and formatting."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from .config import Config
from .git_parser import ParsedCommit
from .utils import format_date_range, sanitize_for_slack


class ChangelogGenerator:
    """Generate formatted changelogs from parsed commits."""

    def __init__(self, config: Config, logger: logging.Logger):
        """
        Initialize the changelog generator.

        Args:
            config: Configuration object
            logger: Logger instance
        """
        self.config = config
        self.logger = logger

    def generate_markdown(
        self,
        grouped_commits: Dict[str, List[ParsedCommit]],
        is_first_run: bool = False,
    ) -> str:
        """
        Generate a markdown-formatted changelog.

        Args:
            grouped_commits: Commits grouped by type
            is_first_run: Whether this is the first run

        Returns:
            Markdown formatted changelog
        """
        if not grouped_commits:
            return "No commits to report."

        lines = []

        # Title
        lines.append(f"# Changelog - {datetime.now().strftime('%B %d, %Y')}")
        lines.append("")

        # Get date range
        all_commits = [
            commit for commits in grouped_commits.values() for commit in commits
        ]
        if all_commits:
            dates = [commit.date for commit in all_commits]
            start_date = min(dates)
            end_date = max(dates)
            date_range = format_date_range(start_date, end_date)
            total_commits = len(all_commits)

        # Generate sections by type
        for commit_type, commits in grouped_commits.items():
            if commit_type in self.config.commit_types:
                type_config = self.config.commit_types[commit_type]
                emoji = type_config.emoji
                label = type_config.label
                section_title = f"## {emoji} {label}"
            else:
                section_title = "## Other Changes"

            lines.append(section_title)
            lines.append("")

            for commit in commits:
                # Build commit line
                parts = [f"- {commit.description}"]

                if self.config.changelog.include_author:
                    parts.append(f"(@{commit.author})")

                if self.config.changelog.include_commit_hash:
                    # Use hyperlink if URL is available, otherwise just show hash
                    if commit.url:
                        parts.append(f"([{commit.short_hash}]({commit.url}))")
                    else:
                        parts.append(f"({commit.short_hash})")

                line = " ".join(parts)
                lines.append(line)

            lines.append("")

        # Footer with metadata
        lines.append("---")
        if all_commits:
            lines.append(f"Total commits: {total_commits} | Period: {date_range}")

        return "\n".join(lines)

    def generate_slack_blocks(
        self,
        grouped_commits: Dict[str, List[ParsedCommit]],
    ) -> List[dict]:
        """
        Generate Slack Block Kit formatted blocks.

        Args:
            grouped_commits: Commits grouped by type

        Returns:
            List of Slack block dictionaries
        """
        if not grouped_commits:
            return [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "No new commits to report.",
                    },
                }
            ]

        blocks = []

        # Header
        header_text = "📋 Changelog"

        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": header_text},
            }
        )

        # Get metadata
        all_commits = [
            commit for commits in grouped_commits.values() for commit in commits
        ]
        if all_commits:
            dates = [commit.date for commit in all_commits]
            start_date = min(dates)
            end_date = max(dates)
            date_range = format_date_range(start_date, end_date)
            total_commits = len(all_commits)

            # Context block with metadata
            context_text = f"*Period:* {date_range} | *Total Commits:* {total_commits}"

            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": context_text}],
                }
            )

            # Add divider
            blocks.append({"type": "divider"})

        # Generate sections by type
        for commit_type, commits in grouped_commits.items():
            if commit_type in self.config.commit_types:
                type_config = self.config.commit_types[commit_type]
                emoji = type_config.emoji
                label = type_config.label
                section_title = f"*{emoji} {label}*"
            else:
                section_title = "*Other Changes*"

            # Build commit list
            commit_lines = []
            for commit in commits:
                # Sanitize description for Slack
                description = sanitize_for_slack(commit.description)

                # Build commit line
                parts = [f"• {description}"]

                if self.config.changelog.include_author:
                    parts.append(f"(@{commit.author})")

                if self.config.changelog.include_commit_hash:
                    # Use hyperlink if URL is available, otherwise just show hash
                    if commit.url:
                        parts.append(f"<{commit.url}|`{commit.short_hash}`>")
                    else:
                        parts.append(f"`{commit.short_hash}`")

                line = " ".join(parts)
                commit_lines.append(line)

            # Combine into section text
            section_text = section_title + "\n" + "\n".join(commit_lines)

            # Check if section is too long (Slack has 3000 char limit per block)
            if len(section_text) > 2900:
                # Truncate and add note
                section_text = section_text[:2900] + "\n... (more commits omitted)"

            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": section_text},
                }
            )

        return blocks

    def generate_slack_payload(
        self,
        grouped_commits: Dict[str, List[ParsedCommit]],
    ) -> dict:
        """
        Generate complete Slack webhook payload.

        Args:
            grouped_commits: Commits grouped by type
            is_first_run: Whether this is the first run

        Returns:
            Complete Slack payload dictionary
        """
        blocks = self.generate_slack_blocks(grouped_commits)

        payload = {
            "username": self.config.slack.username,
            "icon_emoji": self.config.slack.icon_emoji,
            "blocks": blocks,
        }

        return payload
