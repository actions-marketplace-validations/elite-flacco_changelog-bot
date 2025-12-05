"""State management for tracking processed commits."""

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class State:
    """State tracking for changelog generation."""

    repository_name: Optional[str] = None
    last_commit_hash: Optional[str] = None
    last_run_timestamp: Optional[str] = None
    last_commit_date: Optional[str] = None
    total_commits_processed: int = 0
    run_count: int = 0


class StateManager:
    """Manages reading and writing state to track changelog progress."""

    def __init__(
        self, state_file: str, repository_name: str, logger: logging.Logger
    ):
        """
        Initialize the state manager.

        Args:
            state_file: Base path to the state file (e.g., "data/state.json")
            repository_name: Name/identifier of the repository
            logger: Logger instance
        """
        self.repository_name = repository_name
        self.logger = logger

        # Generate per-repo state file name
        # e.g., data/state.json -> data/state.my-repo.json
        base_path = Path(state_file)
        state_dir = base_path.parent
        state_filename = f"state.{self._sanitize_repo_name(repository_name)}.json"
        self.state_file = state_dir / state_filename

    def _sanitize_repo_name(self, name: str) -> str:
        """
        Sanitize repository name for use in filenames.

        Args:
            name: Repository name

        Returns:
            Sanitized name safe for filenames
        """
        # Replace invalid filename characters with hyphens
        import re

        sanitized = re.sub(r"[^\w\-.]", "-", name)
        return sanitized.lower()

    def load_state(self) -> State:
        """
        Load state from file.

        Returns:
            State object, either loaded from file or a new empty state
        """
        if not self.state_file.exists():
            self.logger.info("No state file found. This appears to be the first run.")
            return State()

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            state = State(
                repository_name=data.get("repository_name", self.repository_name),
                last_commit_hash=data.get("last_commit_hash"),
                last_run_timestamp=data.get("last_run_timestamp"),
                last_commit_date=data.get("last_commit_date"),
                total_commits_processed=data.get("total_commits_processed", 0),
                run_count=data.get("run_count", 0),
            )

            self.logger.debug(f"Loaded state from {self.state_file}")
            self.logger.debug(
                f"Repository: {state.repository_name}, "
                f"Last commit hash: {state.last_commit_hash}, Run count: {state.run_count}"
            )

            return state

        except json.JSONDecodeError as e:
            self.logger.warning(
                f"Failed to parse state file {self.state_file}: {e}. Treating as first run."
            )
            return State()
        except Exception as e:
            self.logger.error(
                f"Error loading state file {self.state_file}: {e}. Treating as first run."
            )
            return State()

    def save_state(self, state: State) -> bool:
        """
        Save state to file atomically.

        Args:
            state: State object to save

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert state to dict
            state_dict = asdict(state)

            # Write to temporary file first (atomic operation)
            fd, temp_path = tempfile.mkstemp(
                dir=self.state_file.parent, prefix=".state_", suffix=".tmp"
            )

            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(state_dict, f, indent=2)

                # Replace old file with new file atomically
                os.replace(temp_path, self.state_file)

                self.logger.debug(f"Saved state to {self.state_file}")
                return True

            except Exception as e:
                # Clean up temp file if something went wrong
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
                raise e

        except Exception as e:
            self.logger.error(f"Failed to save state to {self.state_file}: {e}")
            return False

    def update_state(
        self,
        last_commit_hash: str,
        last_commit_date: datetime,
        commits_processed: int,
    ) -> bool:
        """
        Update state with new information.

        Args:
            last_commit_hash: Hash of the last processed commit
            last_commit_date: Date of the last processed commit
            commits_processed: Number of commits processed in this run

        Returns:
            True if successful, False otherwise
        """
        # Load current state
        state = self.load_state()

        # Update fields
        state.repository_name = self.repository_name
        state.last_commit_hash = last_commit_hash
        state.last_run_timestamp = datetime.now().isoformat()
        state.last_commit_date = last_commit_date.isoformat()
        state.total_commits_processed += commits_processed
        state.run_count += 1

        # Save updated state
        return self.save_state(state)

    def is_first_run(self) -> bool:
        """
        Check if this is the first run (no state file exists or no last commit hash).

        Returns:
            True if first run, False otherwise
        """
        if not self.state_file.exists():
            return True

        state = self.load_state()
        return state.last_commit_hash is None
