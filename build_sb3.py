import json
import zipfile
import hashlib
import io
import os

# ---------------------------------------------------------
# Asset Generators (SVGs for beautiful UI)
# ---------------------------------------------------------

SVG_BACKDROP = """<svg width="480" height="360" xmlns="http://www.w3.org/2000/svg">
    <rect width="480" height="360" fill="#131314"/>
    <rect width="480" height="50" fill="#1E1F20"/>
    <text x="240" y="33" font-family="sans-serif" font-size="22" fill="#E3E3E3" text-anchor="middle" font-weight="bold">✨ TurboWarp x Gemini</text>
    <rect x="20" y="60" width="440" height="235" rx="8" fill="#1E1F20"/>
    <rect x="20" y="305" width="440" height="45" rx="22.5" fill="#1E1F20" stroke="#333537" stroke-width="2"/>
    <text x="240" y="333" font-family="sans-serif" font-size="14" fill="#A8C7FA" text-anchor="middle">Start typing and press enter...</text>
</svg>"""

SVG_SPARKLE = """<svg width="60" height="60" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <path d="M50 0 C50 30, 70 50, 100 50 C70 50, 50 70, 50 100 C50 70, 30 50, 0 50 C30 50, 50 30, 50 0 Z" fill="#A8C7FA"/>
</svg>"""

SVG_EMPTY = """<svg version="1.1" width="2" height="2" viewBox="-1 -1 2 2" xmlns="http://www.w3.org/2000/svg"></svg>"""

def md5_svg(svg_data):
    b = svg_data.encode("utf-8")
    return hashlib.md5(b).hexdigest() + ".svg", b

# ---------------------------------------------------------
# Block Builder Utility
# ---------------------------------------------------------

def iN(num): return [4, [20, str(num)]]                 # Number
def iP(num): return [4, [20, str(num)], [20, str(num)]] # Number (positive)
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
    init4 = b.add_to_list(iS("System: こんにちは！下のバーから質問を入力してね。"), "ChatHistory", L_CHAT)
    init5 = b.goto(15, 178)

    loop_ask = b.ask_wait(iS(""))
    answer_len = b.len_(iR(b.answer()))
    gt_0 = b.gt_(iR(answer_len), iN(0))
    
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
    
    b._chain([start, init1, init2, init3, init4, init5, forever], top=True)
    
    # IMPORTANT: Resolve parents automatically for valid Scratch JSON formatting!
    b.resolve_parents()

    project = {
        "targets": [
            {
                "isStage": True,
                "name": "Stage",
                "variables": {},
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
                "x": 15,
                "y": 178,
                "size": 50,
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
                "height": 235,
                "x": 20,
                "y": 60,
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
