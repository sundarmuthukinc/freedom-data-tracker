#!/usr/bin/env python3
"""
Freedom Mobile Data Usage Tracker
==================================
Scrapes your Freedom Mobile account for data usage and provides
weekly summaries with macOS notifications.

Requirements:
    pip install selenium webdriver-manager

Usage:
    python freedom_tracker.py              # Scrape + show summary
    python freedom_tracker.py --notify     # Scrape + show summary + send macOS notification
    python freedom_tracker.py --history    # Show all stored weekly summaries
    python freedom_tracker.py --config     # Set up your credentials
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".freedom-tracker"
DATA_FILE = CONFIG_DIR / "usage_history.json"

KEYCHAIN_SERVICE = "freedom-tracker"


def _keychain_set(account: str, value: str):
    """Store a value in macOS Keychain. Overwrites if it already exists."""
    subprocess.run(
        ["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account],
        capture_output=True,
    )
    subprocess.run(
        ["security", "add-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w", value],
        check=True,
        capture_output=True,
    )


def _keychain_get(account: str) -> str | None:
    """Retrieve a value from macOS Keychain. Returns None if not found."""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def load_config():
    """Load stored credentials from macOS Keychain."""
    phone = _keychain_get("phone")
    pin = _keychain_get("pin")
    if phone and pin:
        return {"phone": phone, "pin": pin}
    return None


def save_config(phone: str, pin: str):
    """Save credentials securely in macOS Keychain."""
    _keychain_set("phone", phone)
    _keychain_set("pin", pin)
    print("✅ Credentials saved securely in macOS Keychain.")


def setup_config():
    """Interactive credential setup."""
    print("=" * 50)
    print("Freedom Mobile Tracker — Setup")
    print("=" * 50)
    print()
    print("Login method: Phone Number + PIN")
    print()
    phone = input("Enter your Freedom Mobile phone number (e.g. 6471234567): ").strip()
    phone = phone.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    if not phone or not phone.isdigit() or len(phone) != 10:
        print("❌ Phone number must be 10 digits.")
        sys.exit(1)
    pin = input("Enter your 4-digit PIN: ").strip()
    if not pin or not pin.isdigit() or len(pin) != 4:
        print("❌ PIN must be exactly 4 digits.")
        sys.exit(1)
    save_config(phone, pin)


# ---------------------------------------------------------------------------
# Usage History Storage
# ---------------------------------------------------------------------------

def load_history() -> list:
    """Load usage history from disk."""
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_history(history: list):
    """Save usage history to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(history, f, indent=2)


def add_usage_record(usage_gb: float, plan_gb: float, cycle_start: str, cycle_end: str):
    """Add a new usage record to history."""
    history = load_history()
    record = {
        "scraped_at": datetime.now().isoformat(),
        "week_ending": datetime.now().strftime("%Y-%m-%d"),
        "usage_gb": round(usage_gb, 2),
        "plan_gb": round(plan_gb, 2),
        "remaining_gb": round(plan_gb - usage_gb, 2),
        "percent_used": round((usage_gb / plan_gb) * 100, 1) if plan_gb > 0 else 0,
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
    }
    history.append(record)
    save_history(history)
    return record


# ---------------------------------------------------------------------------
# Web Scraper (Selenium)
# ---------------------------------------------------------------------------

def scrape_freedom_mobile(phone: str, pin: str) -> dict:
    """
    Log into Freedom Mobile's My Account portal using phone number + PIN,
    handle OTP verification, and scrape data usage.

    This is always interactive — Freedom Mobile requires SMS OTP every login.

    Returns a dict with keys: usage_gb, plan_gb, cycle_start, cycle_end
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import Select
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        print("❌ Missing dependencies. Install them with:")
        print("   pip install selenium webdriver-manager")
        sys.exit(1)

    LOGIN_URL = "https://myaccount.freedommobile.ca/login"

    # Chrome opens visibly so user can watch and enter OTP
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    print("🌐 Launching browser...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # ===============================================================
        # STEP 1: Navigate to login page
        # ===============================================================
        print("🔑 Logging into Freedom Mobile...")
        driver.get(LOGIN_URL)
        time.sleep(5)

        # Ensure we're on Phone+PIN mode (not Username mode)
        try:
            phone_link = driver.find_element(By.XPATH,
                "//a[contains(text(), 'Phone Number')] | "
                "//span[contains(text(), 'Phone Number')] | "
                "//button[contains(text(), 'Phone Number')]"
            )
            if phone_link.is_displayed():
                phone_link.click()
                print("   ✓ Switched to Phone Number login mode")
                time.sleep(3)
        except Exception:
            pass

        driver.save_screenshot(str(CONFIG_DIR / "debug_step1.png"))

        # ===============================================================
        # STEP 2: Fill phone + PIN and submit
        # ===============================================================
        phone_input = driver.find_element(By.ID, "msisdnInput")
        pin_input = driver.find_element(By.ID, "pinInput")

        phone_input.click()
        time.sleep(0.3)
        phone_input.clear()
        phone_input.send_keys(phone)
        print("   ✓ Phone number entered")

        time.sleep(0.5)

        pin_input.click()
        time.sleep(0.3)
        pin_input.clear()
        pin_input.send_keys(pin)
        print("   ✓ PIN entered")

        time.sleep(1)
        driver.save_screenshot(str(CONFIG_DIR / "debug_step2_filled.png"))

        pin_input.send_keys(Keys.RETURN)
        print("   ✓ Sign In submitted")

        # ===============================================================
        # STEP 3: Handle OTP verification
        # ===============================================================
        print("   ⏳ Waiting for verification page...")
        time.sleep(10)

        current_url = driver.current_url
        print(f"   Current URL: {current_url[:80]}...")

        if "account-verification" in current_url.lower():
            print("   🔐 OTP verification required")

            # 3a: Select phone delivery from dropdown
            phone_suffix = phone[-2:]
            print(f"   Selecting phone ending in {phone_suffix}...")

            delivery_select = driver.find_element(By.ID, "maskedChannelList")
            select = Select(delivery_select)

            for option in select.options:
                val = option.get_attribute("value") or ""
                if val.endswith(phone_suffix) and "@" not in val:
                    select.select_by_value(val)
                    print(f"   ✓ Selected: {option.text.strip()}")
                    break

            time.sleep(3)
            driver.save_screenshot(str(CONFIG_DIR / "debug_verify_selected.png"))

            # 3b: Enter full phone number in the new field that appears
            print("   Entering phone number for verification...")
            all_inputs = driver.find_elements(By.TAG_NAME, "input")
            visible_inputs = [i for i in all_inputs if i.is_displayed()]
            for inp in visible_inputs:
                iid = inp.get_attribute("id") or ""
                itype = inp.get_attribute("type") or ""
                if iid in ["msisdnInput", "pinInput", "usernameInput", "passwordInput"]:
                    continue
                if itype in ["tel", "text", "number"]:
                    inp.click()
                    time.sleep(0.3)
                    inp.clear()
                    inp.send_keys(phone)
                    print(f"   ✓ Phone number entered")
                    break

            time.sleep(1)
            driver.save_screenshot(str(CONFIG_DIR / "debug_verify_phone.png"))

            # 3c: Click Next to send the SMS
            clicked_next = False
            # Try finding the orange Next button (not nav buttons)
            buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Next')]")
            for btn in buttons:
                try:
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        clicked_next = True
                        print("   ✓ Clicked Next — SMS code is being sent to your phone...")
                        break
                except Exception:
                    continue
            if not clicked_next:
                # Fallback: JS click
                for btn in buttons:
                    try:
                        if btn.is_displayed():
                            driver.execute_script("arguments[0].click();", btn)
                            clicked_next = True
                            print("   ✓ Clicked Next (JS) — SMS code is being sent...")
                            break
                    except Exception:
                        continue
            if not clicked_next:
                print("   ⚠️  Could not click Next button")

            time.sleep(5)
            driver.save_screenshot(str(CONFIG_DIR / "debug_verify_code_page.png"))

            # 3d: Ask user for the OTP code
            print()
            print("   📱 Check your phone for the SMS verification code!")
            code = input("   Enter the verification code: ").strip()

            if not code:
                raise Exception("No verification code entered.")

            # 3e: Find the code input and enter it
            code_input = None
            all_inputs = driver.find_elements(By.TAG_NAME, "input")
            for inp in all_inputs:
                if inp.is_displayed():
                    iid = inp.get_attribute("id") or ""
                    itype = inp.get_attribute("type") or ""
                    if iid in ["msisdnInput", "pinInput", "usernameInput", "passwordInput"]:
                        continue
                    if itype in ["text", "tel", "number", "password"]:
                        code_input = inp
                        break

            if code_input is None:
                raise Exception("Could not find verification code input field.")

            code_input.click()
            time.sleep(0.3)
            code_input.clear()
            code_input.send_keys(code)
            print("   ✓ Code entered")

            # 3f: Submit the code
            submitted = False
            for btn_text in ["Verify", "Submit", "Confirm", "Next"]:
                try:
                    btn = driver.find_element(By.XPATH, f"//button[contains(text(), '{btn_text}')]")
                    if btn.is_displayed():
                        btn.click()
                        submitted = True
                        print(f"   ✓ Clicked {btn_text}")
                        break
                except Exception:
                    continue
            if not submitted:
                code_input.send_keys(Keys.RETURN)
                print("   ✓ Submitted via Enter key")

            print("   ⏳ Waiting for dashboard to load...")
            time.sleep(10)

            current_url = driver.current_url
            print(f"   Current URL: {current_url[:80]}...")

        driver.save_screenshot(str(CONFIG_DIR / "debug_step3_afterlogin.png"))

        # ===============================================================
        # STEP 4: Scrape data usage from dashboard
        # ===============================================================
        time.sleep(5)
        print("📊 Scraping data usage...")

        page_source = driver.page_source

        usage_gb = None
        plan_gb = None
        cycle_start = ""
        cycle_end = ""

        # Strategy 1: Look for "X.XX GB used of Y GB" or "X.XX / Y GB"
        usage_elements = driver.find_elements(By.XPATH,
            "//*[contains(text(), 'GB') or contains(text(), 'Data') or contains(text(), 'usage')]"
        )
        for elem in usage_elements:
            text = elem.text.strip()
            if not text:
                continue

            match = re.search(r'([\d.]+)\s*GB\s*(?:used\s*)?(?:of|/)\s*([\d.]+)\s*GB', text, re.IGNORECASE)
            if match:
                usage_gb = float(match.group(1))
                plan_gb = float(match.group(2))
                break

            match = re.search(r'([\d.]+)\s*GB', text, re.IGNORECASE)
            if match and usage_gb is None:
                usage_gb = float(match.group(1))

        # Strategy 2: By CSS class names
        if usage_gb is None:
            for selector in [
                "[class*='usage']", "[class*='data-used']", "[class*='progress']",
                "[data-usage]", "[data-used]", "[class*='consumption']"
            ]:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elems:
                        text = elem.text.strip()
                        match = re.search(r'([\d.]+)\s*GB', text, re.IGNORECASE)
                        if match:
                            usage_gb = float(match.group(1))
                            break
                    if usage_gb is not None:
                        break
                except Exception:
                    continue

        # Strategy 3: Billing cycle dates
        cycle_elements = driver.find_elements(By.XPATH,
            "//*[contains(text(), 'cycle') or contains(text(), 'Cycle') or "
            "contains(text(), 'billing') or contains(text(), 'Billing')]"
        )
        for elem in cycle_elements:
            text = elem.text.strip()
            date_match = re.search(
                r'(\w{3}\s+\d{1,2}|\d{4}-\d{2}-\d{2})\s*[-\u2013to]+\s*(\w{3}\s+\d{1,2}|\d{4}-\d{2}-\d{2})',
                text
            )
            if date_match:
                cycle_start = date_match.group(1)
                cycle_end = date_match.group(2)
                break

        if usage_gb is None:
            debug_path = CONFIG_DIR / "debug_screenshot.png"
            driver.save_screenshot(str(debug_path))
            debug_html = CONFIG_DIR / "debug_page.html"
            with open(debug_html, "w") as f:
                f.write(page_source)
            print(f"⚠️  Could not find usage data on the page.")
            print(f"   Debug screenshot: {debug_path}")
            print(f"   Debug HTML: {debug_html}")
            return None

        if plan_gb is None:
            plan_gb = 0.0

        return {
            "usage_gb": usage_gb,
            "plan_gb": plan_gb,
            "cycle_start": cycle_start,
            "cycle_end": cycle_end,
        }

    except Exception as e:
        debug_path = CONFIG_DIR / "debug_screenshot.png"
        try:
            driver.save_screenshot(str(debug_path))
        except Exception:
            pass
        print(f"❌ Error during scraping: {e}")
        print(f"   Debug screenshot: {debug_path}")
        return None

    finally:
        driver.quit()
        print("🌐 Browser closed.")


# ---------------------------------------------------------------------------
# macOS Notification
# ---------------------------------------------------------------------------

def send_macos_notification(title: str, message: str, sound: str = "default"):
    """Send a macOS notification using osascript."""
    title = title.replace('"', '\\"')
    message = message.replace('"', '\\"')
    script = f'display notification "{message}" with title "{title}" sound name "{sound}"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        print(f"🔔 Notification sent!")
    except FileNotFoundError:
        print("⚠️  osascript not found — are you running this on macOS?")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Failed to send notification: {e}")


# ---------------------------------------------------------------------------
# Display / Formatting
# ---------------------------------------------------------------------------

def format_summary(record: dict) -> str:
    """Format a usage record into a readable summary."""
    lines = []
    lines.append("╔══════════════════════════════════════════╗")
    lines.append("║   📱 Freedom Mobile Weekly Data Summary  ║")
    lines.append("╠══════════════════════════════════════════╣")
    lines.append(f"║  Week Ending:  {record['week_ending']:<25} ║")
    lines.append(f"║  Data Used:    {record['usage_gb']:<6.2f} GB{' ' * 19}║")
    if record['plan_gb'] > 0:
        lines.append(f"║  Plan Total:   {record['plan_gb']:<6.2f} GB{' ' * 19}║")
        lines.append(f"║  Remaining:    {record['remaining_gb']:<6.2f} GB{' ' * 19}║")
        lines.append(f"║  Used:         {record['percent_used']:<5.1f}%{' ' * 20}║")
        bar_width = 30
        filled = int(bar_width * record['percent_used'] / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"║  [{bar}] ║")
    if record.get('cycle_start') and record.get('cycle_end'):
        cycle_str = f"{record['cycle_start']} → {record['cycle_end']}"
        lines.append(f"║  Billing Cycle: {cycle_str:<24} ║")
    lines.append("╚══════════════════════════════════════════╝")
    return "\n".join(lines)


def show_history():
    """Display all stored weekly summaries."""
    history = load_history()
    if not history:
        print("📭 No usage history found. Run a scrape first!")
        return

    print(f"\n📊 Freedom Mobile Usage History ({len(history)} records)\n")
    print(f"{'Date':<14} {'Used (GB)':>10} {'Plan (GB)':>10} {'Remaining':>10} {'% Used':>8}")
    print("─" * 56)
    for record in history:
        remaining = f"{record['remaining_gb']:.2f}" if record['plan_gb'] > 0 else "N/A"
        plan = f"{record['plan_gb']:.2f}" if record['plan_gb'] > 0 else "N/A"
        pct = f"{record['percent_used']:.1f}%" if record['plan_gb'] > 0 else "N/A"
        print(f"{record['week_ending']:<14} {record['usage_gb']:>10.2f} {plan:>10} {remaining:>10} {pct:>8}")

    if len(history) >= 2:
        last = history[-1]['usage_gb']
        prev = history[-2]['usage_gb']
        delta = last - prev
        direction = "📈" if delta > 0 else "📉"
        print(f"\n{direction} Change from last week: {delta:+.2f} GB")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Freedom Mobile Data Usage Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python freedom_tracker.py --config     # First-time setup
  python freedom_tracker.py              # Scrape and show summary
  python freedom_tracker.py --notify     # Scrape + macOS notification
  python freedom_tracker.py --history    # View past summaries
        """
    )
    parser.add_argument("--config", action="store_true", help="Set up credentials")
    parser.add_argument("--notify", action="store_true", help="Send macOS notification with summary")
    parser.add_argument("--history", action="store_true", help="Show usage history")
    args = parser.parse_args()

    if args.config:
        setup_config()
        return

    if args.history:
        show_history()
        return

    # --- Scrape mode (always interactive — OTP required every time) ---
    config = load_config()
    if config is None:
        print("❌ No configuration found. Run setup first:")
        print("   python freedom_tracker.py --config")
        sys.exit(1)

    print()
    print("🚀 Freedom Mobile Data Tracker")
    print(f"   {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
    print()

    result = scrape_freedom_mobile(config["phone"], config["pin"])

    if result is None:
        print("\n❌ Failed to scrape usage data. Check the debug files for details.")
        if args.notify:
            send_macos_notification(
                "Freedom Mobile Tracker",
                "⚠️ Failed to retrieve data usage. Check the script."
            )
        sys.exit(1)

    record = add_usage_record(
        usage_gb=result["usage_gb"],
        plan_gb=result["plan_gb"],
        cycle_start=result["cycle_start"],
        cycle_end=result["cycle_end"],
    )

    print()
    print(format_summary(record))
    print()

    if args.notify:
        if record['plan_gb'] > 0:
            notif_msg = (
                f"Used {record['usage_gb']:.2f} GB of {record['plan_gb']:.2f} GB "
                f"({record['percent_used']:.1f}%) — "
                f"{record['remaining_gb']:.2f} GB remaining"
            )
        else:
            notif_msg = f"Used {record['usage_gb']:.2f} GB this billing cycle"
        send_macos_notification("📱 Weekly Data Summary", notif_msg)


if __name__ == "__main__":
    main()
