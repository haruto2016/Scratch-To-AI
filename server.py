"""
Scratch x Gemini AI -- server (Unicode edition)
Flask API + scratchattach cloud variable bridge + Supabase log
"""
import os, time, threading
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

# -- init clients --
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)
_models = {}

def get_model(name):
    if name not in _models:
        _models[name] = genai.GenerativeModel(name)
    return _models[name]

# -- encode/decode (5-digit Unicode) --
def decode_prompt(p1, p2):
    raw = ""
    if p1 and str(p1) != "0" and len(str(p1)) > 1: raw += str(p1).split(".")[0][1:]
    if p2 and str(p2) != "0" and len(str(p2)) > 1: raw += str(p2).split(".")[0][1:]
    
    text = ""
    for i in range(0, len(raw) - 4, 5):
        code = int(raw[i:i+5])
        if 1 <= code <= 65535:
            text += chr(code)
    return text

def chunk_response(text):
    digits = ""
    for ch in text[:350]:  # up to 350 chars (7 vars * 50 chars)
        code = ord(ch)
        if code > 65535: code = 63  # Replace invalid with '?'
        digits += f"{code:05d}"
    
    chunks = []
    for i in range(7):
        piece = digits[i*250 : (i+1)*250]
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

            try:
                cloud.set_var("☁ status", 0)
            except Exception as e:
                pass

            prev_prompt = None

            while True:
                try:
                    raw_status = cloud.get_var("☁ status")
                    status = str(raw_status).split(".")[0].strip() if raw_status is not None else "0"

                    if status == "1":
                        # Read prompt parts
                        raw_p1 = cloud.get_var("☁ p1")
                        raw_p2 = cloud.get_var("☁ p2")
                        prompt_text = decode_prompt(raw_p1, raw_p2)
                        
                        if not prompt_text:
                            time.sleep(0.3)
                            continue

                        prev_prompt = prompt_text
                        print(f"BRIDGE: Got prompt: '{prompt_text[:80]}'", flush=True)

                        cloud.set_var("☁ status", 2)  # processing
                        print("BRIDGE: Status -> 2 (processing)", flush=True)

                        # Supabase logging
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
                            reply = f"AI Connection Error: {e}"
                            db_status = "error"
                            print(f"BRIDGE: Gemini error: {e}", flush=True)

                        ms = int((time.time() - t0) * 1000)

                        if rec_id:
                            try:
                                supabase.table(TABLE).update({
                                    "response": reply, "status": db_status,
                                    "duration_ms": ms,
                                    "updated_at": datetime.utcnow().isoformat(),
                                }).eq("id", rec_id).execute()
                            except Exception:
                                pass

                        # Send response chunks
                        chunks = chunk_response(reply)
                        print(f"BRIDGE: Sending chunks...", flush=True)
                        
                        for i, chunk in enumerate(chunks):
                            cloud.set_var(f"☁ r{i+1}", chunk)
                            time.sleep(0.35)  # rate limit compliance
                            
                        cloud.set_var("☁ status", 3)  # done
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
    return jsonify({"status": "ok", "message": "Scratch x Gemini AI (Unicode Edition)"})

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

threading.Thread(target=scratch_bridge, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Server at http://localhost:{port}", flush=True)
    app.run(host="0.0.0.0", port=port)
