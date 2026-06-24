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

def send_button_message(phone, name, product, price, address):
    url = f"{BASE_URL}/message/sendText/{INSTANCE_NAME}"
    headers = {"apikey": API_KEY, "Content-Type": "application/json"}
    payload = {
        "number": phone,
        "text": (
            f"Assalam o Alaikum *{name}*! 👋\n\n"
            f"Aapka order ready hai! Confirm karne se pehle details check karein:\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📦 *Product:* {product}\n"
            f"💰 *Amount:* Rs. {price}\n"
            f"📍 *Address:* {address}\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"*Reply karein:*\n"
            f"✅ *1* → Confirm Order\n"
            f"❌ *2* → Cancel\n"
            f"✏️ *3* → Edit Info"
        )
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=12)
        return r.status_code, r.text
    except Exception as e:
        return 0, str(e)

def main():
    print("\n" + "=" * 52)
    print(f" 📦 WhatsApp Order Sender | {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 52)

    try:
        sheet = get_sheet()
        all_rows = sheet.get_all_values()
        print(f"📋 {len(all_rows)-1} data rows found.\n")

        sent = skipped = failed = 0

        for i in range(2, len(all_rows) + 1):
            row = all_rows[i - 1]
            def safe(idx, default=""):
                return row[idx].strip() if len(row) > idx else default

            name    = safe(COL_NAME, "Customer")
            phone   = safe(COL_PHONE)
            product = safe(COL_PRODUCT, "Item")
            price   = safe(COL_PRICE, "0")
            address = safe(COL_ADDRESS, "—")
            status  = safe(COL_STATUS)

            if status.lower() in SKIP_STATUSES:
                skipped += 1
                continue

            if not phone:
                skipped += 1
                continue

            cleaned = clean_phone(phone)
            print(f"Row {i:>3} | Sending to {name} → {cleaned}")

            code, resp = send_button_message(cleaned, name, product, price, address)

            if code in (200, 201):
                ts = datetime.now().strftime("%d/%m/%Y %H:%M")
                sheet.update_cell(i, COL_STATUS + 1, "Msg Sent")
                sheet.update_cell(i, COL_SENT_AT + 1, ts)
                print(f"          ✅ Sent!")
                sent += 1
            else:
                sheet.update_cell(i, COL_STATUS + 1, "Send Failed")
                print(f"          ❌ Failed HTTP {code}")
                failed += 1

            time.sleep(2.5) # Anti-spam delay

        print(f"\nDone! ✅ Sent: {sent} | ⏭ Skipped: {skipped} | ❌ Failed: {failed}")
    except Exception as e:
        print(f"❌ Critical Error: {e}")

# ── 🕒 SCHEDULER ────────────────────────────────────────

def job():
    main()

# Run every 1 minute
schedule.every(1).minutes.do(job)

if __name__ == "__main__":
    print("🚀 Automation Started. Checking for new orders every 60 seconds...")
    # Run once immediately on startup
    main()
    
    while True:
        schedule.run_pending()
        time.sleep(1)