"""
webhook_server.py — Semfee Order System
Receives WhatsApp replies, updates Google Sheet, serves dashboard data.
"""

from flask import Flask, request, jsonify
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests

app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['ngrok-skip-browser-warning'] = 'true'
    return response

# ── CONFIGURATION ────────────────────────────────────────
JSON_FILE        = "order-491416-1f9ac46ee348.json"
INSTANCE_NAME = "cs-cst-evolution-api-4b8012ae"
API_KEY       = "196ccbeae0284f18"
BASE_URL      = "https://cst-evolution-api-4b8012ae-5960d586.usecloudstation.com"
SPREADSHEET_NAME = "customer infor "
# ─────────────────────────────────────────────────────────

# Column indices (0-based)
COL_ORDER_ID = 0   # A
COL_NAME     = 1   # B
COL_PHONE    = 2   # C
COL_PRODUCT  = 3   # D
COL_PRICE    = 4   # E
COL_ADDRESS  = 6   # G
COL_STATUS   = 8   # I
COL_SENT_AT  = 10  # K
COL_REPLY    = 11  # L
COL_REPLY_AT = 12  # M# M  ← reply time


def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(JSON_FILE, scopes=scope)
    return gspread.authorize(creds).open(SPREADSHEET_NAME).sheet1


def clean_phone(number):
    n = str(number).strip().replace(" ", "").replace("-", "")
    if n.startswith("0"): n = n[1:]
    if not n.startswith("92"): n = "92" + n
    return n


def phone_to_row(sheet):
    rows = sheet.get_all_values()
    mapping = {}
    for i, row in enumerate(rows[1:], start=2):
        if len(row) > COL_PHONE and row[COL_PHONE].strip():
            mapping[clean_phone(row[COL_PHONE])] = i
    return mapping


def send_text(phone, text):
    url  = f"{BASE_URL}/message/sendText/{INSTANCE_NAME}"
    hdrs = {"apikey": API_KEY, "Content-Type": "application/json"}
    body = {
        "number": phone,
        "text": text
    }
    try:
        r = requests.post(url, json=body, headers=hdrs, timeout=8)
        print(f"  send_text status: {r.status_code} | {r.text[:100]}")
    except Exception as e:
        print(f"  Auto-reply failed: {e}")

# ── Webhook endpoint ──────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data  = request.get_json(force=True)
        event = data.get("event", "")

        if event not in ("messages.upsert", "MESSAGES_UPSERT", ""):
            return jsonify({"ok": True, "skip": "not a message event"})

        msg_data = data.get("data", data)
        message  = msg_data.get("message", {})
        key      = msg_data.get("key", {})

        if key.get("fromMe", False):
            return jsonify({"ok": True, "skip": "own message"})

        jid   = key.get("remoteJid", "")
        phone = jid.replace("@s.whatsapp.net", "").replace("@g.us", "")

        # Extract reply text
        button_id  = ""
        reply_text = ""

        if "buttonsResponseMessage" in message:
            button_id  = message["buttonsResponseMessage"].get("selectedButtonId", "")
            reply_text = message["buttonsResponseMessage"].get("selectedDisplayText", "")
        elif "conversation" in message:
            reply_text = message["conversation"]
        elif "extendedTextMessage" in message:
            reply_text = message["extendedTextMessage"].get("text", "")

        rl = reply_text.lower().strip()
        rt = reply_text.strip()

        print(f"\nIncoming from {phone} | button={button_id!r} | text={reply_text!r}")

        # Find row in sheet
        sheet   = get_sheet()
        row_map = phone_to_row(sheet)
        row_num = row_map.get(phone)

        if not row_num:
            print(f"  Phone {phone} not found in sheet")
            return jsonify({"ok": True, "skip": "phone not found"})

        ts = datetime.now().strftime("%d/%m/%Y %H:%M")

        # ── Determine status from reply ──────────────────
        # 1. CLEAN THE DATA (Critical for 1, 2, 3 replies)
        # Strip whitespace and force to string to avoid Integer vs String errors
        user_reply_text = str(rt).strip().lower() if rt else ""
        user_reply_list = str(rl).strip().lower() if rl else ""
        btn_id = str(button_id).strip() if button_id else ""

        confirm_synonyms = ["1", "yes", "confirm", "haan", "han", "ji", "ok", "done", "theek"]
        cancel_synonyms  = ["2", "no", "cancel", "nahi", "nahin", "na", "stop", "rehne den"]
        edit_synonyms    = ["3", "edit", "change", "badal", "tabdeel", "wrong", "galat"]

        if btn_id == "BTN_YES" or any(word in user_reply_text for word in confirm_synonyms):
            new_status = "Confirmed"
            response = "Shukriya! ✅ Apka order confirm ho gaya hai. Hum jald hi ship kar denge."

        elif btn_id == "BTN_NO" or any(word in user_reply_text for word in cancel_synonyms):
            new_status = "Failed"
            response = "Theek hai! Apka order cancel kar diya gaya. ❌"

        elif btn_id == "BTN_EDIT" or any(word in user_reply_text for word in edit_synonyms):
            new_status = "Edit Requested"
            response = "Zaroor! Kaunsi detail change karni hai? ✏️"

        else:
            try:
                new_status = sheet.cell(row_num, COL_STATUS + 1).value or "Msg Sent"
            except Exception:
                new_status = "Msg Sent"
            response = None

        # Send reply
        if response:
            send_text(phone, response)
            print(f"  Reply sent to {phone}")

        # Update sheet
        sheet.update_cell(row_num, COL_STATUS   + 1, new_status)
        sheet.update_cell(row_num, COL_REPLY    + 1, reply_text or button_id)
        sheet.update_cell(row_num, COL_REPLY_AT + 1, ts)

        print(f"  Row {row_num} updated to: {new_status}")
        return jsonify({"ok": True, "status": new_status})

    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# ── Dashboard API ─────────────────────────────────────────
@app.route("/api/orders", methods=["GET"])
def api_orders():
    try:
        sheet    = get_sheet()
        all_rows = sheet.get_all_values()
        orders   = []
        for i, row in enumerate(all_rows[1:], start=2):
            def safe(idx, d=""):
                return row[idx] if len(row) > idx else d
            orders.append({
                "row":      i,
                "order_id": safe(COL_ORDER_ID),
                "name":     safe(COL_NAME),
                "phone":    safe(COL_PHONE),
                "product":  safe(COL_PRODUCT),
                "price":    safe(COL_PRICE),
                "address":  safe(COL_ADDRESS),
                "status":   safe(COL_STATUS, "Pending"),
                "sent_at":  safe(COL_SENT_AT),
                "reply":    safe(COL_REPLY),
                "reply_at": safe(COL_REPLY_AT),
            })
        return jsonify(orders)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"ok": True, "time": datetime.now().isoformat()})


if __name__ == "__main__":
    print("Webhook server starting on port 5000...")
    app.run(host="0.0.0.0", port=5000, debug=False)