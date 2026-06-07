"""3명의 사용자 데이터 통합 분석 — 기획안 수정용"""
import zipfile, json
from pathlib import Path

# User 1: 본인 (로컬)
U1_DIRS = {
    "103deg": r"C:\Users\JunHa\Desktop\바로목\baromok\debug_logs\posture_experiment\20260521_173723_103deg",
    "107deg": r"C:\Users\JunHa\Desktop\바로목\baromok\debug_logs\posture_experiment\20260521_173837_107deg",
    "112deg": r"C:\Users\JunHa\Desktop\바로목\baromok\debug_logs\posture_experiment\20260521_174034_112deg",
}
# User 2: 어제 받은 데이터
U2_ZIPS = {
    "103deg": r"C:\Users\JunHa\Downloads\20260524_232119_103deg.zip",
    "107deg": r"C:\Users\JunHa\Downloads\20260524_232256_107deg.zip",
    "112deg": r"C:\Users\JunHa\Downloads\20260524_232422_112deg.zip",
}
# User 3: 오늘 받은 데이터
U3_ZIPS = {
    "103deg": r"C:\Users\JunHa\Downloads\20260525_201906_103deg.zip",
    "107deg": r"C:\Users\JunHa\Downloads\20260525_202229_107deg.zip",
    "112deg": r"C:\Users\JunHa\Downloads\20260525_202536_112deg.zip",
}

def load_dir(d):
    p = Path(d)
    return json.loads((p / "summary.json").read_text(encoding="utf-8"))

def load_zip(p):
    z = zipfile.ZipFile(p)
    return json.loads(z.read("summary.json"))

def get_cond(summary, label):
    for c in summary:
        if c["label"] == label:
            return c
    return None

def get_metric(cond, key):
    if cond is None: return None
    return (cond.get("metrics") or {}).get(key)

def pct(val, base):
    if val is None or base is None or base == 0: return None
    return (val - base) / abs(base) * 100

ANGLES = ["103deg", "107deg", "112deg"]
POSTURES = ["forward_head_only", "recline"]

# Load all
data = {}
for ang in ANGLES:
    data[ang] = {
        "U1": load_dir(U1_DIRS[ang]),
        "U2": load_zip(U2_ZIPS[ang]),
        "U3": load_zip(U3_ZIPS[ang]),
    }

# ─────────────────────────────────────────────────────────
# Section 1: Neutral baseline 절대값 — 사용자 간 개인차
# ─────────────────────────────────────────────────────────
print("=" * 100)
print(" [1] Neutral baseline 절대값 — 3 사용자 비교")
print("=" * 100)

KEY = ["cheek_distance", "eye_distance", "cheek_eye_ratio", "vh_ratio", "face_center_y"]

for ang in ANGLES:
    print(f"\n  ▸ {ang}")
    print(f"    {'지표':<22} {'U1':>10} {'U2':>10} {'U3':>10}  {'U2-U1 Δ%':>10} {'U3-U1 Δ%':>10} {'U3-U2 Δ%':>10}")
    print("    " + "-" * 92)
    for key in KEY:
        u1n = get_metric(get_cond(data[ang]["U1"], "neutral"), key)
        u2n = get_metric(get_cond(data[ang]["U2"], "neutral"), key)
        u3n = get_metric(get_cond(data[ang]["U3"], "neutral"), key)
        if u1n is None or u2n is None or u3n is None:
            continue
        d12 = pct(u2n["mean"], u1n["mean"])
        d13 = pct(u3n["mean"], u1n["mean"])
        d23 = pct(u3n["mean"], u2n["mean"])
        print(f"    {key:<22} {u1n['mean']:>10.4f} {u2n['mean']:>10.4f} {u3n['mean']:>10.4f}  {d12:>+9.1f}% {d13:>+9.1f}% {d23:>+9.1f}%")

# ─────────────────────────────────────────────────────────
# Section 2: 자세별 Δ% — 방향 일관성 확인
# ─────────────────────────────────────────────────────────
print("\n" + "=" * 100)
print(" [2] 자세별 Δ% (neutral 대비) — 3 사용자 방향성 일관 여부")
print("=" * 100)

for posture in POSTURES:
    print(f"\n  ▸ {posture} (vs neutral)")
    print(f"    {'지표':<22}", end="")
    for ang in ANGLES:
        print(f"  {ang+' U1':>10} {ang+' U2':>10} {ang+' U3':>10}", end="")
    print()
    print("    " + "-" * 110)
    for key in KEY:
        print(f"    {key:<22}", end="")
        for ang in ANGLES:
            for u in ["U1", "U2", "U3"]:
                n = get_metric(get_cond(data[ang][u], "neutral"), key)
                p = get_metric(get_cond(data[ang][u], posture), key)
                d = pct(p["mean"] if p else None, n["mean"] if n else None)
                s = f"{d:>+9.1f}%" if d is not None else "      N/A"
                print(f"  {s:>10}", end="")
        print()

# ─────────────────────────────────────────────────────────
# Section 3: 기존 임계값 검증 — 3명 데이터에서 정확도
# ─────────────────────────────────────────────────────────
print("\n" + "=" * 100)
print(" [3] 기존 임계값 룰 검증 — 3 사용자 정확도")
print("=" * 100)
print("""
  룰 (어제 도출):
    1. cheek_distance Δ% > +14%  → recline
    2. cheek_distance Δ% ≤ +14% AND vh_ratio Δ% > +7%  → forward_head_only
""")

def classify(cd_d, vh_d):
    if cd_d is None or vh_d is None:
        return "N/A"
    if cd_d > 14:
        return "recline"
    if vh_d > 7:
        return "forward_head_only"
    return "기타"

print(f"  {'사용자':<6} {'각도':<8} {'자세':<22} {'cheek_d Δ%':>12} {'vh_r Δ%':>10} {'판정':>20} {'정답':>20} {'결과':>6}")
print("  " + "-" * 100)

results = {"U1": [0, 0], "U2": [0, 0], "U3": [0, 0]}
for user in ["U1", "U2", "U3"]:
    for ang in ANGLES:
        src = data[ang][user]
        neutral = get_cond(src, "neutral")
        for posture in POSTURES:
            cond = get_cond(src, posture)
            if cond is None: continue
            cd_n = get_metric(neutral, "cheek_distance")
            cd_p = get_metric(cond, "cheek_distance")
            vh_n = get_metric(neutral, "vh_ratio")
            vh_p = get_metric(cond, "vh_ratio")
            cd_d = pct(cd_p["mean"] if cd_p else None, cd_n["mean"] if cd_n else None)
            vh_d = pct(vh_p["mean"] if vh_p else None, vh_n["mean"] if vh_n else None)
            verdict = classify(cd_d, vh_d)
            ok = "O" if verdict == posture else "X"
            results[user][1] += 1
            if verdict == posture: results[user][0] += 1
            cd_s = f"{cd_d:>+10.1f}%" if cd_d is not None else "      N/A"
            vh_s = f"{vh_d:>+8.1f}%" if vh_d is not None else "    N/A"
            print(f"  {user:<6} {ang:<8} {posture:<22} {cd_s:>12} {vh_s:>10} {verdict:>20} {posture:>20} {ok:>6}")

print("\n  사용자별 정확도:")
total_c, total_n = 0, 0
for u in ["U1", "U2", "U3"]:
    c, n = results[u]
    total_c += c; total_n += n
    print(f"    {u}: {c}/{n} = {c/n*100:.1f}%")
print(f"    전체: {total_c}/{total_n} = {total_c/total_n*100:.1f}%")

# ─────────────────────────────────────────────────────────
# Section 4: 사용자별 자체 임계값 추출
# ─────────────────────────────────────────────────────────
print("\n" + "=" * 100)
print(" [4] 사용자별 cheek_distance Δ% 분포 — 일반 임계값 추출 가능성")
print("=" * 100)

print(f"\n  {'사용자':<6} {'각도':<8} {'forward_head_only Δ%':>22} {'recline Δ%':>14}")
print("  " + "-" * 60)
all_fwd, all_rec = [], []
for user in ["U1", "U2", "U3"]:
    for ang in ANGLES:
        src = data[ang][user]
        cd_n = get_metric(get_cond(src, "neutral"), "cheek_distance")
        f_p = get_metric(get_cond(src, "forward_head_only"), "cheek_distance")
        r_p = get_metric(get_cond(src, "recline"), "cheek_distance")
        f_d = pct(f_p["mean"] if f_p else None, cd_n["mean"] if cd_n else None)
        r_d = pct(r_p["mean"] if r_p else None, cd_n["mean"] if cd_n else None)
        if f_d is not None: all_fwd.append(f_d)
        if r_d is not None: all_rec.append(r_d)
        f_s = f"{f_d:>+19.1f}%" if f_d is not None else "         N/A"
        r_s = f"{r_d:>+12.1f}%" if r_d is not None else "       N/A"
        print(f"  {user:<6} {ang:<8} {f_s:>22} {r_s:>14}")

if all_fwd:
    print(f"\n  forward_head_only Δ% 범위: {min(all_fwd):+.1f}% ~ {max(all_fwd):+.1f}% (평균 {sum(all_fwd)/len(all_fwd):+.1f}%)")
if all_rec:
    print(f"  recline Δ% 범위:           {min(all_rec):+.1f}% ~ {max(all_rec):+.1f}% (평균 {sum(all_rec)/len(all_rec):+.1f}%)")
if all_fwd and all_rec:
    overlap_low = max(min(all_rec), min(all_fwd))
    overlap_high = min(max(all_rec), max(all_fwd))
    print(f"\n  자세 간 겹침 구간: {overlap_low:+.1f}% ~ {overlap_high:+.1f}% ({'겹침 발생' if overlap_low < overlap_high else '깨끗하게 분리'})")
