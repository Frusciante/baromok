"""V2 기획안 + 진행현황 PDF 생성 스크립트"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 폰트 등록 ──────────────────────────────────────────────────────────────
pdfmetrics.registerFont(TTFont("PR", "assets/fonts/NanumSquareR.ttf"))
pdfmetrics.registerFont(TTFont("PB", "assets/fonts/NanumSquareB.ttf"))

W, H = A4
MARGIN = 18 * mm

# ── 스타일 정의 ────────────────────────────────────────────────────────────
def style(name, **kw):
    base = dict(fontName="PR", fontSize=10, leading=16, textColor=colors.HexColor("#1a1a1a"))
    base.update(kw)
    return ParagraphStyle(name, **base)

S = {
    "title":   style("title",  fontName="PB", fontSize=22, leading=30, spaceAfter=4,  textColor=colors.HexColor("#3b1f8c")),
    "meta":    style("meta",   fontSize=9,  leading=14, textColor=colors.HexColor("#666666"), spaceAfter=2),
    "h1":      style("h1",     fontName="PB", fontSize=15, leading=22, spaceBefore=14, spaceAfter=4, textColor=colors.HexColor("#3b1f8c")),
    "h2":      style("h2",     fontName="PB", fontSize=12, leading=18, spaceBefore=10, spaceAfter=3, textColor=colors.HexColor("#4a2da8")),
    "h3":      style("h3",     fontName="PB", fontSize=10, leading=16, spaceBefore=7,  spaceAfter=2, textColor=colors.HexColor("#333333")),
    "body":    style("body",   fontSize=9.5, leading=16, spaceAfter=4),
    "bullet":  style("bullet", fontSize=9.5, leading=16, leftIndent=12, spaceAfter=2, bulletIndent=0),
    "code":    style("code",   fontName="PR", fontSize=8.5, leading=13, leftIndent=10,
                     backColor=colors.HexColor("#f4f0ff"), textColor=colors.HexColor("#2d1a6b"),
                     borderPadding=(4,6,4,6), spaceAfter=6),
    "done":    style("done",   fontName="PB", fontSize=11, leading=16, textColor=colors.HexColor("#1a7a3c")),
    "todo":    style("todo",   fontName="PB", fontSize=11, leading=16, textColor=colors.HexColor("#b8290a")),
    "section_label": style("section_label", fontName="PB", fontSize=9,
                           textColor=colors.white, leading=14),
}

def hr(): return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#c4b5f7"), spaceAfter=6)
def sp(h=4): return Spacer(1, h)
def P(text, s="body"): return Paragraph(text, S[s])
def B(text): return Paragraph(f"• {text}", S["bullet"])

def header_box(text, bg="#3b1f8c"):
    t = Table([[Paragraph(text, S["section_label"])]],
              colWidths=[W - 2*MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor(bg)),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return t

def simple_table(headers, rows, col_widths, header_bg="#4a2da8"):
    data = [[Paragraph(h, ParagraphStyle("th", fontName="PB", fontSize=8.5,
                                          leading=13, textColor=colors.white))
             for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), ParagraphStyle("td", fontName="PR", fontSize=8.5,
                                                        leading=13, textColor=colors.HexColor("#1a1a1a")))
                     for c in row])
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor(header_bg)),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, colors.HexColor("#f9f7ff")]),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#d0c8f0")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    return t

def status_table(rows):
    """진행현황 테이블 (아이콘 + 색상 구분)"""
    data = [[
        Paragraph("항목", ParagraphStyle("th", fontName="PB", fontSize=8.5, leading=13, textColor=colors.white)),
        Paragraph("상태", ParagraphStyle("th", fontName="PB", fontSize=8.5, leading=13, textColor=colors.white)),
        Paragraph("비고", ParagraphStyle("th", fontName="PB", fontSize=8.5, leading=13, textColor=colors.white)),
    ]]
    cw = [W - 2*MARGIN - 22*mm - 55*mm, 22*mm, 55*mm]
    for item, done, note in rows:
        icon = "✅" if done else "❌"
        bg   = colors.HexColor("#e8f5e9") if done else colors.HexColor("#fdecea")
        txt_color = colors.HexColor("#1a7a3c") if done else colors.HexColor("#b8290a")
        data.append([
            Paragraph(item, ParagraphStyle("td", fontName="PR", fontSize=8.5, leading=14, textColor=colors.HexColor("#1a1a1a"))),
            Paragraph(icon, ParagraphStyle("ic", fontName="PR", fontSize=10, leading=14, textColor=txt_color, alignment=1)),
            Paragraph(note, ParagraphStyle("td", fontName="PR", fontSize=8.0, leading=12, textColor=colors.HexColor("#444444"))),
        ])
    t = Table(data, colWidths=cw)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), colors.HexColor("#4a2da8")),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#d0c8f0")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, colors.HexColor("#f9f7ff")]),
    ]))
    return t

# ── 문서 구성 ──────────────────────────────────────────────────────────────
story = []

# ── 표지 ──────────────────────────────────────────────────────────────────
story += [
    sp(30),
    P("바로목 자세 감지 로직", "title"),
    P("V2 기획안 + 구현 현황", "title"),
    sp(6),
    hr(),
    sp(4),
    P("문서 버전: 2.0　　　작성일: 2026-05-25", "meta"),
    P("담당: 알고리즘 팀원　　비교 대상: V1 (광대/어깨 비율) → V2 (Δ% + 표준편차 기반 개인화)", "meta"),
    sp(20),
]

# ═══════════════════════════════════════════════════════════════════════════
# PART 1 — 기획안
# ═══════════════════════════════════════════════════════════════════════════
story += [
    header_box("PART 1　기획안"),
    sp(10),
    P("1. V2 설계 철학", "h1"), hr(),
    P("1.1 V1의 한계", "h2"),
    B("고정 임계값: 사용자 신체 비율 차이를 반영 못 함 (cheek_distance neutral 절대값이 사용자 간 ±29% 차이)"),
    B("단일 비율: 광대/어깨 만으로는 자세 유형 구분 어려움"),
    B("어깨 의존: 극단 각도(&lt;100° 또는 &gt;110°)에서 어깨 검출 불안정 → 판정 실패"),
    sp(6),
    P("1.2 V2 핵심 원칙", "h2"),
    B("얼굴 중심 지표 우선 — 어깨가 잡히면 보조로 활용, 안 잡혀도 판정 가능"),
    B("Δ% 기반 판정 — 절대값이 아닌 개인 baseline 대비 변화율"),
    B("neutral 1회 캘리브로 자동 임계값 도출 — UX 부담 V1과 동일"),
    B("표준편차 기반 임계값 — 사용자 흔들림 범위를 벗어나면 자세 변경 판정"),
    sp(6),
    P("1.3 UX 측면 (V1 대비)", "h2"),
    B("캘리브레이션 절차: 변화 없음 (neutral 자세 1회 수집)"),
    B("사용자에게는 V1과 같은 흐름, 알고리즘만 개선"),
    sp(10),
]

# 2. 사용 지표
story += [
    P("2. 사용 지표 정의", "h1"), hr(),
    P("2.1 주요 지표 (Primary)", "h2"),
    simple_table(
        ["지표", "정의", "정규화", "주요 용도"],
        [
            ["cheek_distance",      "양 광대 사이 거리",              "프레임 너비",                  "머리-카메라 거리 변화"],
            ["eye_distance",        "양 눈 사이 거리",                "프레임 너비",                  "머리-카메라 거리 변화 (보조)"],
            ["cheek_eye_ratio",     "cheek_distance / eye_distance",  "비율",                         "각도 안정 지표"],
            ["face_center_y",       "얼굴 중심 세로 좌표",            "프레임 높이 (0=상단, 1=하단)", "머리 상하 위치"],
            ["eye_line_tilt",       "양 눈선의 기울기 (도)",          "—",                            "head_tilt 핵심 지표"],
            ["eye_symmetry_ratio",  "좌우 눈 크기 대칭도",            "비율",                         "비대칭 자세 검출"],
            ["cheek_symmetry_ratio","좌우 광대 대칭도",               "비율",                         "비대칭 자세 검출"],
        ],
        [36*mm, 46*mm, 38*mm, W - 2*MARGIN - 36*mm - 46*mm - 38*mm],
    ),
    sp(8),
    P("2.2 보조 지표 (Auxiliary, 조건부 사용)", "h2"),
    simple_table(
        ["지표", "조건", "활용"],
        [
            ["shoulder_width",      "어깨 검출률 ≥ 70% (최근 5초)",   "forward_head_only vs full 구분, recline 보조"],
            ["shoulder_tilt_deg",   "어깨 검출률 ≥ 70%",              "head_tilt 보조 검증, chin_rest 신호"],
            ["chin_occlusion",      "모든 경우",                       "chin_rest 검출"],
            ["hand_face_score",     "모든 경우",                       "chin_rest 검출 (손-얼굴 거리 + 폐색)"],
            ["chin_alignment_offset","모든 경우",                      "자세 미세 보정"],
        ],
        [38*mm, 46*mm, W - 2*MARGIN - 38*mm - 46*mm],
    ),
    sp(6),
    B("어깨 지표는 검출 신뢰도에 따라 동적 활용. 안 잡히면 얼굴 지표만으로 판정."),
    B("❌ 폐기 지표: vh_ratio — 다중 사용자 검증에서 부호 반대 발생, 일부 사용자(U3)는 측정 자체 실패"),
    sp(10),
]

# 3. 자세별 판정 로직
story += [
    P("3. 자세별 판정 로직", "h1"), hr(),
    P("3.1 감지 대상 자세", "h2"),
    simple_table(
        ["자세", "표시 라벨", "주요 지표", "보조 지표"],
        [
            ["neutral",            "바른 자세",              "(캘리브레이션 baseline)",               "—"],
            ["forward_head_only",  "거북목 경향",            "cheek_distance ↑, eye_distance ↑",      "face_center_y 살짝 ↑"],
            ["forward_head_full",  "몸 기울어진 거북목 의심","cheek_distance ↑↑, shoulder_width ↑",   "face_center_y ↑"],
            ["recline",            "기댄 자세 의심",         "cheek_distance ↑↑, face_center_y ↓/↑",  "eye_line_tilt, shoulder_width ↓"],
            ["head_tilt",          "고개 기울임 의심",       "eye_line_tilt 절대값 변화",              "cheek_symmetry_ratio ↓, shoulder_tilt_deg"],
            ["chin_rest",          "턱 괸 자세 의심",        "hand_face_score ↑, eye_line_tilt",       "cheek_symmetry_ratio ↓"],
        ],
        [36*mm, 36*mm, 56*mm, W - 2*MARGIN - 36*mm - 36*mm - 56*mm],
    ),
    sp(8),
    P("3.2 자세 충돌 처리 정책", "h2"),
    P("여러 자세가 동시에 임계값을 넘는 경우, baseline에서 가장 멀어진(deviation_score 최대) 자세 하나만 표시.", "body"),
    P("deviation_score = sum(abs(Δ% of each primary indicator) × indicator_weight) / number_of_indicators", "code"),
    sp(6),
    P("3.3 Guards 시스템 (자세별 오탐 방지)", "h2"),
    simple_table(
        ["자세", "Guards"],
        [
            ["forward_head_only",  "abs(eye_line_tilt) &lt; 12°, cheek_symmetry_ratio 변화 &lt; 15%"],
            ["forward_head_full",  "cheek_symmetry_ratio 변화 &lt; 15%, shoulder_tilt_deg &lt; 10°"],
            ["recline",            "abs(eye_line_tilt) &lt; 12°, shoulder_tilt_deg &lt; 10°, cheek_symmetry_ratio 변화 &lt; 15%"],
            ["head_tilt",          "(가드 없음 — eye_line_tilt가 주 신호)"],
            ["chin_rest",          "(기존 V1 로직 — hand_face_score 기반)"],
        ],
        [42*mm, W - 2*MARGIN - 42*mm],
    ),
    sp(10),
]

# 4. 캘리브레이션
story += [
    P("4. 캘리브레이션 절차", "h1"), hr(),
    P("4.1 단순화된 1단계 캘리브레이션", "h2"),
    P("V1과 동일한 UX — neutral 자세 1회 수집 (총 13초: 3초 대기 + 10초 측정)", "body"),
    sp(6),
    P("4.2 수집 파라미터", "h2"),
    simple_table(
        ["항목", "값", "비고"],
        [
            ["wait_seconds",          "3.0",      "사용자가 자세 잡을 시간"],
            ["collect_seconds",       "10.0",     "안정적 평균/표준편차 도출용"],
            ["minimum_valid_frames",  "60",       "검증 기준 (JSON 설정값, 소프트코딩)"],
            ["expected_samples",      "100~300",  "FPS 따라"],
        ],
        [50*mm, 30*mm, W - 2*MARGIN - 50*mm - 30*mm],
    ),
    sp(8),
    P("4.3 캘리브레이션 데이터 유효성 검증", "h2"),
    simple_table(
        ["검증 항목", "조건", "실패 시 동작"],
        [
            ["프레임 수",       "≥ 60",       "'조명/카메라 확인' 안내 후 재측정"],
            ["얼굴 검출률",     "≥ 90%",      "동일"],
            ["지표 안정성",     "CV &lt; 0.1","'측정 중 움직임 줄여주세요'"],
            ["어깨 검출률",     "(정보 기록만)", "70% 미만이면 보조 지표 비활성화"],
        ],
        [38*mm, 28*mm, W - 2*MARGIN - 38*mm - 28*mm],
    ),
    sp(8),
    P("4.4 임계값 자동 도출 공식 (방법 2 + 방법 3 결합)", "h2"),
    P("threshold = max(neutral_mean + 3 × neutral_std,  neutral_mean × 1.05)", "code"),
    P("threshold_delta_pct = (threshold - neutral_mean) / neutral_mean × 100", "code"),
    sp(4),
    B("cheek_distance → forward / recline / forward_full 공통 임계값"),
    B("eye_distance → forward 보조 검증"),
    B("shoulder_width → forward_full 검증 (어깨 가용 시)"),
    B("eye_line_tilt → head_tilt 임계값 (기본 ±5°, 최소 baseline std × 3)"),
    sp(10),
]

# 5. 시스템 통합
story += [
    P("5. 시스템 통합", "h1"), hr(),
    P("5.1 상태 머신 호환", "h2"),
    simple_table(
        ["confidence", "상태"],
        [
            ["&lt; 0.45",       "NORMAL"],
            ["0.45 ~ 0.60",    "WARNING"],
            ["≥ 0.60",         "BAD_POSTURE"],
        ],
        [50*mm, W - 2*MARGIN - 50*mm],
    ),
    sp(8),
    P("5.2 자세별 지속 시간 (sustain_seconds)", "h2"),
    simple_table(
        ["자세", "sustain_seconds"],
        [
            ["forward_head_only",  "1.5"],
            ["forward_head_full",  "1.5"],
            ["recline",            "1.5"],
            ["head_tilt",          "1.5"],
            ["chin_rest",          "2.0"],
        ],
        [70*mm, W - 2*MARGIN - 70*mm],
    ),
    sp(8),
    P("5.3 민감도 설정 연동", "h2"),
    simple_table(
        ["민감도", "confidence 최저 표시 임계"],
        [
            ["예민 (high)",    "0.30"],
            ["보통 (medium)", "0.50"],
            ["둔감 (low)",     "0.70"],
        ],
        [60*mm, W - 2*MARGIN - 60*mm],
    ),
    sp(10),
]

# 6. 실험 데이터
story += [
    P("6. 실험 데이터 기반 검증 (2026-05-25 기준)", "h1"), hr(),
    P("6.1 3 사용자 측정 결과 (107deg 기준)", "h2"),
    simple_table(
        ["사용자", "forward_head_only Δ%", "recline Δ%"],
        [
            ["U1", "+6.5%",   "+15.8%"],
            ["U2", "+133.5%", "+42.2%"],
            ["U3", "+4.9%",   "+4.2%"],
        ],
        [40*mm, 60*mm, W - 2*MARGIN - 40*mm - 60*mm],
    ),
    sp(8),
    P("6.2 V1 → V2 개선 매핑", "h2"),
    simple_table(
        ["발견된 문제", "V1 대응", "V2 대응"],
        [
            ["사용자별 cheek_distance 절대값 차이 (±29%)",    "고정 비율 사용, 일반화 실패",     "Δ% 기반 → 개인차 무관"],
            ["사용자별 자세 수행 방식 차이 (Δ% 4~135%)",     "단일 임계값으로 일반화 불가",     "표준편차 기반 자동 임계값"],
            ["vh_ratio 부호 반대 발생",                       "—",                               "vh_ratio 완전 제거"],
            ["U3: 자세 간 변화량 너무 작음 (~5%)",            "감지 불가",                       "최소 5% 변화 보장 + 캘리브 검증 단계 경고"],
            ["노트북 어깨 검출 불안정",                       "어깨 의존 시 실패",                "어깨 검출률 70% 미만 시 자동 비활성화"],
        ],
        [52*mm, 42*mm, W - 2*MARGIN - 52*mm - 42*mm],
    ),
    sp(10),
    PageBreak(),
]

# ═══════════════════════════════════════════════════════════════════════════
# PART 2 — 구현 현황
# ═══════════════════════════════════════════════════════════════════════════
story += [
    header_box("PART 2　구현 현황 (2026-05-28 기준)"),
    sp(10),
]

# 완료
story += [
    P("✅  완료 항목", "done"),
    sp(4),
    P("🔴 Must Have — 전부 완료", "h2"),
    status_table([
        ("calibration_v2.py — 1단계 캘리브레이션 수집 모듈", True, ""),
        ("baseline_v2.json 저장 / 로드 / 검증", True, "save(), load(), is_loaded()"),
        ("자동 임계값 도출 (mean + 3*std + 최소 5%)", True, "_derive_thresholds()"),
        ("classify_posture() — 5개 자세 + Guards", True, "judge() + _eval_*() 5종"),
        ("자세 충돌 시 deviation_score 최대값 선택", True, "max(candidates, key=...)"),
        ("상태 머신 출력 (NORMAL / WARNING / BAD_POSTURE)", True, "_frame_state() confidence 기준"),
        ("어깨 검출률 모니터링 (70% 미만 시 보조 비활성화)", True, "_is_shoulder_usable() 슬라이딩 윈도우 5초"),
        ("confidence 계산", True, "_compute_confidence() ratio 기반"),
        ("sustain_seconds 자세 확정", True, "update_sustain()"),
        ("V1과 병행 운영 (V1/V2 토글)", True, "hub_screen 토글 + camera_worker 분기"),
    ]),
    sp(14),
]

# 미완료
story += [
    P("❌  미완료 항목", "todo"),
    sp(4),
    P("🔴 Must Have 중 미완료", "h2"),
    status_table([
        ("민감도 설정 UI → V2 엔진 연동",
         False,
         "set_sensitivity()는 구현됨. 설정 화면 슬라이더가 V1 숫자값만 저장하고 V2에 high/medium/low 전달 안 함. 항상 'medium'"),
    ]),
    sp(8),
    P("🟡 Should Have 중 미완료", "h2"),
    status_table([
        ("캘리브레이션 UI 화면 (V2 전용)",
         False,
         "V2 병행 수집은 하지만 품질 점수·진행 상태 표시 없음. V1 UI 그대로 사용 중"),
        ("실시간 이벤트 JSON 포맷 — 세션 기록",
         False,
         "JudgmentResultV2 객체 생성은 됨. 세션 매니저에는 V1 형식만 기록"),
        ("face_center_y / cheek_eye_ratio 판정 활용",
         False,
         "calibration_v2에서 수집·통계는 함. judgment_engine_v2 실제 판정 로직(_eval_*)에서 미사용"),
    ]),
    sp(8),
    P("🟢 Nice to Have 중 미완료", "h2"),
    status_table([
        ("chin_rest 가중치 미세 조정",    False, "V1 값 그대로 (w_hand=0.30, w_eye=0.35, ...)"),
        ("캘리브레이션 품질 점수 UI 표시", False, "계산은 하지만 사용자에게 미노출"),
        ("디버그 모드 (candidate score 시각화)", False, "v2_debug.py는 있으나 운영 UI 미통합"),
    ]),
    sp(14),
]

# 알려진 한계
story += [
    P("7. 알려진 한계 및 제외 사항", "h1"), hr(),
    P("7.1 한계 (발표 시 명시)", "h2"),
    B("캘리브레이션 자세 정확도 의존: 사용자가 neutral 자세를 부정확하게 잡으면 임계값 도출 오류"),
    B("자세 수행 방식 일관성: 캘리브 시점과 실제 사용 시점의 자세가 일치해야 함"),
    B("U3 케이스 (자세 변화량 &lt; 5%): '최소 5% 변화 보장'으로 일부 완화, 그래도 정밀도 제한적"),
    B("노트북 극단 각도 시 어깨 불가: forward_head_only/full 구분 어려움 (얼굴 지표만 사용)"),
    sp(6),
    P("7.2 V2에서 제외된 자세", "h2"),
    B("yaw_turn (고개 좌우 회전) — 정상 동작, 오탐 대조군으로만 실험에서 사용"),
    B("crossed_leg_estimated (다리 꼬기) — 본 프로젝트 범위 제외"),
    sp(6),
    P("7.3 향후 과제", "h2"),
    B("사용자 5명 이상 데이터로 임계값 보정 계수 튜닝"),
    B("ML 기반 분류기로의 확장 (현재 규칙 기반)"),
    B("slouching, looking_down 등 추가 자세"),
    sp(10),
]

# 마일스톤
story += [
    P("8. 다음 마일스톤", "h1"), hr(),
    simple_table(
        ["순서", "내용", "상태"],
        [
            ["1", "V2 핵심 알고리즘 구현 완료",        "✅ 완료"],
            ["2", "민감도 UI ↔ V2 엔진 연동",          "❌ 진행 필요"],
            ["3", "V2 세션 기록 포맷 통합",             "❌ 진행 필요"],
            ["4", "V1 (개선 버전) vs V2 비교 테스트",   "대기 중"],
            ["5", "더 정확한 버전 채택 → 발표 PPT 작성","대기 중"],
        ],
        [16*mm, W - 2*MARGIN - 16*mm - 28*mm, 28*mm],
    ),
    sp(20),
    hr(),
    P("문의: UI/기획 담당자　　　생성일: 2026-05-28", "meta"),
]

# ── PDF 빌드 ───────────────────────────────────────────────────────────────
out = "바로목_V2_기획안_구현현황.pdf"
doc = SimpleDocTemplate(
    out,
    pagesize=A4,
    leftMargin=MARGIN, rightMargin=MARGIN,
    topMargin=MARGIN,  bottomMargin=MARGIN,
    title="바로목 V2 기획안 + 구현 현황",
    author="바로목 알고리즘 팀",
)
doc.build(story)
print("PDF generated: " + out)
