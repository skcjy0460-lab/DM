"""Coverage-oriented review engine for Korean type 2 diabetes medications.

This module is intentionally deterministic. It translates the oral combination
matrix and review conditions into auditable messages; it does not make a
patient-specific prescribing decision.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable


POLICY_EFFECTIVE_DATE = "2026-05-01"
POLICY_TITLE = "[일반원칙] 당뇨병용제"
POLICY_REFERENCE = "보건복지부 고시 제2026-92호(약제)"
POLICY_URL = (
    "https://www.hira.or.kr/rc/drug/insuadtcrtr/bbsView.do?"
    "brdBltNo=53126&brdScnBltNo=4&pgmid=HIRAA030069000400"
)

CLASS_ORDER = (
    "MET",
    "SU",
    "MEG",
    "AGI",
    "TZD",
    "DPP4",
    "SGLT2_DA",
    "SGLT2_IP",
    "SGLT2_EM",
    "SGLT2_ER",
    "SGLT2_EN",
)
CLASS_INFO = {
    "MET": ("MET", "Biguanide / Metformin"),
    "SU": ("SU", "Sulfonylurea"),
    "MEG": ("Meg", "Meglitinide"),
    "AGI": ("alpha-GI", "alpha-glucosidase inhibitor"),
    "TZD": ("TZD", "Thiazolidinedione"),
    "DPP4": ("DPP-4i", "DPP-IV inhibitor"),
    "SGLT2_DA": ("SGLT-2 da", "Dapagliflozin"),
    "SGLT2_IP": ("SGLT-2 ip", "Ipragliflozin"),
    "SGLT2_EM": ("SGLT-2 em", "Empagliflozin"),
    "SGLT2_ER": ("SGLT-2 er", "Ertugliflozin"),
    "SGLT2_EN": ("SGLT-2 en", "Enavogliflozin"),
}

# Two-drug reimbursement matrix represented by approved unordered class pairs.
ALLOWED_PAIRS = {
    frozenset(("MET", "SU")),
    frozenset(("MET", "MEG")),
    frozenset(("MET", "AGI")),
    frozenset(("MET", "TZD")),
    frozenset(("MET", "DPP4")),
    frozenset(("MET", "SGLT2_DA")),
    frozenset(("MET", "SGLT2_IP")),
    frozenset(("MET", "SGLT2_EM")),
    frozenset(("MET", "SGLT2_ER")),
    frozenset(("MET", "SGLT2_EN")),
    frozenset(("SU", "AGI")),
    frozenset(("SU", "TZD")),
    frozenset(("SU", "DPP4")),
    frozenset(("SU", "SGLT2_DA")),
    frozenset(("SU", "SGLT2_IP")),
    frozenset(("SU", "SGLT2_EM")),
    frozenset(("SU", "SGLT2_ER")),
    frozenset(("MEG", "AGI")),
    frozenset(("MEG", "TZD")),
    frozenset(("TZD", "DPP4")),
}

# Three-drug exceptions permitted even though one of their two-drug pairs is X.
EXCEPTION_TRIPLES = {
    frozenset(("MET", "DPP4", "SGLT2_DA")),
    frozenset(("MET", "DPP4", "SGLT2_IP")),
    frozenset(("MET", "DPP4", "SGLT2_EM")),
    frozenset(("MET", "DPP4", "SGLT2_ER")),
    frozenset(("MET", "DPP4", "SGLT2_EN")),
    frozenset(("MET", "TZD", "SGLT2_DA")),
    frozenset(("MET", "TZD", "SGLT2_IP")),
    frozenset(("MET", "TZD", "SGLT2_EM")),
}


@dataclass(frozen=True)
class Drug:
    product_name: str
    ingredient: str
    classes: tuple[str, ...]
    dose: str
    price_krw: int | None
    price_as_of: str
    source_note: str

    @property
    def class_label(self) -> str:
        return " + ".join(CLASS_INFO[item][0] for item in self.classes)


@dataclass(frozen=True)
class RegimenReview:
    status: str
    classes: tuple[str, ...]
    title: str
    basis: tuple[str, ...]
    conditions: tuple[str, ...]
    prohibited_pairs: tuple[tuple[str, str], ...]


def load_catalog(file_path: str | Path) -> tuple[Drug, ...]:
    with Path(file_path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        drugs = []
        for row in rows:
            price_text = row.get("price_krw", "").strip()
            drugs.append(
                Drug(
                    product_name=row["product_name"].strip(),
                    ingredient=row["ingredient"].strip(),
                    classes=tuple(part.strip() for part in row["classes"].split("+")),
                    dose=row["dose"].strip(),
                    price_krw=int(price_text) if price_text else None,
                    price_as_of=row.get("price_as_of", "").strip(),
                    source_note=row.get("source_note", "").strip(),
                )
            )
    return tuple(drugs)


def unique_classes(drugs: Iterable[Drug]) -> tuple[str, ...]:
    classes: list[str] = []
    for drug in drugs:
        for code in drug.classes:
            if code not in classes:
                classes.append(code)
    return tuple(sorted(classes, key=CLASS_ORDER.index))


def matrix_status(first: str, second: str) -> str:
    if first == second:
        return "-"
    return "O" if frozenset((first, second)) in ALLOWED_PAIRS else "X"


def _names(classes: Iterable[str]) -> str:
    return " + ".join(CLASS_INFO[code][0] for code in classes)


def evaluate_regimen(classes: Iterable[str]) -> RegimenReview:
    selected = tuple(sorted(set(classes), key=CLASS_ORDER.index))
    if not selected:
        return RegimenReview("선택 대기", (), "성분군을 선택하세요.", (), (), ())
    if len(selected) == 1:
        return RegimenReview(
            "단일제",
            selected,
            f"{_names(selected)} 단일 성분군",
            ("단일요법은 진단 수치 및 Metformin 사용 가능 여부 확인이 필요합니다.",),
            ("제품 허가사항과 급여대상 수치를 확인하세요.",),
            (),
        )
    invalid_pairs = tuple(
        pair for pair in combinations(selected, 2) if matrix_status(pair[0], pair[1]) == "X"
    )
    if len(selected) == 2:
        if invalid_pairs:
            return RegimenReview(
                "조합 불가",
                selected,
                f"{_names(selected)} 2제 조합",
                ("급여 인정 2제 병용 매트릭스에서 해당 교차 칸이 X입니다.",),
                ("허가사항 범위 내 사용이더라도 해당 일반원칙 외에는 약값 전액 환자 부담 여부를 검토하세요.",),
                invalid_pairs,
            )
        return RegimenReview(
            "조합 가능",
            selected,
            f"{_names(selected)} 2제 조합",
            ("급여 인정 2제 병용 매트릭스의 허용 조합(O)에 해당합니다.",),
            (
                "단독요법을 2-4개월 이상 투약 후 HbA1c >= 7.0%, 공복혈당 >= 130mg/dL 또는 식후혈당 >= 180mg/dL 여부를 확인합니다.",
                "HbA1c >= 7.5%인 경우 Metformin 포함 2제요법을 처음부터 인정할 수 있습니다.",
            ),
            (),
        )
    if len(selected) == 3:
        selected_set = frozenset(selected)
        if not invalid_pairs:
            reason = "2제요법에서 인정되는 조합만 포함한 3제 성분 구조입니다."
        elif selected_set in EXCEPTION_TRIPLES:
            reason = "2제 매트릭스에는 X가 있으나, 고시가 별도로 인정하는 3제 예외 조합입니다."
        else:
            return RegimenReview(
                "조합 불가",
                selected,
                f"{_names(selected)} 3제 조합",
                ("인정되지 않는 2제 조합을 포함하며, 고시에 열거된 3제 예외에도 해당하지 않습니다.",),
                ("다른 기전 성분으로 조정하거나 원문 고시를 재확인하세요.",),
                invalid_pairs,
            )
        return RegimenReview(
            "조합 가능",
            selected,
            f"{_names(selected)} 3제 조합",
            (reason,),
            ("2제요법을 2-4개월 이상 투여해도 HbA1c >= 7.0%인지 확인합니다.",),
            invalid_pairs,
        )
    return RegimenReview(
        "별도 검토",
        selected,
        f"{len(selected)}개 경구 성분군 조합",
        ("이 화면의 경구 급여 조합 자동판정 범위는 3제까지입니다.",),
        ("인슐린 또는 주사제 병용, 전액본인부담 여부를 원문 기준으로 별도 심사하세요.",),
        invalid_pairs,
    )


def candidate_additions(classes: Iterable[str]) -> tuple[tuple[str, RegimenReview], ...]:
    current = set(classes)
    candidates = []
    for candidate in CLASS_ORDER:
        if candidate in current:
            continue
        candidates.append((candidate, evaluate_regimen((*current, candidate))))
    return tuple(candidates)


def clinical_review(
    review: RegimenReview,
    hba1c: float | None,
    previous_months: int,
    metformin_unusable: bool,
) -> tuple[str, ...]:
    notes = [f"규칙형 판단: {review.status} - {review.title}."]
    if review.status == "조합 불가":
        notes.append("선택 조합은 급여 매트릭스상 자동 인정 조합으로 판정할 수 없습니다.")
        return tuple(notes)
    if len(review.classes) == 2:
        if hba1c is not None and hba1c >= 7.5 and "MET" in review.classes:
            notes.append("HbA1c가 7.5% 이상이고 MET 포함 2제이므로 초기 2제요법 인정 요건을 검토할 수 있습니다.")
        elif previous_months >= 2 and hba1c is not None and hba1c >= 7.0:
            notes.append("기존 치료기간과 HbA1c 입력값은 2제 추가요법 검토 문턱에 부합합니다.")
        else:
            notes.append("2제 급여 확정 전 기존 단독요법 2-4개월 및 혈당 기준 충족 기록을 확인하세요.")
    if len(review.classes) == 3:
        if previous_months >= 2 and hba1c is not None and hba1c >= 7.0:
            notes.append("2제요법 투여기간과 HbA1c 입력값은 3제 추가요법 검토 문턱에 부합합니다.")
        else:
            notes.append("3제 급여 검토에는 종전 2제요법 2-4개월 이상 및 HbA1c >= 7.0% 기록이 필요합니다.")
    if metformin_unusable and "MET" in review.classes:
        notes.append("Metformin 금기 또는 부작용을 표시했으나 조합에 MET가 포함되어 처방·청구 근거가 상충합니다.")
    elif metformin_unusable and "SU" in review.classes:
        notes.append("Metformin을 사용할 수 없는 경우 SU 포함 초기요법은 투여소견 첨부 여부를 확인하세요.")
    notes.append("최종 급여 판단은 제품별 허가사항, 최신 약가 목록 및 진료기록을 함께 확인해야 합니다.")
    return tuple(notes)
