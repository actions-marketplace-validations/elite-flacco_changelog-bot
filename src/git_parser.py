"""Git commit parsing and grouping."""

import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from .config import Config
from .utils import generate_commit_url, parse_conventional_commit, should_skip_commit


@dataclass
class ParsedCommit:
    """Represents a parsed commit with metadata."""

    hash: str
    short_hash: str
    message: str
    author: str
    date: datetime
    commit_type: Optional[str] = None
    scope: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None


class GitParser:
    """Parse git commits and group them by type."""

    def __init__(self, config: Config, logger: logging.Logger, repository: str, repo_path: Optional[str] = None):
        """
        Initialize the git parser.

        Args:
            config: Configuration object
            logger: Logger instance
            repository: Repository slug (e.g., "owner/repo") - required
            repo_path: Optional path to local repository (if None, will clone from repository slug)
        """
        self.config = config
        self.logger = logger
        self.repository = repository
        self.repo_path = repo_path
        self._is_temp_repo = False
        self.repo = self._init_repository()

    def _init_repository(self) -> Repo:
        """
        Initialize the git repository.
        If repo_path is provided, use it. Otherwise, clone from repository slug.

        Returns:
            Git repository object

        Raises:
            ValueError: If the path is not a valid git repository or cloning fails
        """
        # If path is provided, use existing local repository
        if self.repo_path:
            repo_path = Path(self.repo_path)

            if not repo_path.exists():
                raise ValueError(f"Repository path does not exist: {repo_path}")

            try:
                repo = Repo(repo_path)
                if repo.bare:
                    raise ValueError(f"Repository is bare: {repo_path}")

                # Fetch latest changes to ensure we're up to date
                self.logger.info(f"Fetching latest changes for {self.repository}...")
                try:
                    repo.remotes.origin.fetch()
                    self.logger.debug(f"Fetched latest changes from remote")
                except Exception as e:
                    self.logger.warning(f"Could not fetch from remote: {e}")

                self.logger.debug(f"Using existing repository at {repo_path}")
                return repo

            except InvalidGitRepositoryError:
                raise ValueError(f"Not a valid git repository: {repo_path}")

        # No path provided - clone from repository slug
        return self._clone_repository()

    def _clone_repository(self) -> Repo:
        """
        Clone repository from GitHub using the repository slug.
        Uses a cache directory to avoid re-cloning on every run.

        Returns:
            Git repository object

        Raises:
            ValueError: If cloning fails
        """
        # Create cache directory
        cache_dir = Path(".cache/repos")
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize repository name for filesystem (replace / with -)
        repo_name = self.repository.replace("/", "-")
        repo_cache_path = cache_dir / repo_name

        # Build clone URL with authentication if available
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            # Use x-access-token format for GitHub Actions
            clone_url = f"https://x-access-token:{github_token}@github.com/{self.repository}.git"
        else:
            clone_url = f"https://github.com/{self.repository}.git"

        # Check if already cloned
        if repo_cache_path.exists():
            try:
                repo = Repo(repo_cache_path)
                self.logger.info(f"Using cached repository at {repo_cache_path}")

                # Update remote URL with authentication if token is available
                if github_token:
                    repo.remotes.origin.set_url(clone_url)

                # Fetch latest changes
                self.logger.info(f"Fetching latest changes for {self.repository}...")
                repo.remotes.origin.fetch()
                self.logger.debug(f"Fetched latest changes from remote")

                self.repo_path = str(repo_cache_path)
                return repo

            except InvalidGitRepositoryError:
                # Cache is corrupted, delete and re-clone
                self.logger.warning(f"Cached repository is invalid, removing and re-cloning...")
                shutil.rmtree(repo_cache_path)

        # Clone the repository
        self.logger.info(f"Cloning repository {self.repository} to {repo_cache_path}...")
        try:
            repo = Repo.clone_from(clone_url, repo_cache_path, depth=None)
            self.logger.info(f"Successfully cloned {self.repository}")
            self.repo_path = str(repo_cache_path)
            return repo

        except GitCommandError as e:
            raise ValueError(f"Failed to clone repository {self.repository}: {e}")

    def get_commits_since_hash(
        self, last_hash: Optional[str] = None
    ) -> List[ParsedCommit]:
        """
        Get all commits since the specified hash.

        Args:
            last_hash: Hash of the last processed commit, or None for first run

        Returns:
            List of parsed commits
        """
        if last_hash is None:
            # First run: get commits from the last N days
            return self._get_commits_first_run()
        else:
            return self._get_commits_since_hash(last_hash)

    def _get_commits_first_run(self) -> List[ParsedCommit]:
        """
        Get commits for the first run (look back N days).

        Returns:
            List of parsed commits
        """
        lookback_days = self.config.first_run.lookback_days
        max_commits = self.config.first_run.max_commits

        since_date = datetime.now() - timedelta(days=lookback_days)

        self.logger.info(
            f"First run: fetching commits from the last {lookback_days} days "
            f"(max {max_commits} commits)"
        )

        try:
            commits = list(
                self.repo.iter_commits(since=since_date, max_count=max_commits)
            )

            self.logger.info(f"Found {len(commits)} commits for first run")
            return self._parse_commits(commits)

        except GitCommandError as e:
            self.logger.error(f"Error fetching commits: {e}")
            return []

    def _get_commits_since_hash(self, last_hash: str) -> List[ParsedCommit]:
        """
        Get commits since the specified hash.

        Args:
            last_hash: Hash of the last processed commit

        Returns:
            List of parsed commits
        """
        try:
            # Verify the last hash exists in the repository
            try:
                self.repo.commit(last_hash)
            except Exception:
                self.logger.warning(
                    f"Last commit hash {last_hash} not found in repository. "
                    "Falling back to date-based query."
                )
                return self._get_commits_first_run()

            # Get commits since last hash
            commits = list(self.repo.iter_commits(f"{last_hash}..HEAD"))

            self.logger.info(f"Found {len(commits)} new commits since {last_hash[:7]}")
            return self._parse_commits(commits)

        except GitCommandError as e:
            self.logger.error(f"Error fetching commits: {e}")
            return []

    def _parse_commits(self, commits) -> List[ParsedCommit]:
        """
        Parse git commit objects into ParsedCommit objects.

        Args:
            commits: List of git commit objects

        Returns:
            List of parsed commits
        """
        parsed_commits = []

        for commit in commits:
            # Skip merge commits
            if len(commit.parents) > 1:
                self.logger.debug(f"Skipping merge commit {commit.hexsha[:7]}")
                continue

            # Get commit message
            message = commit.message.strip()

            # Skip commits with skip markers
            if should_skip_commit(message):
                self.logger.debug(
                    f"Skipping commit {commit.hexsha[:7]} with skip marker"
                )
                continue

            # Try to parse as conventional commit
            parsed = parse_conventional_commit(message)

            if parsed:
                commit_type = parsed["type"]
                scope = parsed["scope"]
                description = parsed["description"]

                # Skip if type is not in config or not included
                if commit_type not in self.config.commit_types:
                    self.logger.debug(
                        f"Skipping commit {commit.hexsha[:7]} with unknown type: {commit_type}"
                    )
                    continue

                if not self.config.commit_types[commit_type].include:
                    self.logger.debug(
                        f"Skipping commit {commit.hexsha[:7]} with excluded type: {commit_type}"
                    )
                    continue

            else:
                # Not a conventional commit, categorize as "other"
                commit_type = None
                scope = None
                description = message.split("\n")[0]  # Use first line as description

            # Generate commit URL if repository is provided
            commit_url = generate_commit_url(self.repository, commit.hexsha) if self.repository else None

            # Create parsed commit
            parsed_commit = ParsedCommit(
                hash=commit.hexsha,
                short_hash=commit.hexsha[: self.config.changelog.hash_length],
                message=message,
                author=commit.author.name,
                date=datetime.fromtimestamp(commit.committed_date),
                commit_type=commit_type,
                scope=scope,
                description=description,
                url=commit_url,
            )

            parsed_commits.append(parsed_commit)

        return parsed_commits

    def group_commits_by_type(
        self, commits: List[ParsedCommit]
    ) -> Dict[str, List[ParsedCommit]]:
        """
        Group commits by their type.

        Args:
            commits: List of parsed commits

        Returns:
            Dictionary mapping commit types to lists of commits
        """
        grouped: Dict[str, List[ParsedCommit]] = {}

        for commit in commits:
            commit_type = commit.commit_type or "other"

            if commit_type not in grouped:
                grouped[commit_type] = []

            grouped[commit_type].append(commit)

        # Sort groups by the order defined in config
        sorted_grouped = {}
        for type_name in sorted(
            grouped.keys(),
            key=lambda t: self.config.commit_types.get(t).order
            if t in self.config.commit_types
            else 999,
        ):
            sorted_grouped[type_name] = grouped[type_name]

        return sorted_grouped
