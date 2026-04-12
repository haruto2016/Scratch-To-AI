"""
Scratch x Gemini AI -- server
Flask API + scratchattach cloud variable bridge + Supabase log
"""
import os, time, threading, sys
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS

try:
    from supabase import create_client
    import google.generativeai as genai
    from dotenv import load_dotenv
    load_dotenv()
except ImportError as e:
    raise SystemExit(f"pip install -r requirements.txt: {e}")

# -- config --
SUPABASE_URL   = os.environ["SUPABASE_URL"]
SUPABASE_KEY   = os.environ["SUPABASE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
DEFAULT_MODEL  = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
TABLE          = "scratch_gemini"
CHARSET = ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~'

# -- init clients --
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)
_models = {}

def get_model(name):
    if name not in _models:
        _models[name] = genai.GenerativeModel(name)
    return _models[name]

# -- encode/decode --
def encode(text):
    r = "1"
    for ch in text:
        r += str(CHARSET.index(ch) if ch in CHARSET else 0).zfill(2)
    return r

def decode(num_val):
    s = str(num_val).split(".")[0].lstrip("-")
    if len(s) < 2:
        return ""
    s = s[1:]  # skip leading "1"
    result = []
    for i in range(0, len(s) - 1, 2):
        idx = int(s[i:i+2])
        if 0 <= idx < len(CHARSET):
            result.append(CHARSET[idx])
    return "".join(result)

def chunk_response(text):
    # Only keep ASCII-representable chars, replace others with '?'
    cleaned = ""
    for ch in text[:345]:
        if ch in CHARSET:
            cleaned += ch
        elif ch == '\n':
            cleaned += ' '
        else:
            cleaned += '?'
    body = "".join(str(CHARSET.index(c)).zfill(2) for c in cleaned)
    chunks = []
    for i in range(3):
        piece = body[i*230:(i+1)*230]
        chunks.append(("1" + piece) if piece else "0")
    return chunks

# -- scratchattach bridge --
def scratch_bridge():
    user = os.environ.get("SCRATCH_USERNAME")
    pwd  = os.environ.get("SCRATCH_PASSWORD")
    pid  = os.environ.get("SCRATCH_PROJECT_ID")
    if not all([user, pwd, pid]):
        print("BRIDGE: SCRATCH_* env vars not set, bridge disabled", flush=True)
        return

    try:
        import scratchattach as sa
    except ImportError:
        print("BRIDGE: scratchattach not installed", flush=True)
        return

    print(f"BRIDGE: Starting bridge for project {pid}", flush=True)

    while True:
        try:
            print("BRIDGE: Connecting to Scratch cloud...", flush=True)
            session = sa.login(user, pwd)
            cloud = session.connect_cloud(pid)
            print(f"BRIDGE: Connected OK (project={pid})", flush=True)

            # Reset status
            try:
                cloud.set_var("status", 0)
            except Exception as e:
                print(f"BRIDGE: Reset status failed: {e}", flush=True)

            prev_prompt = None

            while True:
                try:
                    # Read status -- scratchattach uses var name WITHOUT the cloud symbol
                    raw_status = cloud.get_var("status")
                    status = str(raw_status).split(".")[0].strip() if raw_status is not None else "0"

                    if status == "1":
                        # Read prompt
                        raw_prompt = cloud.get_var("prompt")
                        prompt_str = str(raw_prompt) if raw_prompt else ""

                        if not prompt_str or prompt_str == "0" or prompt_str == prev_prompt:
                            time.sleep(0.3)
                            continue

                        prev_prompt = prompt_str
                        prompt_text = decode(prompt_str)
                        print(f"BRIDGE: Got prompt: '{prompt_text[:80]}'", flush=True)

                        # Set status=2 (processing)
                        cloud.set_var("status", 2)
                        print("BRIDGE: Status -> 2 (processing)", flush=True)

                        # Log to Supabase
                        rec_id = None
                        try:
                            res = supabase.table(TABLE).insert({
                                "prompt": prompt_text, "model": DEFAULT_MODEL,
                                "session_id": f"scratch_{pid}", "status": "pending",
                                "created_at": datetime.utcnow().isoformat(),
                            }).execute()
                            rec_id = res.data[0]["id"]
                        except Exception as e:
                            print(f"BRIDGE: DB insert error: {e}", flush=True)

                        # Call Gemini
                        t0 = time.time()
                        try:
                            reply = get_model(DEFAULT_MODEL).generate_content(prompt_text).text
                            db_status = "done"
                            print(f"BRIDGE: Gemini replied: '{reply[:80]}...'", flush=True)
                        except Exception as e:
                            reply = f"Error: {e}"
                            db_status = "error"
                            print(f"BRIDGE: Gemini error: {e}", flush=True)

                        ms = int((time.time() - t0) * 1000)

                        # Update Supabase
                        if rec_id:
                            try:
                                supabase.table(TABLE).update({
                                    "response": reply, "status": db_status,
                                    "duration_ms": ms,
                                    "updated_at": datetime.utcnow().isoformat(),
                                }).eq("id", rec_id).execute()
                            except Exception as e:
                                print(f"BRIDGE: DB update error: {e}", flush=True)

                        # Send response chunks
                        r1, r2, r3 = chunk_response(reply)
                        print(f"BRIDGE: Sending chunks (lens: {len(r1)}, {len(r2)}, {len(r3)})", flush=True)
                        cloud.set_var("resp1", r1)
                        time.sleep(0.1)
                        cloud.set_var("resp2", r2)
                        time.sleep(0.1)
                        cloud.set_var("resp3", r3)
                        time.sleep(0.3)
                        cloud.set_var("status", 3)  # done
                        print(f"BRIDGE: Status -> 3 (done, {ms}ms)", flush=True)

                    time.sleep(0.5)

                except Exception as e:
                    print(f"BRIDGE: Loop error: {e}", flush=True)
                    time.sleep(3)

        except Exception as e:
            print(f"BRIDGE: Connection error: {e} -- retry in 15s", flush=True)
            time.sleep(15)

# -- Flask --
app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Scratch x Gemini AI running"})

@app.route("/api/history")
def history():
    try:
        pid = os.environ.get("SCRATCH_PROJECT_ID", "")
        res = (supabase.table(TABLE)
               .select("prompt,response,model,duration_ms,created_at")
               .eq("session_id", f"scratch_{pid}")
               .eq("status", "done")
               .order("created_at", desc=True)
               .limit(20).execute())
        return jsonify({"history": res.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -- start --
threading.Thread(target=scratch_bridge, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Server at http://localhost:{port}", flush=True)
    app.run(host="0.0.0.0", port=port)
