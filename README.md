# Freedom Mobile Data Usage Tracker

A macOS tool that scrapes your Freedom Mobile account for data usage and displays a summary with notifications.

> **Note:** Freedom Mobile requires SMS OTP verification on every login, so this runs on-demand (not fully automated).

## Quick Start

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd freedom-data-tracker

# 2. Run setup
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Create a Python virtual environment and install dependencies
- Prompt for your Freedom Mobile phone number and 4-digit PIN
- Store credentials securely in macOS Keychain
- Set up a weekly Friday 6 PM reminder notification
- Add a `freedom` terminal alias
- Prepare the Dock app for drag-and-drop

## 3 Ways to Run

| Method | How |
|--------|-----|
| **Dock App** | Double-click `Freedom Tracker.app` (drag it to your Dock) |
| **Terminal Alias** | Type `freedom` in any terminal window |
| **Manual** | `python3 freedom_tracker.py --notify` |

Every Friday at 6 PM, you'll get a macOS notification reminding you to run it.

## How It Works

1. **Selenium** opens a Chrome browser (visible, not headless)
2. Logs into `myaccount.freedommobile.ca` with your phone number + PIN
3. Handles OTP verification — selects your phone, sends the SMS code
4. **You enter the SMS code** when prompted in Terminal
5. Scrapes your data usage from the dashboard
6. Stores the record in `~/.freedom-tracker/usage_history.json`
7. Shows a formatted summary + sends a macOS notification

## Commands

```bash
# Run tracker + get notification
freedom                                    # alias (after setup)
python3 freedom_tracker.py --notify        # full command

# View past usage
python3 freedom_tracker.py --history

# Reconfigure credentials
python3 freedom_tracker.py --config
```

## Requirements

- **macOS** (for Keychain, notifications, and launchd)
- **Python 3.8+**
- **Google Chrome** (Selenium drives it in visible mode)
- **Freedom Mobile account** (phone number + 4-digit PIN)

## Files & Storage

| Path | Purpose |
|------|---------|
| macOS Keychain (`freedom-tracker`) | Phone number + PIN (encrypted by macOS) |
| `~/.freedom-tracker/usage_history.json` | Historical usage records |
| `~/.freedom-tracker/debug_*.png` | Debug screenshots if scraping fails |
| `~/Library/LaunchAgents/com.freedom-tracker.weekly.plist` | Friday reminder schedule |

## Scheduling

The setup script creates a `launchd` job that sends a **reminder notification** every Friday at 6 PM. It does NOT run the scraper automatically (because OTP requires your interaction).

```bash
# Stop reminders
launchctl unload ~/Library/LaunchAgents/com.freedom-tracker.weekly.plist

# Restart reminders
launchctl load ~/Library/LaunchAgents/com.freedom-tracker.weekly.plist
```

## Troubleshooting

### "Could not find usage data on the page"
Freedom Mobile may have updated their website. Check:
1. `~/.freedom-tracker/debug_screenshot.png` — what the page looks like
2. `~/.freedom-tracker/debug_page.html` — inspect elements
3. Update CSS selectors in `freedom_tracker.py`

### Login fails
- Phone number must be 10 digits (no dashes or spaces)
- Verify your PIN works at https://myaccount.freedommobile.ca/login
- Make sure Chrome is installed in `/Applications/`

### OTP not received
- Check that the correct phone number ending is selected
- Wait a minute and try again — Freedom Mobile may rate-limit SMS

## Security

- Credentials stored in **macOS Keychain** (encrypted by macOS)
- To view or delete credentials:
  ```bash
  security find-generic-password -s "freedom-tracker" -a "phone" -w
  security delete-generic-password -s "freedom-tracker" -a "phone"
  security delete-generic-password -s "freedom-tracker" -a "pin"
  ```

## Uninstall

```bash
# Remove the reminder schedule
launchctl unload ~/Library/LaunchAgents/com.freedom-tracker.weekly.plist
rm ~/Library/LaunchAgents/com.freedom-tracker.weekly.plist

# Remove stored data
rm -rf ~/.freedom-tracker

# Remove the alias from ~/.zshrc (delete the "alias freedom=..." line)

# Remove the project
rm -rf /path/to/freedom-data-tracker
```

## Setting Up on Another Computer

1. Clone the repo on the new machine
2. Make sure Python 3 and Google Chrome are installed
3. Run `./setup.sh` — it will create a fresh venv and prompt for credentials
4. Credentials are stored per-machine in macOS Keychain (not in the repo)
