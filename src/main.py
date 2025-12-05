"""Main entry point for the changelog generator."""

import argparse
import sys
from datetime import datetime

from .changelog_generator import ChangelogGenerator
from .config import (
    Config,
    RepositoryConfig,
    load_config,
    load_repositories_from_env,
    setup_logging,
)
from .git_parser import GitParser
from .slack_notifier import SlackNotifier
from .state_manager import StateManager


def parse_arguments():
    """Parse command-line arguments."""
    import os

    parser = argparse.ArgumentParser(
        description="Automated Changelog Generator with Slack Notifications"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate changelog without sending to Slack or updating state",
    )

    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging (DEBUG level)"
    )

    parser.add_argument(
        "--first-run",
        action="store_true",
        help="Force first-run behavior (ignore existing state)",
    )

    parser.add_argument(
        "--console-only",
        action="store_true",
        help="Output changelog to console only (don't send to Slack)",
    )

    # Read CONFIG_PATH from environment if set, otherwise default to config.yaml
    config_path = os.getenv("CONFIG_PATH", "").strip()
    default_config = config_path if config_path else "config.yaml"
    parser.add_argument(
        "--config", default=default_config, help=f"Path to config file (default: {default_config})"
    )

    parser.add_argument(
        "--test-slack",
        action="store_true",
        help="Send a test message to Slack and exit",
    )

    return parser.parse_args()


def process_repository(
    repo: RepositoryConfig,
    config: Config,
    args,
    logger,
    total_repos: int = 1,
) -> bool:
    """
    Process a single repository.

    Args:
        repo: Repository configuration
        config: Main configuration
        args: Command-line arguments
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Processing repository: {repo.name}")
    if repo.path:
        logger.info(f"Repository path: {repo.path}")
    else:
        logger.info(f"Repository: {repo.repository} (will clone if needed)")

    try:
        # Create a modified config with repo-specific settings
        repo_config = config
        if repo.slack_webhook_url:
            # Override webhook URL if specified for this repo
            from dataclasses import replace

            repo_config = replace(config, slack_webhook_url=repo.slack_webhook_url)

        # Initialize components with repository name
        state_manager = StateManager(config.state_file, repo.name, logger)
        git_parser = GitParser(repo_config, logger, repository=repo.repository, repo_path=repo.path)
        changelog_generator = ChangelogGenerator(repo_config, logger)
        notifier = SlackNotifier(repo_config, logger)

        # Check if first run
        is_first_run = args.first_run or state_manager.is_first_run()

        if is_first_run:
            logger.info(f"First run for repository: {repo.name}")
            last_hash = None
        else:
            # Load state
            state = state_manager.load_state()
            last_hash = state.last_commit_hash
            logger.info(
                f"Last processed commit: {last_hash[:7] if last_hash else 'None'}"
            )

        # Get commits
        logger.info("Fetching commits from repository...")
        commits = git_parser.get_commits_since_hash(last_hash)

        if not commits:
            logger.info(f"No new commits found for {repo.name}")
            return True

        logger.info(f"Found {len(commits)} new commits for {repo.name}")

        # Group commits by type
        grouped_commits = git_parser.group_commits_by_type(commits)

        # Log commit breakdown
        for commit_type, type_commits in grouped_commits.items():
            logger.debug(f"  {commit_type}: {len(type_commits)} commits")

        # Generate changelog
        logger.info("Generating changelog...")

        # Generate markdown (for console output)
        markdown = changelog_generator.generate_markdown(grouped_commits, is_first_run)

        # Add repository header for multi-repo
        if total_repos > 1:
            markdown = f"# Repository: {repo.name}\n\n{markdown}"

        # Output to console if requested
        if args.console_only or args.dry_run:
            print("\n" + "=" * 80)
            print(f"Repository: {repo.name}")
            print("=" * 80)
            print(markdown)
            print("=" * 80 + "\n")

        # Send to Slack (unless dry-run or console-only)
        if not args.dry_run and not args.console_only:
            logger.info("Sending changelog to Slack...")
            payload = changelog_generator.generate_slack_payload(
                grouped_commits
            )

            # Add repository name to Slack message if multiple repos
            if total_repos > 1:
                # Insert repository name as a context block at the beginning
                repo_block = {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Repository:* {repo.name}"
                        }
                    ]
                }
                # Insert after the header (first block)
                payload["blocks"].insert(1, repo_block)

            success = notifier.send_message(payload)

            if not success:
                logger.error(f"Failed to send changelog to Slack for {repo.name}")
                logger.error("State will not be updated")
                return False

            logger.info(f"Changelog sent successfully for {repo.name}")

        # Update state (unless dry-run)
        if not args.dry_run:
            logger.info("Updating state...")

            # Get the most recent commit
            most_recent_commit = commits[0]

            success = state_manager.update_state(
                last_commit_hash=most_recent_commit.hash,
                last_commit_date=most_recent_commit.date,
                commits_processed=len(commits),
            )

            if not success:
                logger.error(f"Failed to update state for {repo.name}")
                return False

            logger.info(f"State updated successfully for {repo.name}")

        return True

    except Exception as e:
        logger.error(f"Error processing repository {repo.name}: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return False


def main():
    """Main function."""
    # Parse arguments
    args = parse_arguments()

    try:
        # Load configuration (styling only)
        config = load_config(args.config)

        # Load repositories from environment
        repositories = load_repositories_from_env()

        # Override log level if verbose
        if args.verbose:
            config.log_level = "DEBUG"

        # Setup logging
        logger = setup_logging(config.log_level)

        logger.info("Starting changelog generator")
        logger.debug(f"Configuration loaded from {args.config}")
        logger.info(f"Processing {len(repositories)} repository(ies)")

        # Test Slack connection if requested
        if args.test_slack:
            logger.info("Testing Slack webhook connection...")
            notifier = SlackNotifier(config, logger)
            success = notifier.send_test_message()
            if success:
                logger.info("Test message sent successfully!")
                return 0
            else:
                logger.error("Failed to send test message")
                return 1

        # Process each repository
        all_success = True
        for repo in repositories:
            success = process_repository(repo, config, args, logger, len(repositories))
            if not success:
                all_success = False
                logger.warning(f"Failed to process repository: {repo.name}")

        if all_success:
            logger.info("All repositories processed successfully!")
            return 0
        else:
            logger.error("Some repositories failed to process")
            return 1

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
