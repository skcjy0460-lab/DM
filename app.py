from __future__ import annotations

from html import escape
from io import StringIO
from pathlib import Path

import pandas as pd
import streamlit as st

from diabetes_engine import (
    CLASS_INFO,
    CLASS_ORDER,
    POLICY_EFFECTIVE_DATE,
    POLICY_REFERENCE,
    POLICY_TITLE,
    POLICY_URL,
    Drug,
    candidate_additions,
    clinical_review,
    evaluate_regimen,
    load_catalog,
    matrix_status,
    unique_classes,
)


BASE_DIR = Path(__file__).parent
CATALOG_PATH = BASE_DIR / "data" / "drug_catalog.csv"
ROOT_CATALOG_PATH = BASE_DIR / "drug_catalog.csv"
DEFAULT_CATALOG_CSV = """product_name,ingredient,classes,dose,price_krw,price_as_of,source_note
다이아벡스정500밀리그램,Metformin HCl,MET,500mg,,,기본 내장 데이터 - 공식 약가파일 업로드 후 금액 표시
아마릴정2밀리그램,Glimepiride,SU,2mg,,,기본 내장 데이터 - 공식 약가파일 업로드 후 금액 표시
노보넘정0.5밀리그램,Repaglinide,MEG,0.5mg,,,기본 내장 데이터 - 공식 약가파일 업로드 후 금액 표시
글루코바이정100밀리그램,Acarbose,AGI,100mg,,,기본 내장 데이터 - 공식 약가파일 업로드 후 금액 표시
액토스정15밀리그램,Pioglitazone HCl,TZD,15mg,,,기본 내장 데이터 - 공식 약가파일 업로드 후 금액 표시
제미글로정50밀리그램,Gemigliptin,DPP4,50mg,,,기본 내장 데이터 - 공식 약가파일 업로드 후 금액 표시
포시리진정10밀리그램,Dapagliflozin,SGLT2_DA,10mg,334,2026-05-01,공개 약제정보 확인값 - 배포 전 공식 약가파일 대조 필요
플로가정5밀리그램,Dapagliflozin,SGLT2_DA,5mg,262,2026-05-01,공개 약제정보 확인값 - 배포 전 공식 약가파일 대조 필요
위디앙정25밀리그램,Empagliflozin,SGLT2_EM,25mg,347,2026-05-01,공개 약제정보 확인값 - 배포 전 공식 약가파일 대조 필요
슈가논정5밀리그램,Evogliptin,DPP4,5mg,,,기본 내장 데이터 - 공식 약가파일 업로드 후 금액 표시
자누비아정100밀리그램,Sitagliptin phosphate,DPP4,100mg,,,기본 내장 데이터 - 공식 약가파일 업로드 후 금액 표시
다이아벡스엑스알서방정500밀리그램,Metformin HCl,MET,500mg XR,,,기본 내장 데이터 - 공식 약가파일 업로드 후 금액 표시
직듀오서방정10/1000밀리그램,Dapagliflozin + Metformin HCl,SGLT2_DA+MET,10/1000mg,,,복합제 - 공식 약가파일 업로드 후 금액 표시
"""

st.set_page_config(
    page_title="GlucoClaim Studio | 당뇨 약제 심사",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --paper: #fbfaf6;
        --ink: #172826;
        --navy: #163b43;
        --sage: #3c7b68;
        --mint: #e7f2eb;
        --sand: #efe8dc;
        --coral: #cc6056;
        --line: #d9ddd4;
    }
    .stApp { background: var(--paper); color: var(--ink); }
    .block-container { padding-top: 1.65rem; max-width: 1580px; }
    h1, h2, h3 { color: var(--ink); letter-spacing: -.045em; }
    .hero {
        background: var(--navy); border-radius: 25px; color: #f6f4eb;
        padding: 1.35rem 1.65rem 1.25rem; margin-bottom: .85rem;
        display: flex; justify-content: space-between; align-items: flex-end; gap: 2rem;
    }
    .hero .eyebrow { font-weight: 750; font-size: .76rem; letter-spacing: .18em; color: #9fd1bb; }
    .hero h1 { color: white; margin: .3rem 0 .3rem; font-size: 2.12rem; }
    .hero p { color: #dce5de; max-width: 860px; margin: 0; line-height: 1.52; }
    .hero .stamp {
        min-width: 190px; padding: .8rem .95rem; border: 1px solid #45656a;
        border-radius: 15px; color: #ecf4ef; font-size: .83rem;
    }
    .module {
        color: var(--sage); letter-spacing: .14em; font-size: .74rem;
        font-weight: 800; margin: .72rem 0 .5rem;
    }
    .guide-note {
        border: 1px solid #d1ddd5; background: #eef5f0; border-radius: 13px;
        color: #324d49; padding: .62rem .85rem; font-size: .86rem; margin: .15rem 0 .9rem;
    }
    div[data-testid="stForm"], div[data-testid="stExpander"] {
        border: 1px solid var(--line); border-radius: 17px; background: #ffffff;
        padding: .2rem .48rem;
    }
    div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 12px; }
    .review-card {
        border-radius: 16px; background: white; border: 1px solid var(--line);
        padding: .83rem .95rem; margin: .55rem 0;
    }
    .review-card.ok { border-left: 5px solid var(--sage); }
    .review-card.no { border-left: 5px solid var(--coral); }
    .review-card.wait { border-left: 5px solid #ba9360; }
    .review-card .state { font-weight: 800; font-size: .88rem; }
    .review-card h4 { margin: .27rem 0 .42rem; font-size: 1.03rem; }
    .review-card p { margin: .2rem 0; color: #516660; font-size: .86rem; line-height: 1.52; }
    .drug-card {
        border: 1px solid var(--line); border-radius: 14px; padding: .73rem .82rem;
        margin: .45rem 0; background: #fff;
    }
    .drug-card strong { display: block; color: var(--navy); margin-bottom: .2rem; }
    .drug-card .price { font-size: 1.18rem; color: var(--sage); font-weight: 760; }
    .drug-card small { color: #5c6d67; line-height: 1.4; }
    .badge-ok, .badge-no {
        border-radius: 100px; padding: .17rem .52rem; font-size: .77rem; font-weight: 760;
        display: inline-block; margin-right: .35rem;
    }
    .badge-ok { color: #23604e; background: #e0f1e7; }
    .badge-no { color: #a74741; background: #f6e5e2; }
    .smallprint { color: #64746e; font-size: .8rem; line-height: 1.5; }
    .stButton > button, .stDownloadButton > button { border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def uploaded_catalog(upload) -> tuple[Drug, ...] | None:
    if upload is None:
        return None
    try:
        frame = pd.read_csv(upload, dtype=str).fillna("")
        expected = {
            "product_name",
            "ingredient",
            "classes",
            "dose",
            "price_krw",
            "price_as_of",
            "source_note",
        }
        if not expected.issubset(frame.columns):
            st.error("업로드 파일 열 이름이 맞지 않습니다. 기본 카탈로그 파일 형식을 사용하세요.")
            return None
        drugs = []
        for row in frame.to_dict("records"):
            price = row["price_krw"].replace(",", "").strip()
            classes = tuple(code.strip() for code in row["classes"].split("+"))
            if any(code not in CLASS_INFO for code in classes):
                st.error(f"알 수 없는 성분군 코드가 있습니다: {row['product_name']}")
                return None
            drugs.append(
                Drug(
                    product_name=row["product_name"],
                    ingredient=row["ingredient"],
                    classes=classes,
                    dose=row["dose"],
                    price_krw=int(price) if price else None,
                    price_as_of=row["price_as_of"],
                    source_note=row["source_note"],
                )
            )
        return tuple(drugs)
    except Exception as exc:
        st.error(f"약가 파일을 읽을 수 없습니다: {exc}")
        return None


def builtin_catalog() -> tuple[Drug, ...]:
    frame = pd.read_csv(StringIO(DEFAULT_CATALOG_CSV), dtype=str).fillna("")
    drugs = []
    for row in frame.to_dict("records"):
        price = row["price_krw"].replace(",", "").strip()
        drugs.append(
            Drug(
                product_name=row["product_name"],
                ingredient=row["ingredient"],
                classes=tuple(code.strip() for code in row["classes"].split("+")),
                dose=row["dose"],
                price_krw=int(price) if price else None,
                price_as_of=row["price_as_of"],
                source_note=row["source_note"],
            )
        )
    return tuple(drugs)


def startup_catalog() -> tuple[Drug, ...]:
    if CATALOG_PATH.exists():
        return load_catalog(CATALOG_PATH)
    if ROOT_CATALOG_PATH.exists():
        st.info("최상위의 `drug_catalog.csv` 파일을 불러왔습니다. 권장 위치는 `data/drug_catalog.csv`입니다.")
        return load_catalog(ROOT_CATALOG_PATH)
    st.info(
        "`data/drug_catalog.csv` 또는 `drug_catalog.csv` 파일을 찾지 못해 앱에 포함된 "
        "기본 제품 목록으로 실행합니다. GitHub의 파일 경로와 파일명(대소문자 포함)을 확인하세요."
    )
    return builtin_catalog()


def render_matrix(selected_classes: tuple[str, ...]) -> None:
    labels = [CLASS_INFO[code][0] for code in CLASS_ORDER]
    values = []
    for row in CLASS_ORDER:
        values.append([matrix_status(row, column) for column in CLASS_ORDER])
    frame = pd.DataFrame(values, index=labels, columns=labels)
    selected = set(selected_classes)

    def paint(value: str, row_idx: int, col_idx: int) -> str:
        row_code = CLASS_ORDER[row_idx]
        col_code = CLASS_ORDER[col_idx]
        active = row_code in selected and col_code in selected and row_code != col_code
        if active and value == "O":
            return "background-color:#27805e;color:white;font-weight:800;"
        if active and value == "X":
            return "background-color:#cf5f54;color:white;font-weight:800;"
        if row_code in selected and col_code == row_code:
            return "background-color:#eadbbf;font-weight:800;"
        if value == "O":
            return "color:#326957;background-color:#f2f7f3;"
        if value == "X":
            return "color:#b1584e;background-color:#fdf7f5;"
        return "color:#a0a7a0;background-color:#f4f3ef;"

    styled = frame.style.apply(
        lambda row: [
            paint(value, labels.index(row.name), col_idx) for col_idx, value in enumerate(row)
        ],
        axis=1,
    )
    styled = styled.set_properties(**{"text-align": "center", "font-size": "14px"})
    st.dataframe(styled, width="stretch", height=438)


def render_review_card(review) -> None:
    css = "ok" if review.status == "조합 가능" else "no" if review.status == "조합 불가" else "wait"
    body = "".join(f"<p>{escape(message)}</p>" for message in (*review.basis, *review.conditions))
    st.markdown(
        f'<div class="review-card {css}"><span class="state">{escape(review.status)}</span>'
        f"<h4>{escape(review.title)}</h4>{body}</div>",
        unsafe_allow_html=True,
    )


def render_drug_card(drug: Drug) -> None:
    price = f"{drug.price_krw:,}원 / 정" if drug.price_krw is not None else "금액 미등록"
    as_of = f"기준일 {drug.price_as_of}" if drug.price_as_of else "최신 공식 약가파일 확인 필요"
    st.markdown(
        f'<div class="drug-card"><strong>{escape(drug.product_name)}</strong>'
        f'<span class="price">{escape(price)}</span><br>'
        f'<small>{escape(drug.ingredient)} | {escape(drug.class_label)} | {escape(drug.dose)}<br>'
        f"{escape(as_of)}</small></div>",
        unsafe_allow_html=True,
    )


def clear_clinical_notes() -> None:
    st.session_state.pop("clinical_notes", None)


default_catalog = startup_catalog()
selected_names = st.session_state.get("selected_products", [])
catalog = st.session_state.get("active_catalog", default_catalog)
catalog_map = {drug.product_name: drug for drug in catalog}
selected_drugs = tuple(catalog_map[name] for name in selected_names if name in catalog_map)
selected_classes = unique_classes(selected_drugs)
review = evaluate_regimen(selected_classes)

st.markdown(
    f"""
    <div class="hero">
        <div>
            <div class="eyebrow">GLUCOCLAIM STUDIO</div>
            <h1>당뇨 약제 조합 심사 워크벤치</h1>
            <p>경구 성분군 병용표를 선택 조합에 맞춰 색으로 표시하고, 제품명·성분·상한금액과 급여 검토 근거를 한 화면에서 확인합니다.</p>
        </div>
        <div class="stamp"><b>{POLICY_REFERENCE}</b><br>적용일 {POLICY_EFFECTIVE_DATE}<br>{POLICY_TITLE}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.warning(
    "AI 전문가 검토는 고시 규칙을 구조화한 심사 보조 결과입니다. 처방, 급여 확정 또는 약가 청구 전에는 "
    "환자 진료기록, 제품별 허가사항, 적용일의 공식 약가파일을 반드시 대조하세요."
)

st.markdown('<div class="module">01 / 경구제 병용 가능 조합표</div>', unsafe_allow_html=True)
st.subheader("선택 조합 하이라이트 매트릭스")
st.markdown(
    '<div class="guide-note"><b>표 읽는 방법</b> · 녹색 = 선택한 허용 조합(O) · 적색 = 선택한 불가 조합(X) · '
    "3제 예외 조합은 아래 AI 검토 카드에서 별도로 인정 근거를 표시합니다.</div>",
    unsafe_allow_html=True,
)
render_matrix(selected_classes)

left, right = st.columns([1.02, 0.98], gap="large")

with right:
    st.markdown('<div class="module">02 / 제품 검색 및 금액</div>', unsafe_allow_html=True)
    st.subheader("약제 선택")
    st.caption("제품명을 입력하여 검색한 뒤 최대 3개 경구 성분군의 급여 조합을 검토합니다.")
    picked_names = st.multiselect(
        "제품명 검색",
        [drug.product_name for drug in catalog],
        key="selected_products",
        placeholder="예: 다이아벡스, 제미글로, 포시리진",
        on_change=clear_clinical_notes,
    )
    if len(picked_names) > 3:
        st.warning("제품은 선택할 수 있으나 자동 급여 판정은 경구 성분군 3제까지 제공합니다.")
    picked = tuple(catalog_map[name] for name in picked_names)
    if picked:
        st.markdown("##### 선택 제품 상세")
        for drug in picked:
            render_drug_card(drug)
        priced_total = sum(drug.price_krw or 0 for drug in picked)
        all_priced = all(drug.price_krw is not None for drug in picked)
        if all_priced:
            st.metric("선택 제품 1일 1정 기준 상한금액 합계", f"{priced_total:,}원")
        else:
            st.caption("금액이 미등록된 제품이 포함되어 합계는 표시하지 않습니다.")
    else:
        st.info("제품을 선택하면 성분, 성분군, 상한금액이 표시되고 상단 표가 함께 강조됩니다.")

    with st.expander("약가 데이터 업데이트"):
        st.write("공식 약가파일을 정리한 CSV를 업로드하면 제품명 검색 및 금액 표시 데이터가 교체됩니다.")
        price_upload = st.file_uploader("CSV 업로드", type="csv", key="price_upload")
        replacement = uploaded_catalog(price_upload)
        if replacement:
            st.session_state["active_catalog"] = replacement
            st.success(f"{len(replacement)}개 제품의 업로드 데이터를 사용합니다. 제품 선택을 다시 확인하세요.")
        st.download_button(
            "CSV 형식 예시 다운로드",
            data=CATALOG_PATH.read_bytes() if CATALOG_PATH.exists() else DEFAULT_CATALOG_CSV.encode("utf-8-sig"),
            file_name="diabetes_drug_catalog_template.csv",
            mime="text/csv",
        )

with left:
    st.markdown('<div class="module">03 / 조합 분석 및 심사 의견</div>', unsafe_allow_html=True)
    st.subheader("조합 가능성 검토")
    render_review_card(review)

    with st.form("review_inputs"):
        st.markdown("##### 임상·청구 조건 입력")
        input_a, input_b = st.columns(2)
        with input_a:
            hba1c = st.number_input("현재 HbA1c (%)", min_value=0.0, max_value=20.0, value=7.0, step=0.1)
        with input_b:
            previous_months = st.number_input("종전 요법 투여기간 (개월)", min_value=0, max_value=60, value=2)
        metformin_unusable = st.checkbox("Metformin 금기 또는 부작용으로 사용 불가")
        consult = st.form_submit_button("AI 전문가 검토 생성", type="primary", width="stretch")
    if consult:
        st.session_state["clinical_notes"] = clinical_review(
            review, float(hba1c), int(previous_months), metformin_unusable
        )
    if st.session_state.get("clinical_notes"):
        st.markdown("##### AI 전문가 검토 의견")
        for note in st.session_state["clinical_notes"]:
            st.write(f"- {note}")

    additions = candidate_additions(selected_classes)
    allowed = [(code, item) for code, item in additions if item.status == "조합 가능"]
    blocked = [(code, item) for code, item in additions if item.status == "조합 불가"]
    allowed_tab, blocked_tab = st.tabs(["추가 가능한 성분군", "불가능 조합"])
    with allowed_tab:
        if not selected_classes:
            st.caption("제품을 먼저 선택하면 추가 가능 성분군을 안내합니다.")
        for code, item in allowed:
            st.markdown(
                f'<span class="badge-ok">가능</span><b>{escape(CLASS_INFO[code][1])}</b> '
                f'<span class="smallprint">({escape(CLASS_INFO[code][0])})</span>',
                unsafe_allow_html=True,
            )
    with blocked_tab:
        if not selected_classes:
            st.caption("제품을 먼저 선택하면 불가 조합을 안내합니다.")
        for code, item in blocked:
            st.markdown(
                f'<span class="badge-no">불가</span><b>{escape(CLASS_INFO[code][1])}</b> '
                f'<span class="smallprint">({escape(CLASS_INFO[code][0])})</span>',
                unsafe_allow_html=True,
            )

st.divider()
foot_a, foot_b = st.columns([1.05, 0.95])
with foot_a:
    st.markdown("##### 실무 확인사항")
    st.write(
        "- 2제·3제 조합의 구조가 가능하더라도 HbA1c, 기존 투여기간, Metformin 사용 가능 여부를 기록에서 확인합니다.\n"
        "- 동일 성분 복합제와 단일제를 병용할 경우 용량 한도와 중복 성분을 확인합니다.\n"
        "- 인슐린 및 GLP-1 수용체작용제 조합은 경구제 매트릭스와 분리하여 원문 기준을 확인합니다."
    )
with foot_b:
    st.markdown("##### 공식 근거")
    st.write(f"{POLICY_REFERENCE} | 시행일 {POLICY_EFFECTIVE_DATE}")
    st.link_button("심평원 고시 안내 원문 열기", POLICY_URL)
    st.markdown(
        '<p class="smallprint">기본 카탈로그에서 금액이 표시된 일부 제품은 공개 약제정보 확인값으로 포함했으며, '
        "운영 배포 시 반드시 적용일의 공식 약가파일로 교체·검증해야 합니다.</p>",
        unsafe_allow_html=True,
    )
