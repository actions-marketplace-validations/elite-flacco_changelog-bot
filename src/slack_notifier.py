"""Slack notification via webhooks."""

import json
import logging
import time
from typing import Optional

import requests

from .config import Config


class SlackNotifier:
    """Send notifications to Slack via webhooks."""

    def __init__(self, config: Config, logger: logging.Logger):
        """
        Initialize the Slack notifier.

        Args:
            config: Configuration object
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.webhook_url = config.slack_webhook_url

    def send_message(self, payload: dict, retry_count: int = 3) -> bool:
        """
        Send a message to Slack via webhook.

        Args:
            payload: Slack message payload (blocks, text, etc.)
            retry_count: Number of times to retry on failure

        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            self.logger.error("SLACK_WEBHOOK_URL is required to send messages to Slack")
            return False

        for attempt in range(retry_count):
            try:
                self.logger.debug(
                    f"Sending message to Slack (attempt {attempt + 1}/{retry_count})"
                )

                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )

                # Check response
                if response.status_code == 200:
                    self.logger.info("Successfully sent message to Slack")
                    return True
                elif response.status_code == 429:
                    # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 5))
                    self.logger.warning(
                        f"Rate limited by Slack. Retrying after {retry_after} seconds"
                    )
                    time.sleep(retry_after)
                    continue
                else:
                    self.logger.error(
                        f"Slack webhook returned status {response.status_code}: {response.text}"
                    )

                    # If not the last attempt, wait and retry
                    if attempt < retry_count - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        self.logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        return False

            except requests.exceptions.Timeout:
                self.logger.error("Request to Slack timed out")
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt
                    self.logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    return False

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Failed to send message to Slack: {e}")
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt
                    self.logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    return False

        return False

    def send_test_message(self) -> bool:
        """
        Send a test message to Slack.

        Returns:
            True if successful, False otherwise
        """
        payload = {
            "username": self.config.slack.username,
            "icon_emoji": self.config.slack.icon_emoji,
            "text": "Test message from Changelog Bot! 🎉",
        }

        return self.send_message(payload)
