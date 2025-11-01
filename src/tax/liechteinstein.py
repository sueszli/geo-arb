from currency_converter import CurrencyConverter


def _national_tax(income: float) -> float:
    brackets = [
        (0, 15855, 0.00, 0),
        (15856, 21140, 0.01, 159),
        (21141, 42280, 0.03, 581),
        (42281, 73990, 0.04, 1004),
        (73991, 105700, 0.05, 1744),
        (105701, 137410, 0.06, 2801),
        (137411, 169120, 0.065, 3488),
        (169121, 211400, 0.07, 4334),
        (211401, float("inf"), 0.08, 6448),
    ]
    for low, high, rate, offset in brackets:
        if income <= high:
            tax = income * rate - offset
            return max(tax, 0)
    return 0.0


def net_salary(
    gross_annual_salary: float,
    input_currency: str = "EUR",
    output_currency: str = "EUR",
) -> float:
    # not reliable, not much data available
    # based on: https://www.gesetze.li/konso/2010340000 (Art. 19 SteG)
    converter = CurrencyConverter()
    if input_currency.upper() == "EUR":
        gross_annual_salary = converter.convert(gross_annual_salary, "EUR", "CHF")

    # social insurance (employee share)
    ahv_iv = gross_annual_salary * 0.047  # 4.025 + 0.675
    alv = min(gross_annual_salary, 126000) * 0.005
    social_security = ahv_iv + alv

    # employee share of basic health insurance
    health_insurance = 1920.0

    # taxable income after personal allowance
    taxable_income = max(0, gross_annual_salary - 15855)

    # national + Vaduz municipal (150% surcharge)
    national_tax = _national_tax(taxable_income)
    total_income_tax = national_tax * 2.5

    net = gross_annual_salary - social_security - health_insurance - total_income_tax

    if output_currency.upper() == "EUR":
        return int(converter.convert(net, "CHF", "EUR"))
    return round(net, 2)
