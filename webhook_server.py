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
INSTANCE_NAME    = "cs-cst-evolution-api-c78c1665"
API_KEY          = "ea7542e2bcdd40a6"
BASE_URL         = "https://cst-evolution-api-c78c1665-3677b777.usecloudstation.com"
SPREADSHEET_NAME = "customer infor "
# ─────────────────────────────────────────────────────────

# Column indices (0-based)
COL_ORDER_ID = 0   # A
COL_NAME     = 1   # B
COL_PHONE    = 2   # C
COL_PRODUCT  = 3   # D
COL_PRICE    = 4   # E
COL_ADDRESS  = 6   # G
COL_STATUS   = 8   # I  ← Order Status
COL_SENT_AT  = 9   # J
COL_REPLY    = 11  # L  ← customer reply
COL_REPLY_AT = 12  # M  ← reply time


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
        "options": {"delay": 800, "presence": "composing"},
        "textMessage": {"text": text}
    }
    try:
        requests.post(url, json=body, headers=hdrs, timeout=8)
    except Exception as e:
        print(f"  Warning: Auto-reply failed: {e}")


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
        if button_id == "BTN_YES" or rt == "1" or "yes" in rl or "confirm" in rl or "haan" in rl:
            new_status = "Confirmed"
            send_text(phone,
                "Shukriya! Apka order confirm ho gaya hai.\n"
                "Jaldi hi apke address pe deliver kar denge.")

        elif button_id == "BTN_NO" or rt == "2" or "no" in rl or "wait" in rl or "nahi" in rl or "cancel" in rl:
            new_status = "On Hold"
            send_text(phone,
                "Theek hai! Hum wait karenge.\n"
                "Jab ready hon toh humein zaroor bataen.")

        elif button_id == "BTN_EDIT" or rt == "3" or "edit" in rl or "change" in rl or "badal" in rl:
            new_status = "Edit Requested"
            send_text(phone,
                "Zaroor! Kaunsi detail change karni hai?\n"
                "Address, product, ya kuch aur? Likh ke bhejein.")

        else:
            # Free text — keep existing status
            try:
                new_status = sheet.cell(row_num, COL_STATUS + 1).value or "Msg Sent"
            except Exception:
                new_status = "Msg Sent"

        # ── Update Google Sheet ──────────────────────────
        sheet.update_cell(row_num, COL_STATUS   + 1, new_status)
        sheet.update_cell(row_num, COL_REPLY    + 1, reply_text or button_id)
        sheet.update_cell(row_num, COL_REPLY_AT + 1, ts)

        print(f"  Row {row_num} updated to: {new_status}")
        return jsonify({"ok": True, "row": row_num, "status": new_status})

    except Exception as e:
        print(f"  Webhook error: {e}")
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


# ── Client Onboarding API ────────────────────────────────
@app.route("/api/connect-whatsapp", methods=["POST"])
def connect_whatsapp():
    """Create instance and return QR code for client to scan."""
    try:
        data = request.get_json(force=True)
        client_name = data.get("client_name", "client").strip().lower().replace(" ", "-")

        create_url = f"{BASE_URL}/instance/create"
        headers = {"apikey": API_KEY, "Content-Type": "application/json"}
        payload = {
            "instanceName": client_name,
            "channel": "evolution",
            "qrcode": True
        }
        r = requests.post(create_url, json=payload, headers=headers, timeout=15)

        if r.status_code not in (200, 201):
            return jsonify({"ok": False, "error": "Could not create instance", "detail": r.text}), 400

        result = r.json()
        qr_base64 = result.get("qrcode", {}).get("base64", "")

        return jsonify({
            "ok": True,
            "instance_name": client_name,
            "qrcode": qr_base64
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/whatsapp-status/<instance_name>", methods=["GET"])
def whatsapp_status(instance_name):
    """Check if WhatsApp instance is connected."""
    try:
        url = f"{BASE_URL}/instance/connectionState/{instance_name}"
        headers = {"apikey": API_KEY}
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        state = data.get("instance", {}).get("state", "close")
        return jsonify({"ok": True, "connected": state == "open", "state": state})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/connect-sheet", methods=["POST"])
def connect_sheet():
    """Verify the client's Google Sheet is accessible."""
    try:
        data = request.get_json(force=True)
        sheet_name = data.get("sheet_name", "").strip()

        if not sheet_name:
            return jsonify({"ok": False, "error": "Sheet name required"}), 400

        scope = ["https://spreadsheets.google.com/feeds",
                 "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(JSON_FILE, scopes=scope)
        client = gspread.authorize(creds)

        try:
            sheet = client.open(sheet_name).sheet1
            headers = sheet.row_values(1)
            row_count = max(0, len(sheet.get_all_values()) - 1)
        except gspread.SpreadsheetNotFound:
            return jsonify({
                "ok": False,
                "error": "Sheet not found. Share it with the service account email shown above first."
            }), 404

        return jsonify({
            "ok": True,
            "sheet_name": sheet_name,
            "headers": headers,
            "row_count": row_count
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/service-account-email", methods=["GET"])
def service_account_email():
    """Return the service account email the client needs to share their sheet with."""
    try:
        import json as json_lib
        with open(JSON_FILE) as f:
            data = json_lib.load(f)
        return jsonify({"ok": True, "email": data.get("client_email", "")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("Webhook server starting on port 5000...")
    app.run(host="0.0.0.0", port=5000, debug=False)
