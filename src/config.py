"""Configuration management for the changelog generator."""

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml
from colorlog import ColoredFormatter
from dotenv import load_dotenv

from .utils import validate_webhook_url


@dataclass
class RepositoryConfig:
    """Configuration for a single repository."""

    repository: str  # GitHub slug (e.g., "your-org/frontend-repo") - required
    name: str  # Display name
    path: Optional[str] = None  # Optional filesystem path (if not provided, will clone from repository)
    slack_webhook_url: Optional[str] = None  # Optional override per repo


@dataclass
class CommitTypeConfig:
    """Configuration for a commit type."""

    label: str
    emoji: str
    include: bool
    order: int


@dataclass
class SlackConfig:
    """Slack-specific configuration."""

    username: str = "Changelog Bot"
    icon_emoji: str = ":memo:"


@dataclass
class ChangelogConfig:
    """Changelog generation configuration."""

    include_author: bool = True
    include_date: bool = True
    include_commit_hash: bool = True
    hash_length: int = 7
    group_by_type: bool = True
    max_commits_per_type: int = 50


@dataclass
class FirstRunConfig:
    """First run behavior configuration."""

    lookback_days: int = 30
    max_commits: int = 50


@dataclass
class Config:
    """Main configuration class - styling and presentation only."""

    slack_webhook_url: Optional[str] = None
    log_level: str = "INFO"
    state_file: str = "data/state.json"
    commit_types: Dict[str, CommitTypeConfig] = field(default_factory=dict)
    slack: SlackConfig = field(default_factory=SlackConfig)
    changelog: ChangelogConfig = field(default_factory=ChangelogConfig)
    first_run: FirstRunConfig = field(default_factory=FirstRunConfig)

    def __post_init__(self):
        """Validate configuration after initialization."""
        # Only validate webhook URL if it's provided
        if self.slack_webhook_url and not validate_webhook_url(self.slack_webhook_url):
            raise ValueError(
                f"Invalid Slack webhook URL format: {self.slack_webhook_url}"
            )


def load_repositories_from_env() -> list[RepositoryConfig]:
    """
    Load repository configuration from REPOSITORIES_JSON environment variable.

    Returns:
        List of repository configurations

    Raises:
        ValueError: If REPOSITORIES_JSON is missing or invalid
    """
    import json

    repos_json = os.getenv("REPOSITORIES_JSON")
    if not repos_json:
        raise ValueError(
            "REPOSITORIES_JSON environment variable is required. "
            "It should be a JSON array of repository configurations."
        )

    try:
        repos_data = json.loads(repos_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in REPOSITORIES_JSON: {e}")

    if not isinstance(repos_data, list):
        raise ValueError("REPOSITORIES_JSON must be a JSON array")

    if not repos_data:
        raise ValueError("REPOSITORIES_JSON must contain at least one repository")

    repositories = []
    for idx, repo_data in enumerate(repos_data):
        if not isinstance(repo_data, dict):
            raise ValueError(f"Repository at index {idx} must be a JSON object")

        # Validate required fields
        required_fields = ["name", "repository"]
        for field in required_fields:
            if field not in repo_data:
                raise ValueError(
                    f"Repository at index {idx} is missing required field: {field}"
                )

        repositories.append(
            RepositoryConfig(
                repository=repo_data["repository"],
                name=repo_data["name"],
                path=repo_data.get("path"),  # Optional
                slack_webhook_url=repo_data.get("slack_webhook_url"),
            )
        )

    return repositories


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Setup logging with colored console output.

    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("changelog")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Console handler with colors
    console_handler = logging.StreamHandler()
    console_formatter = ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


def load_config(config_path: str = "config.yaml") -> Config:
    """
    Load configuration from environment variables and config file.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Loaded configuration object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If required configuration is missing
    """
    # Load environment variables from .env file (if exists)
    load_dotenv()

    # Load environment variables
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    state_file = os.getenv("STATE_FILE", "data/state.json")

    # Load YAML configuration
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file, "r", encoding="utf-8") as f:
        yaml_config = yaml.safe_load(f)

    # Parse commit types
    commit_types = {}
    for type_name, type_config in yaml_config.get("commit_types", {}).items():
        commit_types[type_name] = CommitTypeConfig(
            label=type_config["label"],
            emoji=type_config["emoji"],
            include=type_config["include"],
            order=type_config["order"],
        )

    # Parse Slack config
    slack_config_data = yaml_config.get("slack", {})
    slack_config = SlackConfig(
        username=slack_config_data.get("username", "Changelog Bot"),
        icon_emoji=slack_config_data.get("icon_emoji", ":memo:"),
    )

    # Parse changelog config
    changelog_config_data = yaml_config.get("changelog", {})
    changelog_config = ChangelogConfig(
        include_author=changelog_config_data.get("include_author", True),
        include_date=changelog_config_data.get("include_date", True),
        include_commit_hash=changelog_config_data.get("include_commit_hash", True),
        hash_length=changelog_config_data.get("hash_length", 7),
        group_by_type=changelog_config_data.get("group_by_type", True),
        max_commits_per_type=changelog_config_data.get("max_commits_per_type", 50),
    )

    # Parse first run config
    first_run_config_data = yaml_config.get("first_run", {})
    first_run_config = FirstRunConfig(
        lookback_days=first_run_config_data.get("lookback_days", 30),
        max_commits=first_run_config_data.get("max_commits", 50),
    )

    # Create main config (styling only, no repositories)
    config = Config(
        slack_webhook_url=slack_webhook_url,
        log_level=log_level,
        state_file=state_file,
        commit_types=commit_types,
        slack=slack_config,
        changelog=changelog_config,
        first_run=first_run_config,
    )

    return config
