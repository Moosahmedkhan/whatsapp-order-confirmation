# 🚀 Setup Guide — WhatsApp Order System

## Your confirmed sheet layout
| A        | B    | C     | D       | E     | F    | G       | H–I  | J           | K       | L     | M        |
|----------|------|-------|---------|-------|------|---------|------|-------------|---------|-------|----------|
| Order ID | Name | Phone | Product | Price | (–)  | Address | (–)  | Call Status | Sent At | Reply | Reply At |

Columns **J–M** are written automatically by the scripts. You don't need to create them.

---

## Step 1 — Install Python packages

```bash
pip install flask gspread google-auth requests
```

---

## Step 2 — Get a VPS (cheapest option)

**Hetzner CX21** (~€4/month) is the best value:
1. Sign up at https://hetzner.com/cloud
2. Create server → Ubuntu 22.04 → CX21
3. Note the public IP (e.g. `167.235.10.55`)

**Or use DigitalOcean** ($6/month droplet) — same steps.

---

## Step 3 — Install Docker + Evolution API on VPS

SSH into your VPS, then run:

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Create folder and docker-compose.yml
mkdir ~/evolution && cd ~/evolution

cat > docker-compose.yml << 'EOF'
version: '3'
services:
  evolution-api:
    image: atendai/evolution-api:latest
    restart: always
    ports:
      - "8080:8080"
    environment:
      SERVER_URL: "http://YOUR_VPS_IP:8080"
      AUTHENTICATION_API_KEY: "choose_a_strong_key_here"
      AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES: "true"
      DEL_INSTANCE: "false"
    volumes:
      - ./instances:/evolution/instances
EOF

docker-compose up -d
```

**Check it's running:** Open `http://YOUR_VPS_IP:8080` in browser.

---

## Step 4 — Connect WhatsApp (QR code)

```bash
# Create an instance (replace values)
curl -X POST http://YOUR_VPS_IP:8080/instance/create \
  -H "apikey: choose_a_strong_key_here" \
  -H "Content-Type: application/json" \
  -d '{"instanceName": "myshop", "qrcode": true}'
```

Then open `http://YOUR_VPS_IP:8080/instance/qrcode/myshop/base64`
and scan the QR with WhatsApp on your phone. ✅

---

## Step 5 — Upload files to VPS

Upload these 3 files to your VPS home directory:
- `webhook_server.py`
- `order-491416-1f9ac46ee348.json`  (your service account key)

```bash
# From your local machine:
scp webhook_server.py order-491416-1f9ac46ee348.json user@YOUR_VPS_IP:~/
```

---

## Step 6 — Edit config in BOTH Python files

In `send_orders.py` (run locally) and `webhook_server.py` (runs on VPS):

```python
INSTANCE_NAME    = "myshop"                          # what you named it in Step 4
API_KEY          = "choose_a_strong_key_here"        # same key from docker-compose
BASE_URL         = "http://YOUR_VPS_IP:8080"
SPREADSHEET_NAME = "customer infor "                 # keep the trailing space!
```

---

## Step 7 — Start webhook server on VPS

```bash
# SSH into VPS
pip3 install flask gspread google-auth requests

# Run in background (stays alive after you disconnect)
nohup python3 webhook_server.py > webhook.log 2>&1 &

# Verify it's running
curl http://localhost:5000/health
# Should return: {"ok": true, "time": "..."}
```

---

## Step 8 — Set Webhook URL in Evolution API

```bash
curl -X POST http://YOUR_VPS_IP:8080/webhook/set/myshop \
  -H "apikey: choose_a_strong_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://YOUR_VPS_IP:5000/webhook",
    "webhook_by_events": false,
    "events": ["MESSAGES_UPSERT"]
  }'
```

---

## Step 9 — Send your first batch

Run this **on your local machine** (where you have the Google credentials):

```bash
python3 send_orders.py
```

It will:
- Read all rows where Col J is NOT "Verified" / "Msg Sent" / "Confirmed"
- Send WhatsApp button message to each customer
- Mark Col J = "Msg Sent" + timestamp in Col K

---

## Step 10 — Open the Dashboard

Open `dashboard.html` in any browser.
Enter your server URL when prompted: `http://YOUR_VPS_IP:5000`

The dashboard will:
- Show live stats (Total / Sent / Confirmed / On Hold / Edit / Failed)
- Auto-refresh every 30 seconds
- Let you filter by status or search by name/product

---

## Full Flow Summary

```
[ Your PC ] python3 send_orders.py
     ↓  reads Sheet rows (skips Verified)
     ↓  sends WhatsApp button message
     ↓  writes "Msg Sent" + timestamp to Sheet

[ Customer ] taps ✅ Yes / ⏳ No / ✏️ Edit

[ Evolution API ] fires POST to http://YOUR_VPS_IP:5000/webhook

[ VPS: webhook_server.py ]
     ↓  finds customer by phone in Sheet
     ↓  updates Col J  →  ✅ Confirmed / ⏳ On Hold / ✏️ Edit Requested
     ↓  sends auto-reply message to customer

[ dashboard.html ] fetches /api/orders every 30s → shows live data
```

---

## Firewall — open required ports on VPS

```bash
ufw allow 8080    # Evolution API
ufw allow 5000    # Webhook server / Dashboard API
ufw allow 22      # SSH
ufw enable
```

---

## Optional: Auto-send orders daily via cron (on your local PC)

```bash
crontab -e
# Add this line (sends at 10 AM every day):
0 10 * * * cd /path/to/your/project && python3 send_orders.py >> send.log 2>&1
```
