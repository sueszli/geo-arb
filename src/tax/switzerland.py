import csv
import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Tuple

from currency_converter import CurrencyConverter
from numpy import clip

#
# csv data retrieval and parsing
# see: https://swisstaxcalculator.estv.admin.ch/#/taxburden/income-wealth-tax
#

BASE_DIR = Path(__file__).resolve().parent
MULTIPLIERS_PATH = BASE_DIR / "switzerland-estv-income-rates.csv"
SCALES_PATH = BASE_DIR / "switzerland-estv-scales.csv"


@lru_cache(maxsize=None)
def _multipliers() -> Dict[str, Dict[str, object]]:
    result: Dict[str, Dict[str, object]] = {}
    with MULTIPLIERS_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)  # drop header
        for row in reader:
            canton_code = row[1].strip()
            commune_name = row[3].strip()

            percent = lambda value: float(value) / 100.0 if value else 0.0

            canton_multiplier = percent(row[4])
            commune_multiplier = percent(row[5])
            protestant_multiplier = percent(row[6])
            roman_multiplier = percent(row[7])
            christian_multiplier = percent(row[8])

            canton_entry = result.setdefault(
                canton_code,
                {
                    "canton_multiplier": canton_multiplier,
                    "communes": {},
                },
            )
            canton_entry["canton_multiplier"] = canton_multiplier

            commune_record = {
                "name": commune_name,
                "commune_multiplier": commune_multiplier,
                "church_multipliers": {
                    "protestant": protestant_multiplier,
                    "roman catholic": roman_multiplier,
                    "christian catholic": christian_multiplier,
                },
            }

            canton_entry["communes"][commune_name.strip().casefold()] = commune_record
    assert result, "empty multiplier csv"
    return result


@lru_cache(maxsize=None)
def _tax_scales() -> Tuple[Dict[str, Tuple[str, Iterable]], Dict[Tuple[str, str], Tuple[str, Iterable]]]:
    federal_entries = defaultdict(list)
    canton_entries: Dict[Tuple[str, str], Dict[str, Iterable]] = {}

    def parse_row(row: Dict[str, str]) -> None:
        authority = row["Tax authority"]
        if authority not in {"Federal tax", "Canton"}:
            return

        entity = row["Taxable entity"]
        canton = row["Canton"]
        additional = row["Additional %"].strip()
        base_amount = row["Base amount CHF"].strip()
        threshold = row["Taxable income for federal tax"].strip()
        next_amount = row["For the next CHF"].strip()
        tax_rate = row["Tax rate"].strip()

        as_percent = lambda value: float(value) / 100.0 if value else 0.0
        as_float = lambda value: float(value) if value else 0.0

        if authority == "Federal tax" and canton == "Confederation":
            federal_entries[entity].append((float(threshold or 0.0), as_float(base_amount), as_percent(additional)))
            return

        key = (canton, entity)
        bucket = canton_entries.setdefault(key, {"type": None, "rows": []})

        if next_amount:
            portion = float("inf") if float(next_amount) >= 99_999_999 else float(next_amount)
            bucket["type"] = "step"
            bucket["rows"].append((portion, as_percent(additional)))
            return

        if tax_rate:
            bucket["type"] = "flat"
            bucket["rows"] = [(as_percent(tax_rate), as_float(base_amount))]
            return

        if threshold:
            bucket["type"] = "threshold"
            bucket["rows"].append((float(threshold), as_float(base_amount), as_percent(additional)))

    with SCALES_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            parse_row(row)

    assert federal_entries, "missing federal scales"

    federal_scales = {entity: ("threshold", tuple(sorted(rows, key=lambda item: item[0]))) for entity, rows in federal_entries.items()}

    canton_scales = {}
    for key, payload in canton_entries.items():
        kind = payload["type"] or "flat"
        rows = payload["rows"]
        if kind == "threshold":
            rows.sort(key=lambda item: item[0])
            canton_scales[key] = (kind, tuple(rows))
            continue
        canton_scales[key] = (kind, rows[0] if kind == "flat" else tuple(rows))

    return federal_scales, canton_scales


CANTON_CAPITALS: Dict[str, str] = {
    "AG": "Aarau",
    "AI": "Appenzell",
    "AR": "Herisau",
    "BE": "Bern",
    "BL": "Liestal",
    "BS": "Basel",
    "FR": "Fribourg",
    "GE": "Genève",
    "GL": "Glarus",
    "GR": "Chur",
    "JU": "Delémont",
    "LU": "Luzern",
    "NE": "Neuchâtel",
    "NW": "Stans",
    "OW": "Sarnen",
    "SG": "St. Gallen",
    "SH": "Schaffhausen",
    "SO": "Solothurn",
    "SZ": "Schwyz",
    "TG": "Frauenfeld",
    "TI": "Bellinzona",
    "UR": "Altdorf",
    "VD": "Lausanne",
    "VS": "Sion",
    "ZG": "Zug",
    "ZH": "Zürich",
}

CANTON_NAME_ALIASES: Dict[str, Tuple[str, ...]] = {
    "ZH": ("Zurich", "Zuerich"),
    "BE": ("Bern",),
    "LU": ("Lucerne",),
    "UR": ("Uri",),
    "SZ": ("Schwyz",),
    "OW": ("Obwalden",),
    "NW": ("Nidwalden",),
    "GL": ("Glarus",),
    "ZG": ("Zug",),
    "FR": ("Fribourg",),
    "SO": ("Solothurn",),
    "BS": ("Basel Stadt",),
    "BL": ("Basel Landschaft",),
    "SH": ("Schaffhausen",),
    "AR": ("Appenzell Ausserrhoden",),
    "AI": ("Appenzell Innerrhoden",),
    "SG": ("Saint Gallen", "St Gallen"),
    "GR": ("Graubunden", "Graubuenden", "Grisons"),
    "AG": ("Aargau",),
    "TG": ("Thurgau",),
    "TI": ("Ticino",),
    "VD": ("Vaud",),
    "VS": ("Valais",),
    "NE": ("Neuchatel",),
    "GE": ("Geneva",),
    "JU": ("Jura",),
}


def _resolve_canton_code(raw_canton: str, multipliers: Dict[str, Dict[str, object]]) -> str:
    # resolve user input to a canton code
    candidate = raw_canton.strip().upper()
    if candidate in multipliers:
        return candidate

    alias_map = {name.strip().casefold(): code for code, capital in CANTON_CAPITALS.items() for name in {code, capital, *CANTON_NAME_ALIASES.get(code, ())}}
    code = alias_map.get(raw_canton.strip().casefold())
    assert code, "unknown canton"
    assert code in multipliers, "missing canton multipliers"
    return code


def _select_commune_entry(
    canton_code: str,
    requested_commune: str | None,
    multipliers: Dict[str, Dict[str, object]],
) -> Dict[str, object]:
    # pick the commune record matching request or defaults
    commune_map = multipliers[canton_code]["communes"]
    assert commune_map, "missing commune data"

    if requested_commune:
        lookup = requested_commune.strip().casefold()
        assert lookup in commune_map, "unknown commune"
        return commune_map[lookup]

    capital = CANTON_CAPITALS.get(canton_code)
    if capital:
        capital_key = capital.strip().casefold()
        if capital_key in commune_map:
            return commune_map[capital_key]

    return next(iter(commune_map.values()))


def _find_canton_scale(
    canton_code: str,
    canton_scales: Dict[Tuple[str, str], Tuple[str, Iterable]],
) -> Tuple[str, Iterable]:
    # choose best matching canton scale for entity
    preferred_entities = ["Single, no children", "Single, with / no children", "Single", "All"]
    for candidate in preferred_entities:
        key = (canton_code, candidate)
        if key in canton_scales:
            return canton_scales[key]
    assert False


#
# tax calculation logic
#


def _apply_tax_scale(scale: Tuple[str, Iterable], amount: float) -> float:
    # route amount through the configured scale kind
    # a) stepwise tax across bracket portions
    # b) threshold table entries
    # c) flat tax from rate and base

    if amount <= 0:
        return 0.0

    def _step_tax(amount: float, brackets: Iterable[Tuple[float, float]]) -> float:
        remaining = amount
        tax = 0.0
        for portion, rate in brackets:
            if remaining <= 0:
                break
            take = remaining if math.isinf(portion) else min(remaining, portion)
            tax += take * rate
            remaining -= take
        return tax

    def _threshold_tax(amount: float, entries: Iterable[Tuple[float, float, float]]) -> float:
        tax = 0.0
        for index, (threshold, base, rate) in enumerate(entries):
            if amount < threshold:
                break
            next_threshold = entries[index + 1][0] if index + 1 < len(entries) else float("inf")
            taxable_segment = min(amount, next_threshold) - threshold
            tax = base + taxable_segment * rate
            if amount <= next_threshold:
                break
        return tax

    def _flat_tax(amount: float, params: Tuple[float, float]) -> float:
        rate, base = params
        return amount * rate + base

    kind, data = scale
    calculators = {
        "step": lambda rows: _step_tax(amount, rows),
        "threshold": lambda rows: _threshold_tax(amount, rows),
        "flat": lambda params: _flat_tax(amount, params),
    }
    handler = calculators.get(kind)
    assert handler, "unsupported scale"

    if kind == "flat" and isinstance(data, (list, tuple)) and data and isinstance(data[0], tuple):
        data = data[0]
    return handler(data)


def _compute_social_contributions(gross_income: float, age: int) -> Tuple[float, float, float, float]:
    # estimate swiss employee social contributions
    capped = min(gross_income, 148_200)
    oasi = round(gross_income * 0.053)
    unemployment = round(capped * 0.011)
    accident = round(capped * 0.004)

    if gross_income <= 21_510:
        return oasi, unemployment, accident, 0.0

    coord_lower, coord_upper, coordination_deduction = 3_585, 60_945, 25_095
    insured_salary = clip(max(0.0, gross_income - coordination_deduction), coord_lower, coord_upper)
    extra_salary = max(0.0, gross_income - (coordination_deduction + coord_upper))

    age_brackets = ((55, 0.09), (45, 0.075), (35, 0.05), (25, 0.035))
    rate = next((value for threshold, value in age_brackets if age >= threshold), 0.0)

    extra_transition = 3_966.0
    extra_first = min(extra_salary, extra_transition)
    extra_rest = max(0.0, extra_salary - extra_transition)
    pension = round(insured_salary * rate + extra_first * 0.023 + extra_rest * rate)

    return oasi, unemployment, accident, pension


def net_salary(
    gross_annual_salary: int,
    canton: str = "ZH",
    commune: str | None = None,
    age: int = 30,
    input_currency: str = "EUR",
    output_currency: str = "EUR",
    other_deductions: float = 0.0,
) -> int:
    # assume single, atheist, no children unless
    # based on: https://swisstaxcalculator.estv.admin.ch/#/calculator/income-wealth-tax
    converter = CurrencyConverter()
    if input_currency.upper() == "EUR":
        gross_annual_salary = converter.convert(gross_annual_salary, "EUR", "CHF")

    multipliers = _multipliers()
    assert canton in multipliers, "invalid canton"
    assert (not commune) or commune.strip().casefold() in multipliers[canton]["communes"], "invalid commune"
    canton_code = _resolve_canton_code(canton, multipliers)
    commune_entry = _select_commune_entry(canton_code, commune, multipliers)

    federal_scales, canton_scales = _tax_scales()
    canton_scale = _find_canton_scale(canton_code, canton_scales)

    oasi, unemployment, accident, pension = _compute_social_contributions(gross_annual_salary, age)
    social_total = sum((oasi, unemployment, accident, pension))

    net_income_after_social = gross_annual_salary - social_total

    min_professional, max_professional = 2_000.0, 4_000.0
    other_professional = clip(math.floor(net_income_after_social * 0.03), min_professional, max_professional)
    insurance_canton = 2_900.0
    insurance_federal = 1_800.0

    deduction_pool = max(0.0, other_deductions)
    taxable_income_canton = max(0.0, net_income_after_social - other_professional - insurance_canton - deduction_pool)
    taxable_income_federal = max(0.0, net_income_after_social - other_professional - insurance_federal - deduction_pool)

    federal_tax_raw = _apply_tax_scale(federal_scales.get("Single, no children"), taxable_income_federal)
    canton_base_tax = _apply_tax_scale(canton_scale, taxable_income_canton)

    canton_multiplier = multipliers[canton_code]["canton_multiplier"]
    commune_multiplier = commune_entry["commune_multiplier"]

    base_tax_int = math.floor(canton_base_tax)
    cantonal_tax = round(base_tax_int * canton_multiplier)
    communal_tax = round(base_tax_int * commune_multiplier)
    federal_tax = math.floor(federal_tax_raw + 0.004)

    personal_tax = 24.0  # small constant, dropped detailed calculation per canton
    total_tax = federal_tax + cantonal_tax + communal_tax + personal_tax
    net_income = gross_annual_salary - social_total - total_tax

    if output_currency.upper() == "EUR":
        return int(converter.convert(net_income, "CHF", "EUR"))
    return int(net_income)
