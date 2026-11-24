"""Facts for the Korean guide pages (tools/kr_guide.py), read from this repo's source (mod branch) and the ROMs.

- Constants (event flags, landmarks, species, map groups) are evaluated by rgbasm itself (includes.asm + PRINTLN)
  in the pokegold-build Docker image, so they are exactly the numbers the game uses. Event flag numbers and map
  ids are the same in the Korean ROM (tools/kr_patch.py patch_legends relies on the same fact).
- Korean RAM addresses: every English instruction that loads/stores/points at the symbol is decoded forward a few
  instructions, 16-bit operands masked, and searched in the Korean ROM; a unique match gives the Korean operand.
  The address with the most votes wins (checked against the ones already known: wMapGroup, wTimeOfDay, wPartyCount).
- Map -> landmark (place name) and fishing group: data/maps/maps.asm; landmark names: the Korean ROM's own
  Landmarks table (found from the English table's x/y bytes).
- 도감 안내 sources, per species: wild grass/water (the Korean tables), fishing (data/wild/fish.asm by the map's
  fishing group, maps that have a water table), headbutt trees (treemon_maps/treemons), gifts and static
  encounters in map scripts (givepoke/giveegg/loadwildmon), in-game trades (trade NPC_TRADE_*), roaming,
  rock smash, evolution (English ROM EvosAttacks) and breeding. The earliest place (lowest landmark id, the
  order of the game's region map) is shown.
"""
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

L2 = {0x06, 0x0E, 0x16, 0x1E, 0x26, 0x2E, 0x36, 0x3E, 0x18, 0x20, 0x28, 0x30, 0x38, 0xC6, 0xCE, 0xD6, 0xDE,
      0xE6, 0xEE, 0xF6, 0xFE, 0xE0, 0xF0, 0xE8, 0xF8, 0xCB, 0x10}
L3 = {0x01, 0x11, 0x21, 0x31, 0x08, 0xC2, 0xC3, 0xCA, 0xD2, 0xDA, 0xC4, 0xCC, 0xCD, 0xD4, 0xDC, 0xEA, 0xFA}
REF_OPS = {0xFA, 0xEA, 0x21, 0x11, 0x01}
NOT_A_SOURCE = {"Route29"}          # the catching tutorial (Rattata) is the old man's battle, not the player's
ROAMERS = ("RAIKOU", "ENTEI", "SUICUNE")


def en_symbols(en_sym):
    out = {}
    for line in open(en_sym, encoding="utf-8"):
        p = line.split()
        if len(p) == 2 and not line.startswith(";") and ":" in p[0]:
            b, a = (int(x, 16) for x in p[0].split(":"))
            out[p[1]] = (b, a)
    return out


def find_ram(en, kr, addr, n_ins=6):
    """Korean address of the English RAM address `addr` (see the docstring)."""
    votes = Counter()
    for m in re.finditer(re.escape(bytes([addr & 0xFF, addr >> 8])), en):
        at = m.start() - 1
        if at < 0 or en[at] not in REF_OPS:
            continue
        pat, k = [], at
        for _ in range(n_ins):
            op = en[k]
            n = 3 if op in L3 else 2 if op in L2 else 1
            if n == 3:
                pat += [re.escape(bytes([op])), b"(..)" if k == at else b".."]
            else:
                pat += [re.escape(bytes([b])) for b in en[k:k + n]]
            k += n
        hits = list(re.finditer(b"".join(pat), kr, re.S))
        if len(hits) == 1:
            g = hits[0].group(1)
            votes[g[0] | g[1] << 8] += 1
    top = votes.most_common(2)
    assert top and (len(top) == 1 or top[0][1] >= 2 * top[1][1]), f"RAM {addr:04X}: {top}"
    return top[0][0]


def consts(repo, names):
    names = sorted(set(names))
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "c.asm").write_text('INCLUDE "includes.asm"\n' + "".join(f'PRINTLN "{n} {{d:{n}}}"\n' for n in names),
                                 encoding="utf-8")
        out = subprocess.run(["docker", "run", "--rm", "-v", f"{repo}:/src:ro", "-v", f"{t}:/w", "-w", "/src",
                              "pokegold-build", "rgbasm", "-o", "/dev/null", "/w/c.asm"],
                             capture_output=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr[-3000:]
    return {k: int(v) for k, v in (l.split() for l in out.stdout.splitlines() if l.strip())}


def species_names(repo):
    text = (repo / "constants/pokemon_constants.asm").read_text(encoding="utf-8")
    names = re.findall(r"^\s*const (\w+)\s*; ([0-9a-f]{2})", text, re.M)
    out = [n for n, _ in names][:251]
    assert out[0] == "BULBASAUR" and out[-1] == "CELEBI", (out[0], out[-1])
    return out


def map_table(repo):
    """{MapName: (group, number, LANDMARK_*, FISHGROUP_*)}"""
    text = (repo / "data/maps/maps.asm").read_text(encoding="utf-8")
    order = re.findall(r"^\s*dw (MapGroup_\w+)", text, re.M)
    groups, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"(MapGroup_\w+):", line)
        if m:
            cur = groups.setdefault(m.group(1), [])
            continue
        m = re.match(r"\s+map (.+)", line)
        if m and cur is not None:
            a = [x.strip() for x in m.group(1).split(";")[0].split(",")]
            assert len(a) == 8, line
            cur.append((a[0], a[3], a[7]))
    out = {}
    for g, name in enumerate(order, 1):
        for n, (mname, lm, fish) in enumerate(groups[name], 1):
            out[mname] = (g, n, lm, fish)
    return out


def landmark_names(en, sym, kr, count):
    """raw Korean name bytes (without the end byte) of each landmark id"""
    b, a = sym["Landmarks"]
    en_lm = b * 0x4000 + a - 0x4000
    pat = b"".join(re.escape(en[en_lm + 4 * i:en_lm + 4 * i + 2]) + b".." for i in range(1, 16))
    hits = [m.start() - 4 for m in re.finditer(pat, kr, re.S)]
    assert len(hits) == 1, f"Landmarks: {len(hits)} matches"
    kb = hits[0] // 0x4000
    out = []
    for i in range(count):
        p = kr[hits[0] + 4 * i + 2] | kr[hits[0] + 4 * i + 3] << 8
        o = kb * 0x4000 + p - 0x4000
        out.append(bytes(kr[o:kr.index(0x50, o)]))
    return out


def script_label(lines, i):
    while i >= 0:
        m = re.match(r"(\w+):", lines[i])
        if m and not lines[i].startswith("."):
            return m.group(1)
        i -= 1


def map_scripts(repo):
    """[(MapName, command, SPECIES, script label)] for givepoke / giveegg / loadwildmon"""
    out = []
    for f in sorted((repo / "maps").glob("*.asm")):
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            m = re.match(r"\s+(givepoke|giveegg|loadwildmon) (\w+)", line)
            if m:
                out.append((f.stem, m.group(1), m.group(2), script_label(lines, i)))
    return out


def legends(repo, wanted):
    """[(SPECIES, MapName, EVENT_*)] in `wanted` order — the flag that is set once the battle happened:
    a `setevent` in the script before the battle (칠색조·루기아: EVENT_FOUGHT_*, their object flags are set at
    game start to hide them), else the flag of the object whose script starts the battle (`disappear` sets it)"""
    init = set(re.findall(r"setevent (EVENT_\w+)", (repo / "engine/events/std_scripts.asm").read_text(encoding="utf-8")))
    out = []
    for mname, cmd, sp, label in map_scripts(repo):
        if cmd == "loadwildmon" and sp in wanted:
            text = (repo / "maps" / f"{mname}.asm").read_text(encoding="utf-8")
            body = text[text.index(f"\n{label}:"):]
            body = body[:body.index(f"loadwildmon {sp}")]
            fought = re.findall(r"setevent (EVENT_\w+)", body)
            m = re.search(rf"object_event .*, {label}, (\w+)\s*$", text, re.M)
            assert m, f"{mname}: no object for {label}"
            flag = fought[-1] if fought else m.group(1)
            assert flag not in init, f"{sp}: {flag} is set at game start"
            if (sp, mname, flag) not in out:
                out.append((sp, mname, flag))
    assert sorted(x[0] for x in out) == sorted(wanted), out
    return sorted(out, key=lambda x: wanted.index(x[0]))


def fish_species(repo):
    """{fishgroup index (1-based): set of SPECIES}"""
    text = (repo / "data/wild/fish.asm").read_text(encoding="utf-8")
    table = re.findall(r"^\s*fishgroup [^,]+, (\.\w+),\s*(\.\w+),\s*(\.\w+)", text, re.M)
    blocks, cur = {}, None
    time_groups = []
    in_time = False
    for line in text.splitlines():
        m = re.match(r"(\.\w+):", line)
        if m:
            cur = blocks.setdefault(m.group(1), set())
            continue
        if line.startswith("TimeFishGroups:"):
            in_time, cur = True, None
            continue
        if in_time:
            m = re.match(r"\s*db (\w+),\s*\d+,\s*(\w+),\s*\d+", line)
            if m:
                time_groups.append({m.group(1), m.group(2)})
            continue
        m = re.match(r"\s*db [^,]+,\s*(\w+),\s*\d+", line)
        if m and cur is not None:
            cur.add(m.group(1))
        m = re.match(r"\s*db [^,]+,\s*time_group (\d+)", line)
        if m and cur is not None:
            cur.add(("time", int(m.group(1))))
    out = {}
    for k, labels in enumerate(table, 1):
        s = set()
        for lb in labels:
            for x in blocks.get(lb, ()):
                s |= time_groups[x[1]] if isinstance(x, tuple) else {x}
        out[k] = s
    return out


def tree_species(repo):
    """[(MAP_CONST, set of SPECIES)] for headbutt trees"""
    maps = re.findall(r"^\s*treemon_map (\w+),\s*(\w+)", (repo / "data/wild/treemon_maps.asm").read_text(encoding="utf-8"), re.M)
    text = (repo / "data/wild/treemons.asm").read_text(encoding="utf-8")
    sets = re.findall(r"^\s*dw (TreeMonSet_\w+)", text, re.M)
    blocks, cur, last_label = {}, [], False
    for line in text.splitlines():
        m = re.match(r"(TreeMonSet_\w+):", line)
        if m:
            cur = cur if last_label else []
            cur.append(m.group(1))
            blocks[m.group(1)] = blocks.get(m.group(1), set())
            last_label = True
            continue
        m = re.match(r"\s*db \d+,\s*(\w+),\s*\d+", line)
        if m:
            last_label = False
            for lb in cur:
                blocks[lb].add(m.group(1))
    set_names = ["TREEMON_SET_" + s[len("TreeMonSet_"):].upper() for s in sets]
    by_set = {sn: blocks[s] for sn, s in zip(set_names, sets)}
    return [(mc, by_set[st]) for mc, st in maps], by_set


def contest_species(repo):
    text = (repo / "data/wild/bug_contest_mons.asm").read_text(encoding="utf-8")
    return re.findall(r"^\s*db\s+\d+,\s*(\w+),", text, re.M)


def trades(repo):
    """[(MapName, received SPECIES)]"""
    text = (repo / "data/events/npc_trades.asm").read_text(encoding="utf-8")
    got = [m.group(1) for m in re.finditer(r"^\s*npctrade \w+,\s*\w+,\s*(\w+),", text, re.M)]
    order = re.findall(r"^\s*const (NPC_TRADE_\w+)", (repo / "constants/npc_trade_constants.asm").read_text(encoding="utf-8"), re.M)
    out = []
    for f in sorted((repo / "maps").glob("*.asm")):
        for m in re.finditer(r"^\s+trade (NPC_TRADE_\w+)", f.read_text(encoding="utf-8"), re.M):
            out.append((f.stem, got[order.index(m.group(1))]))
    return out


def evolutions(en, sym):
    """{species id: [evolved species id]}"""
    b, a = sym["EvosAttacksPointers"]
    t = b * 0x4000 + a - 0x4000
    out = {}
    for s in range(1, 252):
        p = en[t + 2 * (s - 1)] | en[t + 2 * (s - 1) + 1] << 8
        o = b * 0x4000 + p - 0x4000
        evos = []
        while en[o]:
            kind = en[o]
            n = 4 if kind == 5 else 3      # EVOLVE_STAT: level, ATK_*, species
            evos.append(en[o + n - 1])
            o += n
        out[s] = evos
    return out


# ---- 마을 소개(사용자 지시 2026-11-24 — 3세대 판들의 '마을 소개' 탭과 같게, REA_repo tools/firered_guide/town_npcs.py 규칙) ----
# 오브젝트(object_event … 스크립트 이름표)의 스크립트 블록(그 이름표부터 다음 맨 앞 이름표까지 + 같은 파일 안 sjump·scall로 닿는 블록)에서:
# pokemart 상점 · 체육관 맵 loadtrainer 관장 · 사천왕 방·챔피언 방 · givepoke·special GiveShuckle 선물 · giveegg 알 · giveitem·verbosegiveitem 도구
# · trade 교환(npc_trades.asm) · special NameRater 이름 평가 · DayCareMan 키우미집 · MoveDeletion 기술 삭제 · SelectApricornForKurt 볼 만들기
# · Older/YoungerHaircutBrother 이발(친밀도). 같은 도구를 5곳 이상에서 주는 것은 공통 직원이라 뺀다
TOWN_OUTDOOR = re.compile(r"Route\d+|\w+City|\w+Town|CinnabarIsland|IndigoPlateau|LakeOfRage|SilverCaveOutside")
TOWN_BUILD = [("Pokecenter", "포켓몬센터"), ("PokeCenter", "포켓몬센터"), ("Mart", "프렌들리숍"), ("Gym", "체육관"),
              ("DeptStore", "백화점"), ("House", "집")]
TOWN_DIRS = [["북서쪽", "북쪽", "북동쪽"], ["서쪽", "가운데", "동쪽"], ["남서쪽", "남쪽", "남동쪽"]]
TOWN_ELITE = {"WillsRoom": "elite", "KogasRoom": "elite", "BrunosRoom": "elite", "KarensRoom": "elite", "LancesRoom": "champion"}
TOWN_SPECIAL = {"NameRater": "namerater", "DayCareMan": "daycare", "MoveDeletion": "deleter", "SelectApricornForKurt": "kurt",
                "OlderHaircutBrother": "haircut", "YoungerHaircutBrother": "haircut"}


def town_npcs(repo):
    """[{map, kind, a, b, where}] — a, b: SPECIES·ITEM 이름(교환은 a = 주는 종·b = 받는 종), 관장 등은 a = 트레이너 클래스"""
    norm = lambda s: s.replace("_", "").lower()
    dims = {norm(c): (int(w) * 2, int(h) * 2) for c, w, h in
            re.findall(r"map_const\s+(\w+),\s*(\d+),\s*(\d+)", (repo / "constants/map_constants.asm").read_text(encoding="utf-8"))}
    trade_rows = re.findall(r"^\s*npctrade \w+,\s*(\w+),\s*(\w+),", (repo / "data/events/npc_trades.asm").read_text(encoding="utf-8"), re.M)
    trade_order = re.findall(r"^\s*const (NPC_TRADE_\w+)", (repo / "constants/npc_trade_constants.asm").read_text(encoding="utf-8"), re.M)
    texts, objs, warps = {}, {}, {}
    for f in sorted((repo / "maps").glob("*.asm")):
        t = f.read_text(encoding="utf-8")
        texts[f.stem] = t
        objs[f.stem] = re.findall(r"^\s*object_event\s+(\d+),\s*(\d+),.*?,\s*(\w+),\s*[-\w]+\s*$", t, re.M)
        warps[f.stem] = re.findall(r"^\s*warp_event\s+(\d+),\s*(\d+),\s*(\w+),", t, re.M)
    by_norm = {norm(n): n for n in texts}
    outdoor = {n for n in texts if TOWN_OUTDOOR.fullmatch(n)}
    entry = {}
    for n in sorted(outdoor):
        for x, y, dest in warps[n]:
            d = by_norm.get(norm(dest))
            if d and d not in outdoor and d not in entry:
                entry[d] = (n, int(x), int(y))
    changed = True
    while changed:
        changed = False
        for n in sorted(texts):
            if n in entry:
                for x, y, dest in warps[n]:
                    d = by_norm.get(norm(dest))
                    if d and d not in outdoor and d not in entry:
                        entry[d] = entry[n]
                        changed = True

    def blocks(t):
        marks = [(m.start(), m.end(), m.group(1)) for m in re.finditer(r"^(\w+):{1,2}", t, re.M)]
        return {name: t[e:marks[i + 1][0] if i + 1 < len(marks) else len(t)] for i, (s, e, name) in enumerate(marks)}
    rows = []
    for n, ol in objs.items():
        bl = blocks(texts[n])
        for x, y, script in ol:
            if script not in bl:
                continue
            body, seen, todo = "", set(), [script]
            while todo:
                lb = todo.pop()
                if lb in seen or lb not in bl:
                    continue
                seen.add(lb)
                body += bl[lb]
                todo += re.findall(r"^\s*(?:sjump|scall|sjumpfwd)\s+(\w+)", bl[lb], re.M)
            found = []
            if re.search(r"^\s*pokemart\s", body, re.M):
                found.append(("mart", "", ""))
            for cls in re.findall(r"^\s*loadtrainer (\w+),", body, re.M):
                if n.endswith("Gym"):
                    found.append(("leader", cls, ""))
                elif n in TOWN_ELITE:
                    found.append((TOWN_ELITE[n], cls, ""))
            for sp, lv in re.findall(r"^\s*givepoke (\w+),\s*(\d+)", body, re.M):
                found.append(("gift", sp, lv))
            if re.search(r"special GiveShuckle", body):
                found.append(("gift", "SHUCKLE", "15"))
            for sp in re.findall(r"^\s*giveegg (\w+)", body, re.M):
                found.append(("egg", sp, ""))
            for it in re.findall(r"^\s*(?:verbose)?giveitem (\w+)", body, re.M):
                found.append(("item", it, ""))
            for tr in re.findall(r"^\s*trade (NPC_TRADE_\w+)", body, re.M):
                want, give = trade_rows[trade_order.index(tr)]
                found.append(("trade", want, give))
            for sp, kind in TOWN_SPECIAL.items():
                if re.search(rf"special {sp}\b", body):
                    found.append((kind, "", ""))
            for kind, a, b in dict.fromkeys(found):
                rows.append({"map": n, "kind": kind, "a": a, "b": b, "obj": (int(x), int(y))})
    common = Counter(r["a"] for r in rows if r["kind"] == "item")
    rows = [r for r in rows if not (r["kind"] == "item" and common[r["a"]] >= 5)]
    bk = lambda m: next((k for key, k in TOWN_BUILD if key in m), "건물")
    for r in rows:
        n = r["map"]
        if n in outdoor:
            w, h = dims.get(norm(n), (20, 18))
            x, y = r["obj"]
            r["where"] = TOWN_DIRS[min(2, y * 3 // max(h, 1))][min(2, x * 3 // max(w, 1))]
            continue
        if n not in entry:
            r["where"] = ""
            continue
        town, ex, ey = entry[n]
        w, h = dims.get(norm(town), (20, 18))
        kind = bk(n)
        others = {entry[d][1:] for d in entry if entry[d][0] == town and d != n and bk(d) == kind} - {(ex, ey)}
        where = kind if not others and kind != "건물" else f"{TOWN_DIRS[min(2, ey * 3 // max(h, 1))][min(2, ex * 3 // max(w, 1))]} {kind}"
        fl = re.search(r"(B?)(\d)F$", n)
        if fl:
            where += f" 지하 {fl.group(2)}층" if fl.group(1) else f" {fl.group(2)}층"
        r["where"] = where
    return rows
