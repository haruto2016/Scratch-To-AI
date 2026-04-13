import json
import zipfile
import hashlib
import io
import os

# ---------------------------------------------------------
# Asset Generators (SVGs for beautiful UI)
# ---------------------------------------------------------

SVG_BACKDROP = """<svg width="480" height="360" xmlns="http://www.w3.org/2000/svg">
    <rect width="480" height="360" fill="#F0F4F9"/>
    
    <!-- Top Bar -->
    <path d="M15 17 h14 M15 22 h14 M15 27 h14" stroke="#444746" stroke-width="2" stroke-linecap="round"/>
    
    <!-- Gemini Logo (Sparkle + Text) -->
    <path d="M54 12 c0 4, 3 6, 6 6 c-3 0, -6 2, -6 6 c0 -4, -3 -6, -6 -6 c3 0, 6 -2, 6 -6" fill="#4B8BF5"/>
    <text x="65" y="27" font-family="'Segoe UI', Roboto, sans-serif" font-size="20" fill="#444746" font-weight="600">Gemini</text>
    
    <!-- Greeting -->
    <text x="40" y="65" font-family="'Segoe UI', Roboto, sans-serif" font-size="22" fill="#444746" font-weight="bold">こんにちは！</text>
    <text x="40" y="95" font-family="'Segoe UI', Roboto, sans-serif" font-size="22" fill="#8E918F" font-weight="bold">何から始めますか？</text>
    
    <!-- List Background Cover -->
    <rect x="20" y="110" width="440" height="180" rx="12" fill="#FFFFFF"/>
    
    <!-- Input box pill -->
    <rect x="15" y="300" width="450" height="45" rx="22.5" fill="#FFFFFF" stroke="#E3E3E3" stroke-width="1"/>
    
    <!-- Plus icon for input -->
    <path d="M35 322.5 h10 M40 317.5 v10" stroke="#444746" stroke-width="2" stroke-linecap="round"/>
    
    <!-- Input placeholder text -->
    <text x="60" y="327" font-family="'Segoe UI', Roboto, sans-serif" font-size="14" fill="#8E918F">Gemini に相談</text>
    
    <!-- Microphone icon -->
    <path d="M435 315 v4 a5 5 0 0 0 10 0 v-4 a5 5 0 0 0 -10 0 M432 320 a8 8 0 0 0 16 0 M440 328 v4" stroke="#444746" fill="none" stroke-width="1.5" stroke-linecap="round"/>
</svg>"""

SVG_SPARKLE = """<svg width="60" height="60" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="geminiGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#4B8BF5"/>
            <stop offset="50%" stop-color="#A15BB4"/>
            <stop offset="100%" stop-color="#D96570"/>
        </linearGradient>
    </defs>
    <path d="M50 0 C50 30, 76 50, 100 50 C76 50, 50 70, 50 100 C50 70, 24 50, 0 50 C24 50, 50 30, 50 0 Z" fill="url(#geminiGrad)"/>
</svg>"""

SVG_EMPTY = """<svg version="1.1" width="2" height="2" viewBox="-1 -1 2 2" xmlns="http://www.w3.org/2000/svg"></svg>"""

def md5_svg(svg_data):
    b = svg_data.encode("utf-8")
    return hashlib.md5(b).hexdigest() + ".svg", b

# ---------------------------------------------------------
# Block Builder Utility
# ---------------------------------------------------------

def iN(num): return [1, [4, str(num)]]                 # Number
def iP(num): return [1, [5, str(num)]]                 # Number (positive)
def iS(txt): return [1, [10, str(txt)]]                 # String
def iB(blk_id): return [2, blk_id]                      # Block (Boolean/Reporter)
def iR(blk_id): return [3, blk_id, [10, ""]]            # Reporter with fallback

class B:
    def __init__(self):
        self.blocks = {}
        self.next_id = 1

    def gen_id(self):
        res = f"B_{self.next_id:04d}"
        self.next_id += 1
        return res

    def _blk(self, op, inputs, fields, parent=None, next=None, top=False, shadow=False):
        uid = self.gen_id()
        self.blocks[uid] = {
            "opcode": op,
            "next": next,
            "parent": parent,
            "inputs": inputs,
            "fields": fields,
            "shadow": shadow,
            "topLevel": top
        }
        return uid

    def _chain(self, blks, parent=None, top=False):
        if not blks: return None
        for i in range(len(blks)-1):
            self.blocks[blks[i]]["next"] = blks[i+1]
        self.blocks[blks[0]]["topLevel"] = top
        return blks[0]

    def var(self, name, id): return self._blk("data_variable", {}, {"VARIABLE": [name, id]})
    def list_contents(self, name, id): return self._blk("data_listcontents", {}, {"LIST": [name, id]})

    # Event / Control
    def flag(self): return self._blk("event_whenflagclicked", {}, {}, top=True)
    def forever(self, sub): return self._blk("control_forever", {"SUBSTACK": iB(sub)}, {})
    def repeat_until(self, cond, sub): return self._blk("control_repeat_until", {"CONDITION": iB(cond), "SUBSTACK": iB(sub)}, {})
    def wait(self, sec): return self._blk("control_wait", {"DURATION": iP(sec)}, {})
    def repeat(self, times, sub): return self._blk("control_repeat", {"TIMES": iN(times), "SUBSTACK": iB(sub)}, {})

    # Data / Variables
    def set_var(self, name, id, val): return self._blk("data_setvariableto", {"VALUE": val}, {"VARIABLE": [name, id]})
    def change_var(self, name, id, val): return self._blk("data_changevariableby", {"VALUE": val}, {"VARIABLE": [name, id]})
    def get_var(self, name, id): return self._blk("data_variable", {}, {"VARIABLE": [name, id]})

    # Looks / Motion
    def say(self, txt): return self._blk("looks_say", {"MESSAGE": txt}, {})
    def hide(self): return self._blk("looks_hide", {}, {})
    def show(self): return self._blk("looks_show", {}, {})
    def goto(self, x, y): return self._blk("motion_gotoxy", {"X": iN(x), "Y": iN(y)}, {})
    def turn_right(self, deg): return self._blk("motion_turnright", {"DEGREES": iN(deg)}, {})
    def point_dir(self, deg): return self._blk("motion_pointindirection", {"DIRECTION": iN(deg)}, {})

    # Sensing
    def ask_wait(self, q): return self._blk("sensing_askandwait", {"QUESTION": q}, {})
    def answer(self): return self._blk("sensing_answer", {}, {})

    # Operators
    def join_(self, s1, s2): return self._blk("operator_join", {"STRING1": s1, "STRING2": s2}, {})
    def gt_(self, o1, o2): return self._blk("operator_gt", {"OPERAND1": o1, "OPERAND2": o2}, {})
    def not_(self, o1): return self._blk("operator_not", {"OPERAND": o1}, {})
    def len_(self, s): return self._blk("operator_length", {"STRING": s}, {})

    # Lists
    def delete_all(self, name, id): return self._blk("data_deletealloflist", {}, {"LIST": [name, id]})
    def add_to_list(self, item_val, l_name, l_id): return self._blk("data_addtolist", {"ITEM": item_val}, {"LIST": [l_name, l_id]})

    # Gemini Extension
    def gemini_setServer(self, url): return self._blk("geminiAI_setServer", {"URL": iS(url)}, {})
    def gemini_setModel(self, model): return self._blk("geminiAI_setModel", {"MODEL": iS(model)}, {})
    def gemini_ask(self, prompt_val): return self._blk("geminiAI_ask", {"PROMPT": prompt_val}, {})
    def gemini_getResponse(self): return self._blk("geminiAI_getResponse", {}, {})
    def gemini_isThinking(self): return self._blk("geminiAI_isThinking", {}, {})
    def gemini_fetchHistory(self): return self._blk("geminiAI_fetchHistory", {}, {})
    def gemini_historySize(self): return self._blk("geminiAI_historySize", {}, {})
    def gemini_getHistoryPrompt(self, idx): return self._blk("geminiAI_getHistoryPrompt", {"INDEX": idx}, {})
    def gemini_getHistoryResponse(self, idx): return self._blk("geminiAI_getHistoryResponse", {"INDEX": idx}, {})

    def resolve_parents(self):
        # Automatically connect "parent" fields to make the block tree valid!
        for uid, blk in self.blocks.items():
            if blk.get("next"):
                self.blocks[blk["next"]]["parent"] = uid
            for iname, ival in blk.get("inputs", {}).items():
                if isinstance(ival, list) and len(ival) >= 2 and ival[0] in [2, 3]:
                    target = ival[1]
                    if isinstance(target, str) and target in self.blocks:
                        self.blocks[target]["parent"] = uid

# ---------------------------------------------------------
# Build Function
# ---------------------------------------------------------

def build():
    bd_md5, bd_b = md5_svg(SVG_BACKDROP)
    sp_md5, sp_b = md5_svg(SVG_SPARKLE)
    L_CHAT = "chat_history_list"
    
    b = B()

    # --- Script: Gemini Logic ---
    start = b.flag()
    init1 = b.delete_all("ChatHistory", L_CHAT)
    init2 = b.gemini_setServer("https://web-production-82403.up.railway.app")
    init3 = b.gemini_setModel("gemini-2.0-flash")
    init4 = b.goto(-195, 155)
    
    # History Loading Logic
    h_fetch = b.gemini_fetchHistory()
    h_wait  = b.wait(1.5) # Give it a moment to fetch
    h_set_i = b.set_var("i", "var_i", iN(1))
    
    # Loop body
    h_p = b.join_(iS("You: "), iR(b.gemini_getHistoryPrompt(iR(b.get_var("i", "var_i")))))
    h_add_p = b.add_to_list(iR(h_p), "ChatHistory", L_CHAT)
    
    h_r = b.join_(iS("Gemini: "), iR(b.gemini_getHistoryResponse(iR(b.get_var("i", "var_i")))))
    h_add_r = b.add_to_list(iR(h_r), "ChatHistory", L_CHAT)
    
    h_inc = b.change_var("i", "var_i", iN(1))
    
    h_loop_body = b._chain([h_add_p, h_add_r, h_inc])
    h_loop = b.repeat(iR(b.gemini_historySize()), h_loop_body)
    
    init_done = b.add_to_list(iS("Gemini: おかえりなさい！何かお手伝いしましょうか？"), "ChatHistory", L_CHAT)

    loop_ask = b.ask_wait(iS(""))
    
    user_str = b.join_(iS("You: "), iR(b.answer()))
    add_user = b.add_to_list(iR(user_str), "ChatHistory", L_CHAT)
    
    ext_ask = b.gemini_ask(iR(b.answer()))
    
    is_think = b.gemini_isThinking()
    not_think = b.not_(iB(is_think))
    spin = b.turn_right(10)
    wait_anim = b.repeat_until(not_think, spin)
    
    reset_dir = b.point_dir(90)
    
    gem_str = b.join_(iS("Gemini: "), iR(b.gemini_getResponse()))
    add_gem = b.add_to_list(iR(gem_str), "ChatHistory", L_CHAT)
    
    # Assembly
    main_loop = b._chain([loop_ask, add_user, ext_ask, wait_anim, reset_dir, add_gem])
    forever = b.forever(main_loop)
    
    b._chain([start, init1, init2, init3, h_fetch, h_wait, h_set_i, h_loop, init_done, init4, forever], top=True)
    
    # IMPORTANT: Resolve parents automatically for valid Scratch JSON formatting!
    b.resolve_parents()

    project = {
        "targets": [
            {
                "isStage": True,
                "name": "Stage",
                "variables": {
                    "var_i": ["i", 0]
                },
                "lists": {
                    L_CHAT: ["ChatHistory", []]
                },
                "broadcasts": {},
                "blocks": {},
                "comments": {},
                "currentCostume": 0,
                "costumes": [
                    {
                        "assetId": bd_md5.split(".")[0],
                        "name": "backdrop1",
                        "md5ext": bd_md5,
                        "dataFormat": "svg",
                        "rotationCenterX": 240,
                        "rotationCenterY": 180
                    }
                ],
                "sounds": [],
                "volume": 100,
                "layerOrder": 0,
                "tempo": 60,
                "videoTransparency": 50,
                "videoState": "on"
            },
            {
                "isStage": False,
                "name": "Gemini",
                "variables": {},
                "lists": {},
                "broadcasts": {},
                "blocks": b.blocks,
                "comments": {},
                "currentCostume": 0,
                "costumes": [
                    {
                        "assetId": sp_md5.split(".")[0],
                        "name": "sparkle",
                        "md5ext": sp_md5,
                        "dataFormat": "svg",
                        "rotationCenterX": 50,
                        "rotationCenterY": 50
                    }
                ],
                "sounds": [],
                "volume": 100,
                "layerOrder": 1,
                "visible": True,
                "x": -195,
                "y": 155,
                "size": 35,
                "direction": 90,
                "draggable": False,
                "rotationStyle": "all around"
            }
        ],
        "monitors": [
            {
                "id": L_CHAT,
                "mode": "list",
                "opcode": "data_listcontents",
                "params": {"LIST": "ChatHistory"},
                "spriteName": None,
                "value": [],
                "width": 440,
                "height": 180,
                "x": 20,
                "y": 110,
                "visible": True
            }
        ],
        "extensions": ["geminiAI"],
        "meta": {
            "semver": "3.0.0",
            "vm": "0.2.0"
        }
    }

    out = "gemini_scratch.sb3"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("project.json", json.dumps(project, ensure_ascii=False))
        z.writestr(bd_md5, bd_b)
        z.writestr(sp_md5, sp_b)
        
    print(f"[OK] Generated {out} (TurboWarp Web UI Edition)")

if __name__ == "__main__":
    build()
