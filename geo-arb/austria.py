GROSS_INCOME_BY_PERCENTILE = {
    # data from levels.fyi
    "10th": 28_600,
    "25th": 43_000,
    "50th": 58_300,
    "75th": 74_100,
    "90th": 91_300,
}

EXPENSES_BREAKDOWN = {
    # vienna
    # adjusted from numbeo.com: single, central 1bedroom
    "Housing": 800.00,
    "Utilities": 150.00,
    "Groceries": 280.00,
    "Transportation": 40.00,
    "Subscriptions": 40.00,
    "Discretionary": 70.00,
    "Miscellaneous": 50.00,
}

ANNUAL_EXPENSES = sum(EXPENSES_BREAKDOWN.values()) * 12


#
# income tax
#


def _net_special(gross_special_payments: int) -> float:
    gross = float(gross_special_payments)

    # social insurance
    sv_base = min(gross, 12900.00)  # höchstbeitragsgrundlage sonderzahlungen, ASVG §108
    social_insurance = round(sv_base * 0.1707, 2)  # spacial payments rate

    # income tax
    taxable_base = gross - social_insurance
    tax_free_amount = 620.00 * 2  # first 620 EUR of both payments are tax-free, EStG §67 (1) greibetrag
    taxed_amount = max(0.00, taxable_base - tax_free_amount)
    income_tax = round(taxed_amount * 0.06, 2)  # sechstel-tarif EStG §67 (1)

    net_salary = gross - social_insurance - income_tax

    return round(net_salary, 2)


def _tax_monthly(taxable_income: float) -> float:
    tax_brackets = [
        (1037.33, 0.00),
        (1620.67, 0.20),
        (2704.00, 0.30),
        (5173.33, 0.40),
        (7760.00, 0.48),
        (float("inf"), 0.50),
    ]

    if taxable_income <= tax_brackets[0][0]:
        return 0.00

    income_tax = 0.00
    previous_limit = 0.00

    # progressive tax brackets, einkommensteuertarif, EStG § 33
    for limit, rate in tax_brackets:
        if taxable_income > previous_limit:
            taxable_in_bracket = min(taxable_income, limit) - previous_limit
            income_tax += taxable_in_bracket * rate
            previous_limit = limit

            if taxable_income <= limit:
                break

    # estimated tax deductibles, arbeitnehmerabsetzbetrag/berkehrsabsetzbetrag, EStG § 33
    income_tax = max(0.00, income_tax - 104.63)
    return round(income_tax, 2)


def _net_running(gross_salary_monthly: int) -> float:
    gross = float(gross_salary_monthly)

    # social insurance
    sv_base = min(gross, 6090.00)  # höchstbeitragsgrundlage, ASVG §108
    social_insurance = round(sv_base * 0.1812, 2)  # standard rate

    # income tax
    taxable_income = gross - social_insurance
    income_tax = _tax_monthly(taxable_income)
    net_salary = gross - social_insurance - income_tax

    return round(net_salary, 2)


def net_salary(annual_gross_salary: int) -> int:
    # based on: https://bruttonetto.arbeiterkammer.at/
    if annual_gross_salary <= 0:
        return 0

    # 12x running payments
    gross_monthly_running = annual_gross_salary / 14
    net_monthly = _net_running(int(gross_monthly_running))

    # 2x special payments (13th/14th)
    gross_special_payments = 2 * gross_monthly_running
    net_special = _net_special(int(gross_special_payments))

    return int(12 * net_monthly + net_special)
