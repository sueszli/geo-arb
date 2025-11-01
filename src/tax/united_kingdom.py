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
