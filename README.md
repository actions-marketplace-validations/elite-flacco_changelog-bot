# Changelog Bot Action

Automatically generate changelogs from conventional commits and send them to Slack. Perfect for keeping your team informed about code changes on a schedule.

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-Changelog%20Bot-blue.svg?colorA=24292e&colorB=0366d6&style=flat&longCache=true&logo=github)](https://github.com/marketplace/actions/changelog-bot)

## Features

- 📋 Parses conventional commit messages (`feat:`, `fix:`, `docs:`, etc.)
- 🎨 Groups commits by type with emojis
- 💬 Sends beautifully formatted messages to Slack
- ⏰ Runs automatically on a schedule via GitHub Actions
- 🔄 Tracks state to avoid duplicate notifications
- 📦 Supports multiple repositories from one workflow
- ⚙️ Fully configurable commit types and formatting
- 🔗 Includes clickable commit links to GitHub

## Quick Start

### 1. Create a Slack Webhook

1. Go to https://api.slack.com/apps
2. Click **Create New App** → **From scratch**
3. Name it "Changelog Bot" and select your workspace
4. Click **Incoming Webhooks** → Toggle **ON**
5. Click **Add New Webhook to Workspace**
6. Select your channel (e.g., `#changelog`)
7. Click **Allow** and copy the webhook URL

### 2. Add the Workflow

Create `.github/workflows/changelog.yml` in your repository:

```yaml
name: Weekly Changelog

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM UTC
  workflow_dispatch:     # Allow manual triggers

jobs:
  changelog:
    runs-on: ubuntu-latest
    steps:
      - uses: elite-flacco/changelog-bot@v1
        with:
          repositories: |
            [
              {"repository": "${{ github.repository }}", "name": "My App"}
            ]
          slack-webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### 3. Add Slack Webhook Secret

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `SLACK_WEBHOOK_URL`
4. Value: Your webhook URL from step 1
5. Click **Add secret**

### 4. Test It

1. Go to **Actions** tab
2. Select **Weekly Changelog**
3. Click **Run workflow** → **Run workflow**
4. Check your Slack channel for the changelog message!

## Usage Examples

### Current Repository Only

```yaml
- uses: elite-flacco/changelog-bot@v1
  with:
    repositories: |
      [{"repository": "${{ github.repository }}", "name": "My App"}]
    slack-webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Multiple Repositories

Track multiple repos in one workflow:

```yaml
- uses: elite-flacco/changelog-bot@v1
  with:
    repositories: |
      [
        {"repository": "org/frontend", "name": "Frontend"},
        {"repository": "org/backend", "name": "Backend"},
        {"repository": "org/mobile", "name": "Mobile App"}
      ]
    slack-webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    github-token: ${{ secrets.GH_PAT }}  # For private repos
```

### Different Slack Channels per Repository

```yaml
- uses: elite-flacco/changelog-bot@v1
  with:
    repositories: |
      [
        {
          "repository": "org/frontend",
          "name": "Frontend",
          "slack_webhook_url": "${{ secrets.SLACK_WEBHOOK_FRONTEND }}"
        },
        {
          "repository": "org/backend",
          "name": "Backend",
          "slack_webhook_url": "${{ secrets.SLACK_WEBHOOK_BACKEND }}"
        }
      ]
```

### Dry Run for Testing

Test without sending to Slack or updating state:

```yaml
- uses: elite-flacco/changelog-bot@v1
  with:
    repositories: '[{"repository": "${{ github.repository }}", "name": "Test"}]'
    slack-webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    dry-run: true
    verbose: true
```

## Configuration

### All Input Options

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `repositories` | JSON array of repositories to track | ✅ Yes | - |
| `slack-webhook-url` | Slack webhook URL (can be per-repo) | No | - |
| `github-token` | GitHub token for cloning repos | No | `${{ github.token }}` |
| `config-path` | Path to custom config.yaml file | No | Uses default |
| `dry-run` | Run without sending to Slack or updating state | No | `false` |
| `console-only` | Output to console only, skip Slack | No | `false` |
| `verbose` | Enable verbose logging | No | `false` |
| `first-run` | Force first-run behavior (30 day lookback) | No | `false` |

### Repository JSON Format

```json
[
  {
    "repository": "owner/repo",           // Required: GitHub repo slug
    "name": "Display Name",               // Required: Name shown in Slack
    "slack_webhook_url": "https://..."    // Optional: Override default webhook
  }
]
```

### Schedule Examples

Change the `cron` schedule to fit your needs:

```yaml
# Daily at 9 AM UTC
- cron: '0 9 * * *'

# Monday and Friday at 9 AM UTC
- cron: '0 9 * * 1,5'

# First day of every month at 9 AM UTC
- cron: '0 9 1 * *'

# Every 6 hours
- cron: '0 */6 * * *'
```

### Custom Configuration

Create a custom config file to change commit types, emojis, and formatting:

1. Create `.github/changelog-config.yaml`:

```yaml
# Customize which commit types to include
commit_types:
  feat:
    label: "New Features"
    emoji: "🎉"
    include: true
    order: 1
  fix:
    label: "Bug Fixes"
    emoji: "🐛"
    include: true
    order: 2
  docs:
    label: "Documentation"
    emoji: "📚"
    include: false  # Skip docs commits

# Slack formatting
slack:
  username: "Changelog Bot"
  icon_emoji: ":memo:"

# Changelog settings
changelog:
  include_author: true
  include_commit_hash: true
  hash_length: 7
  max_commits_per_type: 50
```

2. Reference it in your workflow:

```yaml
- uses: elite-flacco/changelog-bot@v1
  with:
    repositories: '[{"repository": "${{ github.repository }}", "name": "App"}]'
    slack-webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    config-path: .github/changelog-config.yaml
```

> **💡 Tip:** Check out [`.github/config.custom.yaml`](.github/config.custom.yaml) for a complete example of a custom configuration file. This example is also used in the [test workflow](.github/workflows/test-action.yml) to demonstrate the `config-path` parameter.

## Conventional Commits

This action works best with conventional commit messages:

```
<type>[optional scope]: <description>

[optional body]
```

### Supported Types

| Type | Description | Emoji |
|------|-------------|-------|
| `feat` | New features | ✨ |
| `fix` | Bug fixes | 🐛 |
| `docs` | Documentation changes | 📚 |
| `style` | Style changes (formatting, etc.) | 💎 |
| `refactor` | Code refactoring | ♻️ |
| `perf` | Performance improvements | ⚡ |
| `test` | Test additions/changes | ✅ |
| `chore` | Maintenance tasks | 🔧 |
| `ci` | CI/CD changes | 👷 |
| `build` | Build system changes | 📦 |
| `revert` | Revert previous commits | ⏪ |

### Examples

```bash
git commit -m "feat: add user authentication"
git commit -m "fix: resolve login timeout issue"
git commit -m "docs: update API documentation"
git commit -m "feat(auth): implement OAuth2 support"
git commit -m "refactor(api): simplify error handling"
```

### Skip Commits

Exclude commits from the changelog:

```bash
git commit -m "chore: update dependencies [skip changelog]"
git commit -m "WIP: testing feature [skip ci]"
```

## Private Repositories

The default `GITHUB_TOKEN` works for public repositories. For private repositories, create a Personal Access Token:

### 1. Create Fine-Grained Token (Recommended)

1. Go to **GitHub Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
2. Click **Generate new token**
3. Configure:
   - **Token name**: "Changelog Generator"
   - **Expiration**: Your preference
   - **Repository access**: Select specific repositories or all
   - **Permissions**:
     - Contents: **Read-only** ✅
     - Metadata: **Read-only** ✅ (auto-included)
4. Generate and copy the token

### 2. Add Token as Secret

Add as `GH_PAT` in **Settings** → **Secrets and variables** → **Actions**

### 3. Use in Workflow

```yaml
- uses: elite-flacco/changelog-bot@v1
  with:
    repositories: '[{"repository": "org/private-repo", "name": "Private App"}]'
    slack-webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    github-token: ${{ secrets.GH_PAT }}
```

## Example Output

The action generates Slack messages like this:

```
📋 Changelog Report
My App

Period: Nov 26 - Dec 3, 2025 | Total Commits: 5

✨ Features
• Add user authentication system (@johndoe) abc1234
• Implement dark mode toggle (@janedoe) def5678

🐛 Bug Fixes
• Fix login timeout issue (@johndoe) ghi9012
• Resolve memory leak in data processor (@bobsmith) jkl3456

📚 Documentation
• Update API documentation (@janedoe) mno7890
```

Commit hashes are clickable links to GitHub.

## How It Works

1. **Triggers** on schedule or manual workflow dispatch
2. **Clones** configured repositories (cached for performance)
3. **Fetches** latest commits from the default branch
4. **Parses** conventional commit messages
5. **Groups** commits by type (feat, fix, etc.)
6. **Formats** as Slack Block Kit message
7. **Sends** to configured Slack webhook(s)
8. **Saves** state via GitHub Actions cache to track processed commits

### State Management

- State is automatically cached between workflow runs
- Each repository has its own state file
- Cache expires after 7 days of inactivity
- On first run, looks back 30 days
- Use `first-run: true` to reset state

## Troubleshooting

### No commits appearing

**Check commit format**
- Commits must use conventional format: `type: description`
- Verify types are enabled in config (default: all enabled)

**Check for skip markers**
- Commits with `[skip changelog]` or `[skip ci]` are excluded

**Check date range**
- Use `verbose: true` to see what dates are being checked
- Use `first-run: true` to force 30-day lookback

### Slack webhook not working

**Verify the webhook**
- Test with `console-only: true` first to verify changelog generation
- Check webhook URL in secrets (no extra spaces)
- Verify webhook hasn't been revoked in Slack

**Check permissions**
- Ensure the Slack app has permission to post to the channel

### Permission errors

**For public repos**
- Default `${{ github.token }}` should work

**For private repos**
- Use Personal Access Token with Contents: Read permission
- Pass via `github-token` input

### Cache issues

**State not persisting**
- GitHub Actions cache expires after 7 days of inactivity
- This triggers first-run behavior automatically

**Reset state**
- Use `first-run: true` input to force reset
- Will look back 30 days from current date

### Multiple workflows

**Multiple changelogs**
- Create separate workflow files for different schedules
- Each workflow maintains its own cache

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Support

- **Issues**: [GitHub Issues](https://github.com/elite-flacco/changelog-bot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/elite-flacco/changelog-bot/discussions)

## License

MIT License - See [LICENSE](LICENSE) for details.

---

