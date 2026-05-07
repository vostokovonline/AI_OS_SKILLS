#!/bin/bash
# upgrade_4_extras.sh - AVATAR, WALLET, WEBHOOK
set -e

echo "✨ DEPLOYING EXTRA SERVICES (Avatar, Wallet, Webhook)..."

# ------------------------------------------
# 1. SERVICE: AVATAR (Visual Interface)
# ------------------------------------------
echo "🗣 Generating Avatar..."
cat << 'EOF' > services/avatar/requirements.txt
fastapi
uvicorn
python-dotenv
edge-tts
httpx
jinja2
python-multipart
EOF

cat << 'EOF' > services/avatar/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8005"]
EOF

cat << 'EOF' > services/avatar/main.py
import os, httpx, edge_tts, base64
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()
CORE = os.getenv("CORE_URL", "http://core:8000")

@app.get("/")
async def get():
    return HTMLResponse("""
<!DOCTYPE html><html><body style="background:#000;color:#0f0;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;font-family:monospace">
<div id="orb" style="width:200px;height:200px;border-radius:50%;background:radial-gradient(circle,#0ff,#000);box-shadow:0 0 50px #0ff;transition:all 0.2s"></div>
<button onclick="start()" style="margin-top:20px;padding:10px;background:#333;color:#fff;border:1px solid #0f0;cursor:pointer">🎤 Activate Voice</button>
<div id="status" style="margin-top:10px">System Offline</div>
<script>
    let ws = new WebSocket("ws://"+location.host+"/ws");
    let orb = document.getElementById('orb');
    
    ws.onopen = () => document.getElementById('status').innerText = "Connected. Ready.";
    
    ws.onmessage = (e) => {
        let d = JSON.parse(e.data);
        if(d.type=="audio"){
            orb.style.boxShadow = "0 0 80px #0f0";
            let a = new Audio("data:audio/mp3;base64,"+d.payload);
            a.onended = () => orb.style.boxShadow = "0 0 50px #0ff";
            a.play();
        }
        if(d.type=="text") document.getElementById('status').innerText = "AI: " + d.payload;
    };
    function start() {
        if (!('webkitSpeechRecognition' in window)) return alert("Use Chrome");
        let r = new webkitSpeechRecognition();
        r.onresult = (e) => {
            let txt = e.results[0][0].transcript;
            document.getElementById('status').innerText = "You: " + txt;
            ws.send(JSON.stringify({type:"text", payload:txt}));
            orb.style.boxShadow = "0 0 50px #f00";
        };
        r.start();
    }
</script></body></html>
""")

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    while True:
        d = await websocket.receive_json()
        async with httpx.AsyncClient(timeout=60) as c:
            # Send to Core
            r = await c.post(f"{CORE}/chat", json={"session_id":"voice", "content":d['payload']})
            txt = r.json().get("content", "Error")
            
            # Send Text back
            await websocket.send_json({"type": "text", "payload": txt})
            
            # TTS
            comm = edge_tts.Communicate(txt, "en-US-ChristopherNeural")
            audio = b""
            async for chunk in comm.stream():
                if chunk["type"] == "audio": audio += chunk["data"]
            await websocket.send_json({"type":"audio", "payload": base64.b64encode(audio).decode('utf-8')})
EOF

# ------------------------------------------
# 2. SERVICE: WALLET (Financial Agency)
# ------------------------------------------
echo "💰 Generating Wallet Service..."
mkdir -p services/wallet # Ensure dir exists

cat << 'EOF' > services/wallet/requirements.txt
fastapi
uvicorn
pydantic
EOF

cat << 'EOF' > services/wallet/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]
EOF

cat << 'EOF' > services/wallet/main.py
import os
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Sovereign Wallet")
DATA_FILE = "/app/data/balance.txt"
os.makedirs("/app/data", exist_ok=True)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f: f.write("100.00")

class Transaction(BaseModel):
    to_address: str
    amount: float

@app.get("/balance")
async def get_balance():
    with open(DATA_FILE, "r") as f: bal = float(f.read().strip())
    return {"balance": bal, "currency": "USDT", "address": "0xAI_WALLET_V1"}

@app.post("/send")
async def send(tx: Transaction):
    with open(DATA_FILE, "r") as f: bal = float(f.read().strip())
    if bal < tx.amount: return {"status": "failed", "reason": "Insufficient funds"}
    
    new_bal = bal - tx.amount
    with open(DATA_FILE, "w") as f: f.write(str(new_bal))
    return {"status": "success", "new_balance": new_bal, "tx": "0xFAKE_HASH"}
EOF

# ------------------------------------------
# 3. SERVICE: WEBHOOK (Nervous System)
# ------------------------------------------
echo "🔌 Generating Webhook Gateway..."
mkdir -p services/webhook

cat << 'EOF' > services/webhook/requirements.txt
fastapi
uvicorn
httpx
python-dotenv
EOF

cat << 'EOF' > services/webhook/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8007"]
EOF

cat << 'EOF' > services/webhook/main.py
import os, httpx
from fastapi import FastAPI, Request, BackgroundTasks

app = FastAPI()
CORE = os.getenv("CORE_URL", "http://core:8000")

async def forward_event(source, payload):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(f"{CORE}/event", json={"source": source, "payload": payload})
            print(f"Event {source} forwarded to Core.")
        except Exception as e:
            print(f"Failed to forward event: {e}")

@app.post("/trigger/{source}")
async def trigger(source: str, request: Request, bt: BackgroundTasks):
    try: body = await request.json()
    except: body = (await request.body()).decode()
    
    bt.add_task(forward_event, source, body)
    return {"status": "accepted"}
EOF

echo "✅ EXTRAS INSTALLED."
echo "👉 Now your 'docker-compose build' will succeed."
