GROSS_INCOME_BY_PERCENTILE = {
    # data from levels.fyi
    "10th": 48_100,
    "25th": 66_000,
    "50th": 98_500,
    "75th": 145_000,
    "90th": 210_000,
}

EXPENSES_BREAKDOWN = {
    # london
    # adjusted from numbeo.com: single, central 1bedroom
    "Housing": 2776.95,
    "Utilities": 263.93,
    "Groceries": 286.88,
    "Transportation": 218.03,
    "Subscriptions": 57.38,
    "Discretionary": 114.75,
    "Miscellaneous": 68.85,
}

ANNUAL_EXPENSES = sum(EXPENSES_BREAKDOWN.values()) * 12


#
# income tax
#


from currency_converter import CurrencyConverter


def progressive_charge(amount: float, bands) -> float:
    total = 0.0
    remaining = max(amount, 0.0)
    for width, rate in bands:
        if remaining <= 0:
            break
        taxable = remaining if width is None else min(remaining, width)
        total += taxable * rate
        remaining -= taxable
    return total


def net_salary(
    gross_annual_salary: int,
    input_currency: str = "EUR",
    output_currency: str = "EUR",
) -> int:
    # based on:
    # https://www.gov.uk/estimate-income-tax
    # https://github.com/hmrc/income-tax-calculation/
    converter = CurrencyConverter()
    if input_currency.upper() == "EUR":
        gross_annual_salary = converter.convert(gross_annual_salary, "EUR", "GBP")

    PERSONAL_ALLOWANCE = 12570.0
    TAPER_START = 100000.0
    TAPER_RATE = 0.50
    TAX_BANDS = ((37700.0, 0.20), (87440.0, 0.40), (None, 0.45))
    NATIONAL_INSURANCE_BANDS = ((12570.0, 0.00), (37700.0, 0.08), (None, 0.02))

    allowance = PERSONAL_ALLOWANCE
    if gross_annual_salary > TAPER_START:
        allowance -= (gross_annual_salary - TAPER_START) * TAPER_RATE
        allowance = max(allowance, 0.0)
    taxable = max(gross_annual_salary - allowance, 0.0)
    tax = round(progressive_charge(taxable, TAX_BANDS))
    national_insurance = round(progressive_charge(gross_annual_salary, NATIONAL_INSURANCE_BANDS))
    net = round(gross_annual_salary - tax - national_insurance)

    if output_currency.upper() == "EUR":
        return int(converter.convert(net, "GBP", "EUR"))
    return int(round(net))
