import zipfile, json, sys

# ---- Other user's data (from zip) ----
z = zipfile.ZipFile(r'C:\Users\JunHa\Downloads\20260524_223251.zip')
other_summary = json.loads(z.read('summary.json'))
other_report = z.read('report.txt').decode('utf-8')

# ---- My data (local) ----
import os
local_dir = r'C:\Users\JunHa\Desktop\바로목\baromok\debug_logs\angle_experiment\20260521_164830'
with open(os.path.join(local_dir, 'summary.json'), encoding='utf-8') as f:
    local_summary = json.load(f)

METRICS = ['cheek_distance', 'eye_distance', 'cheek_eye_ratio', 'vh_ratio',
           'face_center_y', 'face_center_x', 'shoulder_width']

def get_baseline(summary_list, baseline_label='+00deg'):
    for cond in summary_list:
        if cond['label'] == baseline_label:
            return cond
    return None

def pct_change(val, base):
    if base == 0:
        return None
    return (val - base) / abs(base) * 100

print("=" * 90)
print(" 비교 분석: 나 (20260521) vs 다른 사용자 (20260524)")
print(" 각도 눈대중이므로 경향성 위주로 해석")
print("=" * 90)

# Detection rates comparison
print("\n[검출률 비교]")
print(f"  {'조건':10s}  {'나 face':>10s}  {'나 shoulder':>12s}  {'상대 face':>10s}  {'상대 shoulder':>13s}")
print("  " + "-" * 60)

other_by_label = {c['label']: c for c in other_summary}
local_by_label = {c['label']: c for c in local_summary}

# Common angles
all_labels = ['-20deg', '-10deg', '-05deg', '+00deg', '+05deg', '+10deg', '+20deg']
for lbl in all_labels:
    # normalize: local uses '+05deg' notation, other uses same
    me = local_by_label.get(lbl)
    them = other_by_label.get(lbl)
    me_face = f"{me['face_detection_rate']:.1%}" if me else "—"
    me_shldr = f"{me['shoulder_detection_rate']:.1%}" if me else "—"
    them_face = f"{them['face_detection_rate']:.1%}" if them else "—"
    them_shldr = f"{them['shoulder_detection_rate']:.1%}" if them else "—"
    print(f"  {lbl:10s}  {me_face:>10s}  {me_shldr:>12s}  {them_face:>10s}  {them_shldr:>13s}")

# Key metrics comparison
print("\n[핵심 지표 비교 — 기준(+00deg) 대비 Δ%]")

for metric in METRICS:
    print(f"\n  [{metric}]")
    print(f"  {'조건':10s}  {'나 mean':>9s}  {'나 CV%':>7s}  {'나 Δ%':>8s}  |  {'상대 mean':>9s}  {'상대 CV%':>8s}  {'상대 Δ%':>8s}")
    print("  " + "-" * 80)

    local_base = get_baseline(local_summary)
    other_base = get_baseline(other_summary)
    local_base_val = local_base['metrics'].get(metric, {}).get('mean') if local_base else None
    other_base_val = other_base['metrics'].get(metric, {}).get('mean') if other_base else None

    for lbl in all_labels:
        me = local_by_label.get(lbl)
        them = other_by_label.get(lbl)

        me_metric = (me.get('metrics') or {}).get(metric) if me else None
        if me and me_metric is not None:
            me_m = me_metric['mean']
            me_cv = me_metric['cv'] * 100
            me_d = pct_change(me_m, local_base_val)
            if lbl == '+00deg':
                me_str = f"{me_m:9.5f}  {me_cv:6.1f}%     base"
            elif me_d is not None:
                me_str = f"{me_m:9.5f}  {me_cv:6.1f}%  {me_d:+7.1f}%"
            else:
                me_str = f"{me_m:9.5f}  {me_cv:6.1f}%       N/A"
        else:
            me_str = f"{'N/A':>9s}  {'N/A':>7s}  {'N/A':>8s}"

        them_metric = (them.get('metrics') or {}).get(metric) if them else None
        if them and them_metric is not None:
            them_m = them_metric['mean']
            them_cv = them_metric['cv'] * 100
            them_d = pct_change(them_m, other_base_val)
            if lbl == '+00deg':
                them_str = f"{them_m:9.5f}  {them_cv:7.1f}%     base"
            elif them_d is not None:
                them_str = f"{them_m:9.5f}  {them_cv:7.1f}%  {them_d:+7.1f}%"
            else:
                them_str = f"{them_m:9.5f}  {them_cv:7.1f}%       N/A"
        else:
            them_str = f"{'N/A':>9s}  {'N/A':>8s}  {'N/A':>8s}"

        print(f"  {lbl:10s}  {me_str}  |  {them_str}")

# Trend agreement summary
print("\n" + "=" * 90)
print(" 경향성 일치도 요약")
print("=" * 90)
print("""
  분석 방법: 공통 각도(−10, −5, 0, +5)에서 각 지표의 Δ% 부호(방향) 및 크기 비교
  ⬆ = 기준 대비 증가, ⬇ = 감소, ≈ = 5% 미만 변화

  지표               경향 일치 여부    해석
  ─────────────────────────────────────────────────────────────
""")

# Calculate trend agreement
metrics_to_compare = ['cheek_distance', 'eye_distance', 'cheek_eye_ratio', 'vh_ratio', 'face_center_y', 'shoulder_width']
common_angles = ['-10deg', '-05deg', '+05deg']

for metric in metrics_to_compare:
    lb_base = get_baseline(local_summary)
    ob_base = get_baseline(other_summary)
    lbv = lb_base['metrics'].get(metric, {}).get('mean') if lb_base else None
    obv = ob_base['metrics'].get(metric, {}).get('mean') if ob_base else None

    agreements = 0
    total = 0
    details = []
    for lbl in common_angles:
        me = local_by_label.get(lbl)
        them = other_by_label.get(lbl)
        if not me or not them:
            continue
        me_mval = (me.get('metrics') or {}).get(metric)
        them_mval = (them.get('metrics') or {}).get(metric)
        if me_mval is None or them_mval is None:
            continue
        me_d = pct_change(me_mval['mean'], lbv)
        them_d = pct_change(them_mval['mean'], obv)
        if me_d is None or them_d is None:
            continue
        total += 1
        same_dir = (me_d > 1 and them_d > 1) or (me_d < -1 and them_d < -1) or (abs(me_d) <= 1 and abs(them_d) <= 1)
        if same_dir:
            agreements += 1
        details.append(f"{lbl}:{'+' if me_d>0 else '-'}/{'+' if them_d>0 else '-'}")

    if total > 0:
        pct = agreements / total * 100
        flag = "✓ 일치" if pct >= 67 else "△ 혼재" if pct >= 33 else "✗ 불일치"
        print(f"  {metric:22s} {flag} ({agreements}/{total})  {' '.join(details)}")
    else:
        print(f"  {metric:22s} 데이터 부족")
