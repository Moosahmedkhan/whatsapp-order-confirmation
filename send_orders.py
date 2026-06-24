import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import schedule
from datetime import datetime

# ── 🔧 CONFIGURATION ────────────────────────────────────
INSTANCE_NAME = "YOUR_INSTANCE_NAME"
API_KEY       = "YOUR_API_KEY"
BASE_URL      = "http://YOUR_VPS_IP:8080"
# ────────────────────────────────────────────────────────

# Column indices (0-based)
# Column indices (0-based)
COL_ORDER_ID = 0   # A
COL_NAME     = 1   # B
COL_PHONE    = 2   # C
COL_PRODUCT  = 3   # D
COL_PRICE    = 4   # E
COL_ADDRESS  = 6   # G
COL_STATUS   = 8   # I  ← Order Status
COL_SENT_AT  = 10  # K  ← msg sent time
COL_REPLY    = 11  # L  ← customer reply
COL_REPLY_AT = 12  # M  ← customer reply time

SKIP_STATUSES = {"verified", "msg sent", "confirmed", "on hold", "edit requested", "send failed"}

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(JSON_FILE, scopes=scope)
    return gspread.authorize(creds).open(SPREADSHEET_NAME).sheet1

def clean_phone(number):
    n = str(number).strip().replace(" ", "").replace("-", "")
    if n.startswith("0"): n = n[1:]
    if not n.startswith("92"): n = "92" + n
    return n


        schedule.run_pending()
        time.sleep(1)
