from shiny import App, ui, render, reactive
from datetime import datetime
from pathlib import Path
import random
import pandas as pd
import os
import json
import inspect
import requests

# Optional import – if missing, app still runs but without Sheets sync
try:
    import gspread  # type: ignore
except ImportError:
    gspread = None


# --- Game constants ---
LOSS_CHANCE = 0.10          # 10% chance to suffer a loss
LOSS_PERCENTAGE = -50       # -50% result when loss happens
MIN_PROFIT_PERCENT = 20     # 20% minimum profit
MAX_PROFIT_PERCENT = 200    # 200% maximum profit
INSIDER_TRADING_BONUS = 0.10  # Optional +10% on the final total when armed
INSIDER_LOSS_MULTIPLIER = 2   # ...but doubles the chance of a loss occurring


# --- Google Sheets configuration (all via env vars) ---

# Spreadsheet ID (the long ID from the Google Sheets URL)
GOOGLE_SHEET_ID = os.getenv("GT_TAVERN_SHEET_ID", "PUT_YOUR_SHEET_ID_HERE")

# Worksheet/tab name inside the spreadsheet
GOOGLE_SHEET_TAB = os.getenv("GT_TAVERN_SHEET_TAB", "Ledger")

# Env var containing the FULL service account JSON (as one string)
SERVICE_ACCOUNT_JSON_ENV = "GT_TAVERN_SERVICE_ACCOUNT_JSON"

# Env var containing the FULL service account JSON (as one string)
SERVICE_ACCOUNT_JSON_ENV = "GT_TAVERN_SERVICE_ACCOUNT_JSON"

# Discord webhook URL (optional)
DISCORD_WEBHOOK_URL = os.getenv("GT_TAVERN_DISCORD_WEBHOOK_URL", "")

# Canonical column order we expect in Sheets
LEDGER_HEADERS = [
    "date",
    "investment",
    ...
]

# Canonical column order we expect in Sheets
LEDGER_HEADERS = [
    "date",
    "investment",
    "wheel_pct",
    "flair_pct",
    "base_outcome",
    "flair_bonus_gp",
    "net_profit",
    "final_amount",
]


def _build_gspread_client(info: dict):
    """
    Build a gspread client from a service account info dict.
    Tries service_account_from_dict first; falls back to google-auth.
    """
    if hasattr(gspread, "service_account_from_dict"):
        return gspread.service_account_from_dict(info)

    from google.oauth2.service_account import Credentials  # type: ignore

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)


def get_worksheet():
    """
    Return a gspread worksheet object for the configured spreadsheet/tab,
    or None if Sheets is not available or misconfigured.
    """
    if gspread is None:
        print("[Sheets] gspread not installed; skipping Sheets sync.")
        return None

    if not GOOGLE_SHEET_ID or GOOGLE_SHEET_ID == "PUT_YOUR_SHEET_ID_HERE":
        print("[Sheets] GT_TAVERN_SHEET_ID not set; skipping Sheets sync.")
        return None

    json_str = os.getenv(SERVICE_ACCOUNT_JSON_ENV)
    if not json_str:
        print(
            f"[Sheets] Service account JSON not found in env "
            f"{SERVICE_ACCOUNT_JSON_ENV}; skipping Sheets sync."
        )
        return None

    try:
        info = json.loads(json_str)
    except Exception as e:
        print(f"[Sheets] Failed to parse service account JSON: {e}")
        return None

    try:
        gc = _build_gspread_client(info)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
    except Exception as e:
        print(
            f"[Sheets] Failed to open spreadsheet {GOOGLE_SHEET_ID!r}: {e}"
        )
        return None

    try:
        ws = sh.worksheet(GOOGLE_SHEET_TAB)
        return ws
    except Exception as e:
        print(
            f"[Sheets] Failed to open worksheet/tab {GOOGLE_SHEET_TAB!r}: {e}"
        )
        return None


def ensure_header_row(ws):
    """
    Ensure the first row of the worksheet contains LEDGER_HEADERS.
    If the row is entirely empty, write the headers. Otherwise leave it alone.
    """
    try:
        existing = ws.row_values(1)
    except Exception as e:
        print(f"[Sheets] Failed reading header row: {e}")
        existing = []

    if not any((cell or "").strip() for cell in existing):
        try:
            ws.update("A1", [LEDGER_HEADERS])
            print("[Sheets] Wrote header row to ledger sheet.")
        except Exception as e:
            print(f"[Sheets] Failed writing header row: {e}")


def load_ledger_from_sheets():
    """
    Load ledger rows from Google Sheets and return a list of state dicts.
    Does NOT write anything to the sheet – purely a read.
    """
    ws = get_worksheet()
    if ws is None:
        return []

    try:
        ensure_header_row(ws)
        records = ws.get_all_records()  # list of dicts keyed by header row
    except Exception as e:
        print(f"[Sheets] Failed to load ledger: {e}")
        return []

    states = []
    for r in records:
        try:
            states.append(
                {
                    "date": r.get("date", "") or r.get("Date", ""),
                    "investment": float(
                        r.get("investment", r.get("Investment (gp)", 0)) or 0
                    ),
                    "wheel_pct": float(
                        r.get("wheel_pct", r.get("Fortune wheel", 0)) or 0
                    ),
                    "flair_pct": float(
                        r.get("flair_pct", r.get("Flair", 0)) or 0
                    ),
                    "base_outcome": float(r.get("base_outcome", 0) or 0),
                    "flair_bonus_gp": float(r.get("flair_bonus_gp", 0) or 0),
                    "net_profit": float(
                        r.get("net_profit", r.get("Net profit (gp)", 0)) or 0
                    ),
                    "final_amount": float(
                        r.get("final_amount", r.get("Final amount (gp)", 0)) or 0
                    ),
                }
            )
        except Exception as e:
            print(f"[Sheets] Skipping malformed row {r}: {e}")

    states.reverse()
    print(f"[Sheets] Loaded {len(states)} ledger entries from Sheets.")
    return states


def append_state_to_sheets(state: dict):
    """
    Append a single new state row to the ledger sheet.
    Does NOT clear or overwrite existing data – pure append.
    """
    ws = get_worksheet()
    if ws is None:
        return

    try:
        ensure_header_row(ws)
        row = [
            state["date"],
            state["investment"],
            state["wheel_pct"],
            state["flair_pct"],
            state["base_outcome"],
            state["flair_bonus_gp"],
            state["net_profit"],
            state["final_amount"],
        ]
        ws.append_row(row, value_input_option="RAW")
        print("[Sheets] Appended 1 ledger entry to Sheets.")

        # New: notify Discord only after a successful append
        notify_discord(state)
    except Exception as e:
        print(f"[Sheets] Failed to append row: {e}")


def notify_discord(state: dict):
    """
    Send a Discord webhook notice for the latest tavern result.
    Does nothing if DISCORD_WEBHOOK_URL is not set.
    """
    url = DISCORD_WEBHOOK_URL
    if not url:
        return

    try:
        investment = float(state.get("investment", 0) or 0)
        net_profit = float(state.get("net_profit", 0) or 0)
        final_amount = float(state.get("final_amount", 0) or 0)
        wheel_pct = float(state.get("wheel_pct", 0) or 0)

        # Profit % including flair, based on actual net profit vs investment
        if investment > 0:
            profit_pct_total = (net_profit / investment) * 100.0
        else:
            # Fallback: just use the wheel percentage if no gold was invested
            profit_pct_total = wheel_pct

        message = (
            "🏠 I have examined your tavern's financials for the tenday:\n"
            f"Profit: {profit_pct_total:.1f}%\n"
            f"Net Income: {final_amount:.0f} gp"
        )

        payload = {"content": message}
        requests.post(url, json=payload, timeout=5)
        print("[Discord] Sent tavern summary webhook.")
    except Exception as e:
        print(f"[Discord] Failed to send webhook: {e}")


# ========================= UI =========================

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.title("The Gilded Tankard — Tavern Management System"),
        ui.tags.link(
            rel="stylesheet",
            href=(
                "https://fonts.googleapis.com/css2?"
                "family=Cinzel+Decorative:wght@700&"
                "family=Spectral:wght@400;600&display=swap"
            ),
        ),
        ui.tags.script(
            """
            document.addEventListener('DOMContentLoaded', function() {
              if (window.Shiny) {
                Shiny.addCustomMessageHandler('spin_wheel', function(message) {
                  var el = document.getElementById('wheel-disc-img');
                  if (!el) return;
                  el.style.transform =
                    'translate(-50%, -50%) rotate(' + message.angle + 'deg)';
                });
              }
            });
            """
        ),
        ui.tags.style(
            """
            body {
              background: #050304;
              color: #fce7b2;
              min-height: 100vh;
              margin: 0;
            }

            ::selection {
              background: #f97316;
              color: #ffffff;
            }
            ::-moz-selection {
              background: #f97316;
              color: #ffffff;
            }

            .bg-video-container {
              position: fixed;
              inset: 0;
              overflow: hidden;
              z-index: -2;
            }

            .bg-video {
              position: absolute;
              top: 50%;
              left: 50%;
              min-width: 100%;
              min-height: 100%;
              transform: translate(-50%, -50%);
              object-fit: cover;
              filter: saturate(1.1) contrast(1.05);
            }

            .bg-overlay {
              position: fixed;
              inset: 0;
              background:
                radial-gradient(circle at top,
                  rgba(10, 6, 3, 0.15) 0,
                  rgba(3, 2, 2, 0.10) 55%);
              z-index: -1;
            }

            .app-shell {
              max-width: 1200px;
              margin: 0 auto 2rem auto;
              padding: 0 1.5rem 2rem 1.5rem;
            }

            .app-header {
              background: rgba(15, 10, 6, 0.70);
              border-bottom: 1px solid rgba(90, 60, 24, 0.8);
              box-shadow: 0 10px 30px rgba(0,0,0,0.85);
              padding: 0.8rem 0;
              margin-bottom: 1.5rem;
              backdrop-filter: blur(16px) saturate(130%);
            }

            .app-header-inner {
              max-width: 1200px;
              margin: 0 auto;
              display: flex;
              align-items: center;
              justify-content: space-between;
              padding: 0 1.5rem;
            }

            .brand-block {
              display: flex;
              align-items: center;
              gap: 0.75rem;
            }

            .brand-icon {
              width: 34px;
              height: 34px;
              border-radius: 50%;
              border: 2px solid #f5b63a;
              display: flex;
              align-items: center;
              justify-content: center;
              background: radial-gradient(circle at 30% 0%, #ffeeca, #f6b53b);
              box-shadow: 0 0 14px rgba(0,0,0,0.9);
              font-size: 1.1rem;
            }

            .brand-text-main {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.18em;
              font-size: 1.1rem;
              color: #f4d191;
            }

            .brand-text-sub {
              font-family: 'Spectral', serif;
              font-size: 0.8rem;
              letter-spacing: 0.18em;
              text-transform: uppercase;
              color: #d0a45c;
            }

            .header-tagline {
              font-family: 'Spectral', serif;
              text-transform: uppercase;
              letter-spacing: 0.16em;
              font-size: 0.75rem;
              color: #f9d474;
            }

            .main-grid {
              display: grid;
              grid-template-columns: 1.1fr 1.7fr;
              gap: 1.5rem;
            }

            .left-stack {
              display: flex;
              flex-direction: column;
              gap: 1.2rem;
            }

            .glass-panel {
              background: rgba(17, 13, 10, 0.50);
              border-radius: 12px;
              border: 1px solid rgba(107, 74, 32, 0.9);
              box-shadow: 0 18px 40px rgba(0,0,0,0.9);
              padding: 1.1rem 1.2rem;
              backdrop-filter: blur(18px) saturate(130%);
            }

            .panel-header {
              display: flex;
              align-items: center;
              gap: 0.55rem;
              margin-bottom: 0.9rem;
            }

            .panel-glyph {
              width: 24px;
              height: 24px;
              border-radius: 50%;
              border: 1px solid #f5b63a;
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 0.9rem;
              background: radial-gradient(circle at 30% 0%, #fef3d0, #f4b337);
              color: #43230b;
            }

            .panel-title {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.18em;
              font-size: 0.86rem;
              color: #f8e0a8;
            }

            .panel-caption {
              font-family: 'Spectral', serif;
              font-size: 0.78rem;
              color: #f8e0bb;
            }

            .field-label {
              font-family: 'Spectral', serif;
              font-size: 0.82rem;
              margin-bottom: 0.25rem;
              color: #fdf3cd;
            }

            .help-text {
              font-family: 'Spectral', serif;
              font-size: 0.75rem;
              color: #ffffff !important;
              margin-top: 0.25rem;
            }

            .form-control {
              background-color: rgba(22, 18, 15, 0.85);
              border-radius: 8px;
              border: 1px solid #4c3620;
              color: #fce7b2;
            }

            .form-control:focus {
              border-color: #f1b13b;
              box-shadow: 0 0 0 1px #f1b13b;
            }

            .shiny-input-radiogroup {
              margin-top: 0.5rem;
            }

            .shiny-input-radiogroup .radio {
              margin-bottom: 0.4rem;
            }

            .shiny-input-radiogroup label {
              width: 100%;
              display: flex;
              align-items: center;
              gap: 0.5rem;
              padding: 0.55rem 0.75rem;
              border-radius: 10px;
              background: rgba(24, 16, 13, 0.9);
              border: 1px solid #5f4020;
              color: #fef3d5;
              font-family: 'Spectral', serif;
              font-size: 0.84rem;
              cursor: pointer;
              justify-content: center;
              text-align: center;
            }

            .shiny-input-radiogroup label:hover {
              border-color: #f59e0b;
            }

            .shiny-input-radiogroup input[type="radio"] {
              margin-right: 0.45rem;
            }

            .wheel-panel {
              padding: 1.1rem 1.3rem 1.2rem 1.3rem;
            }

            .wheel-title {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.2em;
              font-size: 0.9rem;
              text-align: center;
              margin-bottom: 0.8rem;
              color: #f9dfaa;
            }

            .wheel-shell {
              background: transparent;
              border: none;
              padding: 0;
              backdrop-filter: none;
            }

            .wheel-wrapper {
              position: relative;
              width: 600px;
              height: 600px;
              margin: 0.3rem auto 0.2rem auto;
            }

            .wheel-disc {
              position: absolute;
              top: 50%;
              left: 50%;
              width: 600px;
              height: 600px;
              transform: translate(-50%, -50%);
              border-radius: 50%;
              background: radial-gradient(circle at center, #2b231e 0, #15100d 68%);
              box-shadow: 0 0 40px rgba(0,0,0,0.9);
              overflow: hidden;
            }

            .wheel {
              position: absolute;
              top: 50%;
              left: 50%;
              width: 220%;
              height: 220%;
              max-width: none;
              max-height: none;
              object-fit: contain;
              transform-origin: 50% 50%;
              transform: translate(-50%, -50%) rotate(0deg);
              transition: transform 4s cubic-bezier(0.22, 0.61, 0.36, 1);
              border-radius: 50%;
              border: none;
              z-index: 1;
            }

            .wheel-pointer,
            .wheel-pointer-pin {
              z-index: 5;
            }

            .wheel-pointer {
              position: absolute;
              top: -9px;
              left: 50%;
              transform: translateX(-50%);
              width: 0;
              height: 0;
              border-left: 10px solid transparent;
              border-right: 10px solid transparent;
              border-bottom: 22px solid #fef3c7;
              filter: drop-shadow(0 3px 6px rgba(0,0,0,0.9));
            }

            .wheel-pointer-pin {
              position: absolute;
              top: 10px;
              left: 50%;
              transform: translateX(-50%);
              width: 11px;
              height: 11px;
              border-radius: 50%;
              border: 2px solid #4b2c08;
              background: radial-gradient(circle at 30% 0%, #fef3c7, #fbbf24);
            }

            .wheel-center-button {
              position: absolute;
              top: 50%;
              left: 50%;
              width: 110px;
              height: 110px;
              transform: translate(-50%, -50%);
              border-radius: 50%;
              border: 2px solid rgba(68,41,13,0.9);
              background: radial-gradient(circle at 30% 0%, #fff5d1, #f5b037);
              display: flex;
              align-items: center;
              justify-content: center;
              cursor: pointer;
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.16em;
              font-size: 0.7rem;
              color: #3a2410;
              text-align: center;
              box-shadow: 0 0 20px rgba(0,0,0,1);
              z-index: 6;
            }

            .wheel-center-button:hover {
              filter: brightness(1.05);
            }

            .wheel-center-button.btn {
              border: none;
              background: transparent;
              box-shadow: none;
            }

            .wheel-center-text {
              line-height: 1.4;
            }

            .loss-warning {
              font-family: 'Spectral', serif;
              text-align: center;
              font-size: 0.78rem;
              color: #fda4af;
              margin-top: 0.4rem;
            }

            .status-text {
              margin-top: 0.45rem;
              font-family: 'Spectral', serif;
              font-size: 0.85rem;
              color: #fef3c7;
              text-align: center;
            }

            table {
              font-size: 0.8rem;
              font-family: 'Spectral', serif;
              background-color: rgba(10, 7, 5, 0.35);
              color: #ffffff;
              backdrop-filter: blur(14px) saturate(130%);
            }

            table thead tr th {
              background-color: rgba(26, 19, 15, 0.55) !important;
              color: #f9deb1 !important;
              border-bottom: 1px solid rgba(70, 48, 26, 0.9) !important;
            }

            table tbody tr td {
              background-color: rgba(12, 8, 6, 0.45) !important;
              border-color: rgba(59, 40, 22, 0.9) !important;
              color: #ffffff !important;
            }

            .table-striped > tbody > tr:nth-of-type(odd) > td {
              background-color: rgba(18, 12, 9, 0.55) !important;
            }

            .ledger-footer-text {
              font-family: 'Spectral', serif;
              font-size: 0.78rem;
              color: #f5d0a6;
              margin-top: 0.3rem;
              text-align: center;
              font-style: italic;
            }

            .section-title {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.18em;
              font-size: 0.86rem;
              margin-bottom: 0.8rem;
              color: #f9dfaa;
            }

            .modal-content {
              border-radius: 14px;
              border: 1px solid #f59e0b;
              background: radial-gradient(circle at top, #201713 0, #120e0c 65%);
              box-shadow: 0 18px 45px rgba(0,0,0,0.95);
            }

            .modal-header {
              border-bottom: none;
              padding-bottom: 0;
            }

            .modal-body {
              padding-top: 0;
            }

            .results-modal {
              font-family: 'Spectral', serif;
              color: #fef3d5;
            }

            .results-title {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.18em;
              font-size: 1.0rem;
              text-align: center;
              margin-bottom: 0.25rem;
              color: #fde68a;
            }

            .results-subtitle {
              font-size: 0.78rem;
              text-align: center;
              margin-bottom: 0.75rem;
              color: #facc85;
            }

            .results-warning {
              width: 40px;
              height: 40px;
              border-radius: 50%;
              border: 2px solid #f97316;
              display: flex;
              align-items: center;
              justify-content: center;
              color: #fed7aa;
              margin: 0 auto 0.5rem auto;
              font-size: 1.2rem;
            }

            .results-row {
              display: flex;
              justify-content: space-between;
              font-size: 0.86rem;
              margin-bottom: 0.25rem;
            }

            .results-label {
              color: #fef3d5;
            }

            .results-value {
              font-weight: 600;
            }

            .results-muted {
              font-size: 0.78rem;
              color: #a3a3c2;
              text-align: right;
            }

            .results-divider {
              border-bottom: 1px solid #31201a;
              margin: 0.6rem 0 0.6rem 0;
            }

            .results-netbox {
              margin-top: 0.4rem;
              padding: 0.65rem 0.75rem;
              border-radius: 10px;
              border: 1px solid #5f4020;
              background: radial-gradient(circle at top, #241812 0, #18100d 70%);
            }

            .results-net-label {
              font-size: 0.75rem;
              text-transform: uppercase;
              letter-spacing: 0.12em;
              color: #f97316;
            }

            .results-net-value {
              font-size: 0.95rem;
              color: #fef3d5;
            }

            .results-final-label {
              font-size: 0.78rem;
              text-transform: uppercase;
              letter-spacing: 0.12em;
              color: #fcd34d;
            }

            .results-final-value {
              font-size: 1.05rem;
              color: #facc15;
            }

            .btn-record {
              width: 100%;
              text-transform: uppercase;
              letter-spacing: 0.12em;
              font-family: 'Cinzel Decorative', serif;
              font-size: 0.8rem;
              border-radius: 999px;
              border: 1px solid #f97316;
              background: linear-gradient(135deg, #f97316, #f59e0b);
              color: #1f140c;
              margin-top: 0.8rem;
            }

            .btn-record:hover {
              filter: brightness(1.04);
            }

            /* ===== Insider Trading buff (optional, risk/reward) ===== */
            @keyframes insiderGlow {
              0%, 100% {
                box-shadow:
                  0 0 14px rgba(52, 211, 153, 0.40),
                  0 18px 40px rgba(0,0,0,0.9);
              }
              50% {
                box-shadow:
                  0 0 28px rgba(52, 211, 153, 0.85),
                  0 18px 40px rgba(0,0,0,0.9);
              }
            }

            @keyframes insiderShine {
              0% { left: -60%; }
              60%, 100% { left: 140%; }
            }

            @keyframes insiderPulse {
              0%, 100% { opacity: 0.65; }
              50% { opacity: 1; }
            }

            .insider-option {
              position: relative;
              overflow: hidden;
              border-radius: 12px;
              border: 1px solid #f59e0b;
              background: linear-gradient(
                135deg,
                rgba(67, 33, 5, 0.85),
                rgba(20, 14, 10, 0.92)
              );
              padding: 0.85rem 1rem;
              backdrop-filter: blur(18px) saturate(130%);
              box-shadow:
                0 0 14px rgba(245, 158, 11, 0.35),
                0 18px 40px rgba(0,0,0,0.9);
              transition: border-color .25s ease, background .25s ease;
            }

            .insider-option::after {
              content: "";
              position: absolute;
              top: 0;
              left: -60%;
              width: 40%;
              height: 100%;
              background: linear-gradient(
                120deg,
                transparent,
                rgba(255, 255, 255, 0.25),
                transparent
              );
              transform: skewX(-20deg);
              animation: insiderShine 3.4s ease-in-out infinite;
              pointer-events: none;
            }

            /* When the option is armed, the whole panel flips emerald and glows */
            .insider-option:has(input:checked) {
              border-color: #34d399;
              background: linear-gradient(
                135deg,
                rgba(6, 78, 59, 0.88),
                rgba(20, 14, 10, 0.92)
              );
              animation: insiderGlow 2.4s ease-in-out infinite;
            }

            .insider-option-head {
              position: relative;
              z-index: 1;
              display: flex;
              align-items: center;
              gap: 0.6rem;
              margin-bottom: 0.5rem;
            }

            .insider-option-glyph {
              width: 32px;
              height: 32px;
              border-radius: 50%;
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 1rem;
              border: 1px solid #fcd34d;
              background: radial-gradient(circle at 30% 0%, #fef3c7, #f59e0b);
              box-shadow: 0 0 12px rgba(245, 158, 11, 0.8);
              transition: all .25s ease;
            }

            .insider-option:has(input:checked) .insider-option-glyph {
              border-color: #6ee7b7;
              background: radial-gradient(circle at 30% 0%, #d1fae5, #10b981);
              box-shadow: 0 0 12px rgba(52, 211, 153, 0.85);
            }

            .insider-option-title {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.14em;
              font-size: 0.8rem;
              color: #fde68a;
            }

            .insider-option:has(input:checked) .insider-option-title {
              color: #d1fae5;
            }

            .insider-option-sub {
              font-family: 'Spectral', serif;
              font-size: 0.72rem;
              color: #fbbf24;
            }

            .insider-option:has(input:checked) .insider-option-sub {
              color: #a7f3d0;
            }

            .insider-option-flag {
              margin-left: auto;
              font-family: 'Spectral', serif;
              font-size: 0.62rem;
              letter-spacing: 0.14em;
              text-transform: uppercase;
              color: #fcd34d;
              border: 1px solid #f59e0b;
              border-radius: 999px;
              padding: 0.1rem 0.5rem;
              animation: insiderPulse 2.2s ease-in-out infinite;
            }

            .insider-option .checkbox,
            .insider-option .form-check,
            .insider-option .shiny-input-container {
              position: relative;
              z-index: 1;
              margin-bottom: 0;
            }

            .insider-option label {
              font-family: 'Spectral', serif;
              font-size: 0.82rem;
              color: #fdf3cd;
              cursor: pointer;
            }

            .insider-option input[type="checkbox"] {
              accent-color: #f59e0b;
              width: 1rem;
              height: 1rem;
              cursor: pointer;
              margin-right: 0.4rem;
            }

            .insider-option:has(input:checked) input[type="checkbox"] {
              accent-color: #10b981;
            }

            .insider-option-stats {
              position: relative;
              z-index: 1;
              display: flex;
              gap: 0.5rem;
              flex-wrap: wrap;
              margin-top: 0.55rem;
            }

            .insider-stat {
              font-family: 'Spectral', serif;
              font-size: 0.68rem;
              padding: 0.12rem 0.5rem;
              border-radius: 999px;
              letter-spacing: 0.03em;
            }

            .insider-stat.benefit {
              color: #6ee7b7;
              border: 1px solid #34d399;
              background: rgba(16, 185, 129, 0.15);
            }

            .insider-stat.risk {
              color: #fda4af;
              border: 1px solid #f43f5e;
              background: rgba(244, 63, 94, 0.15);
            }

            /* ===== Insider Trading reminder dialogue ===== */
            .insider-modal {
              font-family: 'Spectral', serif;
              color: #fef3d5;
            }

            .insider-modal-glyph {
              width: 46px;
              height: 46px;
              border-radius: 50%;
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 1.4rem;
              margin: 0 auto 0.5rem auto;
              border: 2px solid #f59e0b;
              background: radial-gradient(circle at 30% 0%, #fef3c7, #f59e0b);
              color: #3a2410;
              box-shadow: 0 0 18px rgba(245, 158, 11, 0.7);
            }

            .insider-modal-title {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.18em;
              font-size: 1rem;
              text-align: center;
              color: #fde68a;
            }

            .insider-modal-subtitle {
              font-size: 0.78rem;
              text-align: center;
              margin-bottom: 0.85rem;
              color: #facc85;
            }

            .insider-modal-benefit,
            .insider-modal-risk {
              display: flex;
              align-items: flex-start;
              gap: 0.55rem;
              padding: 0.55rem 0.7rem;
              border-radius: 10px;
              margin-bottom: 0.5rem;
              font-size: 0.84rem;
            }

            .insider-modal-benefit {
              border: 1px solid #34d399;
              background: linear-gradient(
                135deg,
                rgba(6, 78, 59, 0.55),
                rgba(20, 14, 10, 0.5)
              );
            }

            .insider-modal-risk {
              border: 1px solid #f43f5e;
              background: linear-gradient(
                135deg,
                rgba(76, 5, 25, 0.55),
                rgba(20, 14, 10, 0.5)
              );
            }

            .insider-modal-tag {
              font-family: 'Cinzel Decorative', serif;
              font-size: 0.66rem;
              letter-spacing: 0.08em;
              text-transform: uppercase;
              white-space: nowrap;
            }

            .insider-modal-tag.benefit { color: #6ee7b7; }
            .insider-modal-tag.risk { color: #fda4af; }

            .insider-modal-foot {
              text-align: center;
              font-style: italic;
              font-size: 0.78rem;
              color: #f5d0a6;
              margin-top: 0.4rem;
            }

            .btn-insider-cancel {
              text-transform: uppercase;
              letter-spacing: 0.1em;
              font-family: 'Cinzel Decorative', serif;
              font-size: 0.74rem;
              border-radius: 999px;
              border: 1px solid #6b4a20;
              background: rgba(24, 16, 13, 0.9);
              color: #fde68a;
            }

            .btn-insider-confirm {
              text-transform: uppercase;
              letter-spacing: 0.1em;
              font-family: 'Cinzel Decorative', serif;
              font-size: 0.74rem;
              border-radius: 999px;
              border: 1px solid #f43f5e;
              background: linear-gradient(135deg, #f43f5e, #f59e0b);
              color: #1f140c;
            }

            .btn-insider-confirm:hover { filter: brightness(1.05); }

            .results-insider-row {
              display: flex;
              justify-content: space-between;
              align-items: center;
              margin: 0.45rem 0 0.2rem 0;
              padding: 0.4rem 0.65rem;
              border-radius: 8px;
              border: 1px solid #34d399;
              background: linear-gradient(
                135deg,
                rgba(6, 78, 59, 0.6),
                rgba(20, 14, 10, 0.55)
              );
              animation: insiderGlow 2.8s ease-in-out infinite;
            }

            .results-insider-label {
              display: flex;
              align-items: center;
              gap: 0.4rem;
              font-size: 0.82rem;
              text-transform: uppercase;
              letter-spacing: 0.08em;
              color: #6ee7b7;
            }

            .results-insider-glyph {
              font-size: 0.95rem;
            }

            .results-insider-value {
              font-weight: 700;
              color: #a7f3d0;
              text-shadow: 0 0 10px rgba(52, 211, 153, 0.85);
            }
            """
        ),
    ),

    ui.div(
        {"class": "bg-video-container"},
        ui.tags.video(
            ui.tags.source(src="TavernBG - Trim.mp4", type="video/mp4"),
            autoplay="autoplay",
            muted="muted",
            loop="loop",
            playsinline="playsinline",
            class_="bg-video",
        ),
    ),
    ui.div({"class": "bg-overlay"}),

    ui.div(
        {"class": "app-header"},
        ui.div(
            {"class": "app-header-inner"},
            ui.div(
                {"class": "brand-block"},
                ui.div("🍺", class_="brand-icon"),
                ui.div(
                    ui.div("THE GILDED TANKARD", class_="brand-text-main"),
                    ui.div("TAVERN MANAGEMENT SYSTEM", class_="brand-text-sub"),
                ),
            ),
            ui.div("MAY FORTUNE FLAVOUR YOUR BREW", class_="header-tagline"),
        ),
    ),

    ui.div(
        {"class": "app-shell"},
        ui.div(
            {"class": "main-grid"},
            ui.div(
                {"class": "left-stack"},
                ui.div(
                    {"class": "insider-option"},
                    ui.div(
                        {"class": "insider-option-head"},
                        ui.div("🤫", class_="insider-option-glyph"),
                        ui.div(
                            ui.div("INSIDER TRADING", class_="insider-option-title"),
                            ui.div("High risk, high reward", class_="insider-option-sub"),
                        ),
                        ui.div("OPTIONAL", class_="insider-option-flag"),
                    ),
                    ui.input_checkbox(
                        "insider",
                        "Trade on privileged whispers this tenday",
                        value=False,
                    ),
                    ui.div(
                        {"class": "insider-option-stats"},
                        ui.span(
                            f"📈 +{INSIDER_TRADING_BONUS * 100:.0f}% final total",
                            class_="insider-stat benefit",
                        ),
                        ui.span(
                            f"⚠️ ×{INSIDER_LOSS_MULTIPLIER} loss chance",
                            class_="insider-stat risk",
                        ),
                    ),
                ),
                ui.div(
                    {"class": "glass-panel"},
                    ui.div(
                        {"class": "panel-header"},
                        ui.div("🪙", class_="panel-glyph"),
                        ui.div(
                            ui.div("TREASURY INVESTMENT", class_="panel-title"),
                            ui.div("Gold Pieces (gp) to invest", class_="panel-caption"),
                        ),
                    ),
                    ui.div("Gold Pieces (gp) to invest", class_="field-label"),
                    ui.input_numeric("investment", None, value=0, min=0, step=10),
                    ui.div(
                        "*Optional: Enter 0 to test fortune without gold.",
                        class_="help-text",
                    ),
                ),
                ui.div(
                    {"class": "glass-panel"},
                    ui.div(
                        {"class": "panel-header"},
                        ui.div("✨", class_="panel-glyph"),
                        ui.div(
                            ui.div("NARRATIVE FLAIR", class_="panel-title"),
                            ui.div(
                                "How well did you describe the tavern's atmosphere this tenday?",
                                class_="panel-caption",
                            ),
                        ),
                    ),
                    ui.input_radio_buttons(
                        "flair",
                        None,
                        choices={
                            "5": "Passable: 5%",
                            "10": "Good: 10%",
                            "15": "Excellent: 15%",
                        },
                        selected="5",
                    ),
                ),
            ),
            ui.div(
                ui.div(
                    {"class": "glass-panel wheel-panel"},
                    ui.div("WHEEL OF FORTUNE", class_="wheel-title"),
                    ui.div(
                        {"class": "wheel-shell"},
                        ui.div(
                            {"class": "wheel-wrapper"},
                            ui.div(
                                {"class": "wheel-disc"},
                                ui.tags.img(
                                    id="wheel-disc-img",
                                    src="Wheel.png",
                                    class_="wheel",
                                ),
                            ),
                            ui.div({"class": "wheel-pointer"}),
                            ui.div({"class": "wheel-pointer-pin"}),
                            ui.input_action_button(
                                "spin",
                                ui.HTML(
                                    "<span class='wheel-center-text'>SPIN<br>FOR GOLD</span>"
                                ),
                                class_="wheel-center-button",
                            ),
                        ),
                        ui.div("Beware the Loss sector!", class_="loss-warning"),
                    ),
                    ui.div(ui.output_text("status"), class_="status-text"),
                ),
                ui.br(),
                ui.div(
                    {"class": "glass-panel"},
                    ui.div("THE EARNINGS", class_="section-title"),
                    ui.output_table("latest_summary"),
                ),
            ),
        ),
        ui.br(),
        ui.div(
            {"class": "glass-panel"},
            ui.div("THE TAVERN LEDGER", class_="section-title"),
            ui.output_table("ledger_table"),
            ui.div(ui.output_text("ledger_message"), class_="ledger-footer-text"),
        ),
    ),
)


# ========================= SERVER =========================

def server(input, output, session):
    rotation = reactive.Value(0.0)
    last_result = reactive.Value(None)
    ledger = reactive.Value([])

    # Load existing ledger from Google Sheets on session start
    initial_ledger = load_ledger_from_sheets()
    if initial_ledger:
        ledger.set(initial_ledger)

    # When the player arms Insider Trading, remind them of the risk and reward
    @reactive.effect
    @reactive.event(input.insider)
    def _insider_warning():
        # Only prompt when the box is being ticked on, not when cleared
        if not input.insider():
            return

        modal_body = ui.div(
            {"class": "insider-modal"},
            ui.div("⚖️", class_="insider-modal-glyph"),
            ui.div("INSIDER TRADING", class_="insider-modal-title"),
            ui.div(
                "Privileged whispers, dangerous odds.",
                class_="insider-modal-subtitle",
            ),
            ui.div(
                {"class": "insider-modal-benefit"},
                ui.span("📈 Reward", class_="insider-modal-tag benefit"),
                ui.span(
                    f"An extra {INSIDER_TRADING_BONUS * 100:.0f}% is added to "
                    "your final total for the tenday."
                ),
            ),
            ui.div(
                {"class": "insider-modal-risk"},
                ui.span("⚠️ Risk", class_="insider-modal-tag risk"),
                ui.span(
                    "Your chance of a catastrophic loss "
                    f"{'doubles' if INSIDER_LOSS_MULTIPLIER == 2 else f'rises {INSIDER_LOSS_MULTIPLIER}x'}"
                    f", from {LOSS_CHANCE * 100:.0f}% to "
                    f"{LOSS_CHANCE * INSIDER_LOSS_MULTIPLIER * 100:.0f}%."
                ),
            ),
            ui.div(
                "The wheel does not forgive the greedy. Trade anyway?",
                class_="insider-modal-foot",
            ),
        )

        modal = ui.modal(
            modal_body,
            title=None,
            easy_close=False,
            footer=ui.div(
                {
                    "style": (
                        "display:flex; justify-content:flex-end; "
                        "width:100%; gap:0.5rem;"
                    )
                },
                ui.input_action_button(
                    "insider_cancel",
                    "Play it safe",
                    class_="btn btn-insider-cancel",
                ),
                ui.modal_button(
                    "Embrace the risk", class_="btn btn-insider-confirm"
                ),
            ),
            size="m",
        )
        ui.modal_show(modal)

    # "Play it safe" backs out: clear the toggle and dismiss the dialogue
    @reactive.effect
    @reactive.event(input.insider_cancel)
    def _insider_cancel():
        ui.update_checkbox("insider", value=False)
        ui.modal_remove()

    @reactive.effect
    @reactive.event(input.spin)
    async def _spin_wheel():
        investment = float(input.investment() or 0.0)
        flair_pct = int(input.flair() or "0")
        use_insider = bool(input.insider())

        # Determine loss vs profit. Insider trading doubles the loss chance,
        # though the drawn loss wedge on the wheel stays the same size.
        effective_loss_chance = (
            LOSS_CHANCE * INSIDER_LOSS_MULTIPLIER if use_insider else LOSS_CHANCE
        )
        is_loss = random.random() < effective_loss_chance
        loss_degrees = 360 * LOSS_CHANCE
        profit_degrees = 360 - loss_degrees

        if is_loss:
            result_pct = LOSS_PERCENTAGE
            margin = 2
            target_angle = margin + random.random() * (loss_degrees - 2 * margin)
        else:
            u = random.random()
            result_pct = MIN_PROFIT_PERCENT + u * (
                MAX_PROFIT_PERCENT - MIN_PROFIT_PERCENT
            )
            target_angle = loss_degrees + u * profit_degrees

        # Rotate wheel so the chosen sector ends up under the pointer at 90°
        extra_spins = 360 * random.randint(4, 7)
        final_rot = rotation() + extra_spins + (90 - target_angle)
        rotation.set(final_rot)

        # Safe await for send_custom_message (handles both sync/async versions)
        maybe_coro = session.send_custom_message("spin_wheel", {"angle": final_rot})
        if inspect.isawaitable(maybe_coro):
            await maybe_coro

        # Earnings maths
        base_profit = investment * (result_pct / 100.0)
        base_outcome = investment + base_profit
        flair_bonus_gp = base_outcome * (flair_pct / 100.0)
        final_with_flair = base_outcome + flair_bonus_gp

        # Optional Insider Trading bonus: +10% on the running total, only if armed
        insider_bonus_gp = (
            final_with_flair * INSIDER_TRADING_BONUS if use_insider else 0.0
        )
        final_total = final_with_flair + insider_bonus_gp
        net_profit = final_total - investment

        state = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "investment": investment,
            "wheel_pct": result_pct,
            "flair_pct": flair_pct,
            "base_outcome": base_outcome,
            "flair_bonus_gp": flair_bonus_gp,
            "insider_bonus_gp": insider_bonus_gp,
            "insider_used": use_insider,
            "net_profit": net_profit,
            "final_amount": final_total,
        }

        # Update in-memory ledger (newest first)
        current = ledger()
        ledger.set([state] + current)
        last_result.set(state)

        # Append to Google Sheets (no overwrites)
        append_state_to_sheets(state)

        # Tenday Results modal
        sign = "+" if result_pct >= 0 else ""
        wheel_str = f"{sign}{result_pct:.1f}%"
        flair_str = f"+{flair_pct}%"

        # Only surface the Insider Trading line when the option was actually armed
        if use_insider:
            insider_section = ui.TagList(
                ui.div(
                    {"class": "results-insider-row"},
                    ui.div(
                        {"class": "results-insider-label"},
                        ui.span("🤫", class_="results-insider-glyph"),
                        ui.span("Insider Trading"),
                    ),
                    ui.span(
                        f"+{INSIDER_TRADING_BONUS * 100:.0f}%",
                        class_="results-insider-value",
                    ),
                ),
                ui.div(
                    {"class": "results-muted"},
                    f"(Added {insider_bonus_gp:.0f} gp to gross total)",
                ),
            )
        else:
            insider_section = ui.TagList()

        modal_body = ui.div(
            {"class": "results-modal"},
            ui.div("!", class_="results-warning"),
            ui.div("TENDAY RESULTS", class_="results-title"),
            ui.div("The wheel has spoken!", class_="results-subtitle"),
            ui.div(
                {"class": "results-row"},
                ui.span("Initial Investment:", class_="results-label"),
                ui.span(f"{investment:.0f} gp", class_="results-value"),
            ),
            ui.div(
                {"class": "results-row"},
                ui.span("Wheel Result:", class_="results-label"),
                ui.span(wheel_str, class_="results-value"),
            ),
            ui.div(
                {"class": "results-row"},
                ui.span("Base Outcome:", class_="results-label"),
                ui.span(f"{base_outcome:.0f} gp", class_="results-value"),
            ),
            ui.div(
                {"class": "results-row"},
                ui.span("Narrative Flair Bonus:", class_="results-label"),
                ui.span(flair_str, class_="results-value"),
            ),
            ui.div(
                {"class": "results-muted"},
                f"(Added {flair_bonus_gp:.0f} gp to gross total)",
            ),
            insider_section,
            ui.div(class_="results-divider"),
            ui.div(
                {"class": "results-netbox"},
                ui.div(
                    ui.span("NET PROFIT", class_="results-net-label"),
                    ui.span(f"{net_profit:.0f} gp", class_="results-net-value"),
                ),
                ui.div(
                    {
                        "style": (
                            "margin-top:0.35rem; display:flex; "
                            "justify-content:space-between;"
                        )
                    },
                    ui.span("FINAL AMOUNT", class_="results-final-label"),
                    ui.span(
                        f"{final_total:.0f} gp", class_="results-final-value"
                    ),
                ),
            ),
        )

        modal = ui.modal(
            modal_body,
            title=None,
            easy_close=True,
            footer=ui.modal_button("Record in Ledger", class_="btn btn-record"),
            size="m",
        )
        ui.modal_show(modal)

    @render.text
    def status():
        res = last_result()
        if res is None:
            rows = ledger()
            if rows:
                return (
                    f"{len(rows)} historical entries loaded from the ledger. "
                    "Spin again to tempt fate."
                )
            return "The ledger is empty. Spin the wheel to record business."

        pct = res["wheel_pct"]
        net = res["net_profit"]
        flair_pct = res["flair_pct"]

        if pct < 0:
            return (
                f"Loss of {pct:.1f}% — down roughly {abs(net):.1f} gp, "
                f"even with {flair_pct}% narrative flair."
            )
        else:
            return (
                f"Gain of {pct:.1f}% — about {net:.1f} gp profit after a "
                f"{flair_pct}% flair bonus."
            )

    @render.table
    def latest_summary():
        res = last_result()
        cols = [
            "Investment (gp)",
            "Fortune wheel",
            "Flair",
            "Net profit (gp)",
            "Final amount (gp)",
        ]
        if res is None:
            return pd.DataFrame(columns=cols)
        row = {
            "Investment (gp)": round(res["investment"], 1),
            "Fortune wheel": f"{res['wheel_pct']:.1f}%",
            "Flair": f"+{res['flair_pct']}%",
            "Net profit (gp)": round(res["net_profit"], 1),
            "Final amount (gp)": round(res["final_amount"], 1),
        }
        return pd.DataFrame([row], columns=cols)

    @render.table
    def ledger_table():
        rows = ledger()
        cols = [
            "Date",
            "Investment (gp)",
            "Fortune wheel",
            "Flair",
            "Net profit (gp)",
            "Final amount (gp)",
        ]
        if not rows:
            return pd.DataFrame(columns=cols)
        display_rows = [
            {
                "Date": r["date"],
                "Investment (gp)": round(r["investment"], 1),
                "Fortune wheel": f"{r['wheel_pct']:.1f}%",
                "Flair": f"+{r['flair_pct']}%",
                "Net profit (gp)": round(r["net_profit"], 1),
                "Final amount (gp)": round(r["final_amount"], 1),
            }
            for r in rows
        ]
        return pd.DataFrame(display_rows, columns=cols)

    @render.text
    def ledger_message():
        if not ledger():
            return "The ledger is empty. Spin the wheel to record business."
        return ""


assets_dir = Path(__file__).parent / "assets"
app = App(app_ui, server, static_assets=assets_dir)
