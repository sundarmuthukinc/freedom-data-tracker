#!/bin/bash
# Freedom Tracker — Weekly Reminder
# Sends a macOS notification reminding you to check your data usage.
# This does NOT run the scraper (which requires OTP interaction).

osascript -e 'display notification "Open Freedom Tracker to check your data usage!" with title "📱 Freedom Mobile Reminder" subtitle "Weekly Data Check" sound name "default"'
