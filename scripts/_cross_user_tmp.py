import zipfile, json, sys, os
from pathlib import Path

# Other user's data
OTHER_ZIPS = {
    "103deg": r"C:\Users\JunHa\Downloads\20260524_232119_103deg.zip",
    "107deg": r"C:\Users\JunHa\Downloads\20260524_232256_107deg.zip",
    "112deg": r"C:\Users\JunHa\Downloads\20260524_232422_112deg.zip",
}

# My data
MY_DIRS = {
    "103deg": r"C:\Users\JunHa\Desktop\바로목\baromok\debug_logs\posture_experiment\20260521_173723_103deg",
    "107deg": r"C:\Users\JunHa\Desktop\바로목\baromok\debug_logs\posture_experiment\20260521_173837_107deg",
    "112deg": r"C:\Users\JunHa\Desktop\바로목\baromok\debug_logs\posture_experiment\20260521_174034_112deg",
}

def load_other(angle):
    z = zipfile.ZipFile(OTHER_ZIPS[angle])
    return json.loads(z.read("summary.json")), json.loads(z.read("metadata.json"))

def load_mine(angle):
    d = Path(MY_DIRS[angle])
    return json.loads((d / "summary.json").read_text(encoding="utf-8")), json.loads((d / "metadata.json").read_text(encoding="utf-8"))

def get_cond(summary, label):
    for c in summary:
        if c["label"] == label:
            return c
    return None

def get_metric(cond, key):
    if cond is None: return None
    m = (cond.get("metrics") or {}).get(key)
    return m

def pct(val, base):
    if val is None or base is None or base == 0: return None
    return (val - base) / abs(base) * 100

def fmt(x, n=2, suffix=""):
    return f"{x:>+{n+5}.{n}f}%" if x is not None else "    N/A"

ANGLES = ["103deg", "107deg", "112deg"]
KEY_METRICS = ["cheek_distance", "eye_distance", "cheek_eye_ratio", "vh_ratio", "face_center_y", "eye_line_tilt", "shoulder_width"]
POSTURES_COMMON = ["neutral", "forward_head_only", "recline"]
POSTURES_OTHER_EXTRA = ["forward_head_full", "chin_rest", "yaw_turn"]

# Load all
data = {}
for ang in ANGLES:
    other_s, other_m = load_other(ang)
    mine_s, mine_m = load_mine(ang)
    data[ang] = {"other": other_s, "mine": mine_s, "other_meta": other_m, "mine_meta": mine_m}

# ── Section 1: Detection rates ─────────────────────────────────────────────
print("=" * 110)
print(" [1] 검출률 비교")
print("=" * 110)
all_postures = POSTURES_COMMON + POSTURES_OTHER_EXTRA
print(f"\n  {'자세':<22}", end="")
for ang in ANGLES:
    print(f"  {'내 face/sh':>15}  {'상대 face/sh':>17}", end="")
print()
print("  " + "-" * 105)

for posture in all_postures:
    print(f"  {posture:<22}", end="")
    for ang in ANGLES:
        d = data[ang]
        m = get_cond(d["mine"], posture)
        o = get_cond(d["other"], posture)
        my_str = f"{m['face_detection_rate']*100:>5.1f}/{m['shoulder_detection_rate']*100:>5.1f}%" if m else "    N/A"
        ot_str = f"{o['face_detection_rate']*100:>5.1f}/{o['shoulder_detection_rate']*100:>5.1f}%" if o else "       N/A"
        print(f"  {my_str:>15}  {ot_str:>17}", end="")
    print()

# ── Section 2: Neutral baseline comparison (절대값 차이) ────────────────────
print("\n" + "=" * 110)
print(" [2] neutral baseline 절대값 — 두 사용자 비교")
print("=" * 110)

for ang in ANGLES:
    print(f"\n  ▸ {ang}")
    print(f"    {'지표':<22} {'내 값':>12} {'상대 값':>12} {'개인차 Δ%':>12}")
    print("    " + "-" * 60)
    d = data[ang]
    my_neutral = get_cond(d["mine"], "neutral")
    ot_neutral = get_cond(d["other"], "neutral")
    for key in KEY_METRICS:
        mv = get_metric(my_neutral, key)
        ov = get_metric(ot_neutral, key)
        if mv is None or ov is None:
            continue
        diff = pct(ov["mean"], mv["mean"])
        diff_str = f"{diff:>+10.1f}%" if diff is not None else "       N/A"
        print(f"    {key:<22} {mv['mean']:>12.5f} {ov['mean']:>12.5f}  {diff_str}")

# ── Section 3: Posture detection Δ% (각 사용자별, 자세 vs neutral) ──────────
print("\n" + "=" * 110)
print(" [3] 자세별 Δ% — neutral 대비 (두 사용자 비교)")
print("=" * 110)

for posture in POSTURES_COMMON:
    if posture == "neutral": continue
    print(f"\n  ▸ {posture} (vs neutral)")
    print(f"    {'지표':<22}", end="")
    for ang in ANGLES:
        print(f"  {ang+' 내':>11}  {ang+' 상대':>13}", end="")
    print()
    print("    " + "-" * 100)

    for key in KEY_METRICS:
        print(f"    {key:<22}", end="")
        for ang in ANGLES:
            d = data[ang]
            my_n = get_metric(get_cond(d["mine"], "neutral"), key)
            my_p = get_metric(get_cond(d["mine"], posture), key)
            ot_n = get_metric(get_cond(d["other"], "neutral"), key)
            ot_p = get_metric(get_cond(d["other"], posture), key)
            my_d = pct(my_p["mean"] if my_p else None, my_n["mean"] if my_n else None)
            ot_d = pct(ot_p["mean"] if ot_p else None, ot_n["mean"] if ot_n else None)
            my_s = f"{my_d:>+9.1f}%" if my_d is not None else "       N/A"
            ot_s = f"{ot_d:>+11.1f}%" if ot_d is not None else "         N/A"
            print(f"  {my_s:>11}  {ot_s:>13}", end="")
        print()

# ── Section 4: 상대방만 측정한 자세들 ──────────────────────────────────
print("\n" + "=" * 110)
print(" [4] 상대 데이터에서만 측정한 자세 (forward_head_full, chin_rest, yaw_turn) — vs neutral")
print("=" * 110)

for posture in POSTURES_OTHER_EXTRA:
    print(f"\n  ▸ {posture} (상대 데이터)")
    print(f"    {'지표':<22}", end="")
    for ang in ANGLES:
        print(f"  {ang:>10}", end="")
    print()
    print("    " + "-" * 60)

    for key in KEY_METRICS:
        print(f"    {key:<22}", end="")
        for ang in ANGLES:
            d = data[ang]
            ot_n = get_metric(get_cond(d["other"], "neutral"), key)
            ot_p = get_metric(get_cond(d["other"], posture), key)
            ot_d = pct(ot_p["mean"] if ot_p else None, ot_n["mean"] if ot_n else None)
            ot_s = f"{ot_d:>+9.1f}%" if ot_d is not None else "       N/A"
            print(f"  {ot_s:>10}", end="")
        print()

# ── Section 5: Threshold rule validation ─────────────────────────────────
print("\n" + "=" * 110)
print(" [5] 판정 규칙 검증 — 어제 도출한 규칙이 상대 데이터에서도 작동하는가?")
print("=" * 110)
print("""
  규칙:
    1. cheek_distance Δ% > +14%  → recline
    2. cheek_distance Δ% ≤ +14% AND vh_ratio Δ% > +7%  → forward_head_only
    3. cheek_eye_ratio |Δ%| < 2%  → stable
""")

print(f"  {'사용자':<8} {'각도':<8} {'자세':<24} {'cheek_dist Δ%':>14} {'vh_ratio Δ%':>13} {'판정':>20} {'정답':>20} {'결과':>6}")
print("  " + "-" * 110)

def classify(cheek_d, vh_d, cer_d):
    if cheek_d is None or vh_d is None:
        return "N/A"
    if cheek_d > 14:
        return "recline"
    if vh_d > 7:
        return "forward_head_only"
    if cer_d is not None and abs(cer_d) < 2:
        return "stable"
    return "기타"

total = 0
correct = 0
for user, src_key in [("내 데이터", "mine"), ("상대", "other")]:
    for ang in ANGLES:
        d = data[ang]
        src = d[src_key]
        neutral = get_cond(src, "neutral")
        for posture in ["forward_head_only", "recline"]:
            cond = get_cond(src, posture)
            if cond is None: continue
            cd_n = get_metric(neutral, "cheek_distance")
            cd_p = get_metric(cond, "cheek_distance")
            vh_n = get_metric(neutral, "vh_ratio")
            vh_p = get_metric(cond, "vh_ratio")
            cer_n = get_metric(neutral, "cheek_eye_ratio")
            cer_p = get_metric(cond, "cheek_eye_ratio")
            cd_d = pct(cd_p["mean"] if cd_p else None, cd_n["mean"] if cd_n else None)
            vh_d = pct(vh_p["mean"] if vh_p else None, vh_n["mean"] if vh_n else None)
            cer_d = pct(cer_p["mean"] if cer_p else None, cer_n["mean"] if cer_n else None)
            verdict = classify(cd_d, vh_d, cer_d)
            ok = "✓" if verdict == posture else "✗"
            total += 1
            if verdict == posture: correct += 1
            cd_s = f"{cd_d:>+12.1f}%" if cd_d is not None else "       N/A"
            vh_s = f"{vh_d:>+11.1f}%" if vh_d is not None else "       N/A"
            print(f"  {user:<8} {ang:<8} {posture:<24} {cd_s:>14} {vh_s:>13} {verdict:>20} {posture:>20} {ok:>6}")

print(f"\n  → 정확도: {correct}/{total} = {correct/total*100:.1f}%")
