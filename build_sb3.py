"""
Scratch x Gemini AI -- sb3 builder (Unicode edition)
"""
import json, hashlib, zipfile

def md5(data): return hashlib.md5(data).hexdigest()

class B:
    def __init__(self): self.d = {}; self._n = 0
    def nid(self): self._n += 1; return f"b{self._n}"

    def _blk(self, opcode, inputs=None, fields=None, top=False, x=0, y=0):
        bid = self.nid()
        self.d[bid] = {"opcode": opcode, "next": None, "parent": None,
                       "inputs": inputs or {}, "fields": fields or {},
                       "shadow": False, "topLevel": top, "x": x, "y": y}
        return bid

    def var(self, n, vid): return self._blk("data_variable", fields={"VARIABLE": [n, vid]})
    def answer(self): return self._blk("sensing_answer")

    def join_(self, a, b_): return self._blk("operator_join", {"STRING1": a, "STRING2": b_})
    def eq_(self, a, b_):   return self._blk("operator_equals", {"OPERAND1": a, "OPERAND2": b_})
    def lt_(self, a, b_):   return self._blk("operator_lt",     {"OPERAND1": a, "OPERAND2": b_})
    def not_(self, a):      return self._blk("operator_not",    {"OPERAND": a})
    def add_(self, a, b_):  return self._blk("operator_add",    {"NUM1": a, "NUM2": b_})
    def sub_(self, a, b_):  return self._blk("operator_subtract", {"NUM1": a, "NUM2": b_})
    def div_(self, a, b_):  return self._blk("operator_divide", {"NUM1": a, "NUM2": b_})
    def floor_(self, a):    return self._blk("operator_mathop", {"NUM": a}, {"OPERATOR": ["floor", None]})
    def letter_of(self, idx, s): return self._blk("operator_letter_of", {"LETTER": idx, "STRING": s})
    def length_(self, s):        return self._blk("operator_length",   {"STRING": s})

    def setvr(self, n, vid, v): return self._blk("data_setvariableto",   {"VALUE": v},   {"VARIABLE": [n, vid]})
    def chgvr(self, n, vid, v): return self._blk("data_changevariableby", {"VALUE": v},  {"VARIABLE": [n, vid]})
    def say(self, m):           return self._blk("looks_say",            {"MESSAGE": m})
    def say_for(self, m, s):    return self._blk("looks_sayforsecs",     {"MESSAGE": m, "SECS": s})
    def ask(self, q):           return self._blk("sensing_askandwait",   {"QUESTION": q})
    def wait_until(self, c):    return self._blk("control_wait_until",   {"CONDITION": c})
    def if_(self, c, s):        return self._blk("control_if",           {"CONDITION": c, "SUBSTACK": [2, s]})
    def ifelse(self, c, s1, s2):return self._blk("control_if_else",     {"CONDITION": c, "SUBSTACK": [2, s1], "SUBSTACK2": [2, s2]})
    def forever(self, s):       return self._blk("control_forever",      {"SUBSTACK": [2, s]})
    def repeat(self, t, s):     return self._blk("control_repeat",       {"TIMES": t, "SUBSTACK": [2, s]})
    def flag_hat(self, x=50, y=50): return self._blk("event_whenflagclicked", top=True, x=x, y=y)

    def chain(self, *ids):
        ids = [i for i in ids if i]
        for i in range(len(ids)-1):
            self.d[ids[i]]["next"]         = ids[i+1]
            self.d[ids[i+1]]["parent"]     = ids[i]
        return ids[0] if ids else None

    def fix(self):
        for bid, blk in self.d.items():
            for _, v in blk["inputs"].items():
                if isinstance(v, list) and len(v) >= 2 and isinstance(v[1], str) and v[1] in self.d:
                    if self.d[v[1]]["parent"] is None: self.d[v[1]]["parent"] = bid
                if isinstance(v, list) and len(v) >= 3 and isinstance(v[2], str) and v[2] in self.d:
                    if self.d[v[2]]["parent"] is None: self.d[v[2]]["parent"] = bid

def iN(v): return [1, [4, str(v)]]
def iS(v): return [1, [10, str(v)]]
def iB(bid): return [2, bid]
def iR(bid): return [3, bid, [4, "0"]]
def iRS(bid): return [3, bid, [10, ""]]

def build():
    b = B()
    V = {
        "p1": "cp1", "p2": "cp2", 
        "r1": "cr1", "r2": "cr2", "r3": "cr3", "r4": "cr4", "r5": "cr5", "r6": "cr6", "r7": "cr7",
        "status": "cst",
        "enc_i": "vei", "code_val": "vcv", "code_z": "vcz",
        "resp_str": "vrs", "resp_full": "vrf", "dec_i": "vdi",
        "unicode": "lst_uni"
    }

    # -- Encoding logic --
    # Init prompt vars
    s_p1    = b.setvr("p1", V["p1"], iS("1"))
    s_p2    = b.setvr("p2", V["p2"], iS("1"))
    s_enci  = b.setvr("enc_i", V["enc_i"], iN(1))
    
    # Inside repeat(length of answer)
    c_letter = b.letter_of(iR(b.var("enc_i", V["enc_i"])), iRS(b.answer()))
    c_idx   = b._blk("data_itemnumoflist", {"ITEM": iRS(c_letter)}, {"LIST": ["unicode", V["unicode"]]})
    s_code  = b.setvr("code_val", V["code_val"], iR(c_idx))
    
    eq0     = b.eq_(iR(b.var("code_val", V["code_val"])), iN(0))
    s_63    = b.setvr("code_val", V["code_val"], iN(63))
    if_0    = b.if_(iB(eq0), s_63)
    
    add100  = b.add_(iR(b.var("code_val", V["code_val"])), iN(100000))
    s_cz    = b.setvr("code_z", V["code_z"], iRS(add100))
    
    def l(idx): return b.letter_of(iN(idx), iRS(b.var("code_z", V["code_z"])))
    j1      = b.join_(iRS(l(5)), iRS(l(6)))
    j2      = b.join_(iRS(l(4)), iRS(j1))
    j3      = b.join_(iRS(l(3)), iRS(j2))
    j5      = b.join_(iRS(l(2)), iRS(j3))
    
    len_p1  = b.length_(iRS(b.var("p1", V["p1"])))
    lt250   = b.lt_(iR(len_p1), iN(250))
    
    j_p1    = b.join_(iRS(b.var("p1", V["p1"])), iRS(j5))
    j_p2    = b.join_(iRS(b.var("p2", V["p2"])), iRS(j5))
    s_app1  = b.setvr("p1", V["p1"], iRS(j_p1))
    s_app2  = b.setvr("p2", V["p2"], iRS(j_p2))
    ifelse_app = b.ifelse(iB(lt250), s_app1, s_app2)
    
    chg_ei  = b.chgvr("enc_i", V["enc_i"], iN(1))
    
    b.chain(s_code, if_0, s_cz, ifelse_app, chg_ei)
    rep_enc = b.repeat(iR(b.length_(iRS(b.answer()))), s_code)
    b.chain(s_p1, s_p2, s_enci, rep_enc)
    encode_chain = s_p1
    
    # -- Decoding logic generator --
    def make_decode(cloud_var_name, cloud_var_id):
        v_resp = b.var(cloud_var_name, cloud_var_id)
        eq0 = b.eq_(iR(v_resp), iN(0))
        not0 = b.not_(iB(eq0))
        
        s_rstr = b.setvr("resp_str", V["resp_str"], iR(v_resp))
        s_deci = b.setvr("dec_i", V["dec_i"], iN(2))
        
        sub1 = b.sub_(iR(b.length_(iRS(b.var("resp_str", V["resp_str"])))), iN(1))
        times = b.floor_(iR(b.div_(iR(sub1), iN(5))))
        
        def r_l(idx): return b.letter_of(iR(b.add_(iR(b.var("dec_i", V["dec_i"])), iN(idx))), iRS(b.var("resp_str", V["resp_str"])))
        rj1 = b.join_(iRS(r_l(3)), iRS(r_l(4)))
        rj2 = b.join_(iRS(r_l(2)), iRS(rj1))
        rj3 = b.join_(iRS(r_l(1)), iRS(rj2))
        rcode = b.join_(iRS(r_l(0)), iRS(rj3))
        
        s_rcode = b.setvr("code_val", V["code_val"], iRS(rcode))
        
        char_blk = b._blk("data_itemoflist", {"INDEX": iR(b.var("code_val", V["code_val"]))}, {"LIST": ["unicode", V["unicode"]]})
        s_rfull = b.setvr("resp_full", V["resp_full"], iRS(b.join_(iRS(b.var("resp_full", V["resp_full"])), iRS(char_blk))))
        
        chg_di = b.chgvr("dec_i", V["dec_i"], iN(5))
        
        b.chain(s_rcode, s_rfull, chg_di)
        rep = b.repeat(iR(times), s_rcode)
        b.chain(s_rstr, s_deci, rep)
        
        return b.if_(iB(not0), s_rstr)

    dec_blocks = [make_decode(f"r{i}", V[f"r{i}"]) for i in range(1, 8)]

    # -- Main Loop --
    hat         = b.flag_hat(x=50, y=50)
    say1        = b.say_for(iS("Gemini AI (日本語対応) 起動！"), iN(2))
    
    ask_b       = b.ask(iS("Gemini AI: 日本語で何でも質問してね！"))
    s_status1   = b.setvr("status", V["status"], iN(1))
    say_think   = b.say(iS("考え中..."))
    
    wait3       = b.wait_until(iB(b.eq_(iR(b.var("status", V["status"])), iN(3))))
    s_rfclear   = b.setvr("resp_full", V["resp_full"], iS(""))
    say_recv    = b.say(iS("受信完了！デコード中..."))
    say_resp    = b.say_for(iRS(b.var("resp_full", V["resp_full"])), iN(30))
    s_status0   = b.setvr("status", V["status"], iN(0))
    
    # link decode blocks chain
    b.chain(*dec_blocks)
    
    # link entirely
    b.chain(ask_b, encode_chain, s_status1, say_think, wait3, s_rfclear, dec_blocks[0], say_recv, say_resp, s_status0)
    forever_b   = b.forever(ask_b)
    b.chain(hat, say1, forever_b)
    
    b.fix()

    # -- Generate Unicode Array (1 to 65535) --
    unicode_arr = []
    for i in range(1, 65536):
        if (i < 32 and i != 10) or (55296 <= i <= 57343) or i == 127:
            unicode_arr.append("?")
        else:
            try: unicode_arr.append(chr(i))
            except: unicode_arr.append("?")

    # -- Meta and JSON formulation --
    stage_vars = {
        V["p1"]: ["☁ p1", 0, True], V["p2"]: ["☁ p2", 0, True],
        V["r1"]: ["☁ r1", 0, True], V["r2"]: ["☁ r2", 0, True], V["r3"]: ["☁ r3", 0, True], V["r4"]: ["☁ r4", 0, True],
        V["r5"]: ["☁ r5", 0, True], V["r6"]: ["☁ r6", 0, True], V["r7"]: ["☁ r7", 0, True],
        V["status"]: ["☁ status", 0, True],
        V["enc_i"]: ["enc_i", 0], V["code_val"]: ["code_val", 0], V["code_z"]: ["code_z", ""],
        V["resp_str"]: ["resp_str", ""], V["resp_full"]: ["resp_full", ""], V["dec_i"]: ["dec_i", 0]
    }
    
    lists = {
        V["unicode"]: ["unicode", unicode_arr]
    }

    robot_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#4285f4"/><stop offset="100%" stop-color="#9b72cb"/>'
        '</linearGradient></defs>'
        '<line x1="60" y1="8" x2="60" y2="20" stroke="#aaa" stroke-width="3"/>'
        '<circle cx="60" cy="5" r="5" fill="#4285f4"/>'
        '<rect x="18" y="20" width="84" height="65" rx="14" fill="url(#g)"/>'
        '<circle cx="42" cy="50" r="10" fill="white"/><circle cx="78" cy="50" r="10" fill="white"/>'
        '<circle cx="44" cy="50" r="5" fill="#1a237e"/><circle cx="80" cy="50" r="5" fill="#1a237e"/>'
        '<path d="M38 72 Q60 82 82 72" stroke="white" stroke-width="3" fill="none" stroke-linecap="round"/>'
        '<rect x="28" y="90" width="64" height="25" rx="8" fill="url(#g)" opacity="0.7"/>'
        '</svg>'
    )
    backdrop_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360">'
        '<defs><radialGradient id="bg" cx="50%" cy="50%">'
        '<stop offset="0%" stop-color="#1a1a3e"/><stop offset="100%" stop-color="#0a0a1a"/>'
        '</radialGradient></defs>'
        '<rect width="480" height="360" fill="url(#bg)"/>'
        '<text x="240" y="335" text-anchor="middle" font-family="sans-serif"'
        ' font-size="13" fill="#7986cb">Scratch x Gemini AI (Unicode Edition)</text>'
        '</svg>'
    )
    b_md5 = md5(backdrop_svg.encode())
    r_md5 = md5(robot_svg.encode())

    project = {
        "targets": [
            {"isStage": True, "name": "Stage", "variables": stage_vars, "lists": lists,
             "blocks": {}, "costumes": [{"assetId": b_md5, "name": "backdrop1", "dataFormat": "svg", "md5ext": f"{b_md5}.svg"}],
             "sounds": []},
            {"isStage": False, "name": "Gemini", "variables": {}, "lists": {}, "blocks": b.d,
             "costumes": [{"assetId": r_md5, "name": "robot", "dataFormat": "svg", "md5ext": f"{r_md5}.svg"}],
             "sounds": []}
        ],
        "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": "python"}
    }

    out = "gemini_scratch.sb3"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.json", json.dumps(project))
        zf.writestr(f"{b_md5}.svg", backdrop_svg.encode())
        zf.writestr(f"{r_md5}.svg", robot_svg.encode())

    print(f"✅ {out} 生成完了 (65535 Unicode完全対応)")

if __name__ == "__main__":
    build()
