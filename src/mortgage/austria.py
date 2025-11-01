TRANSFER_TAX_RATE = 0.035
NOTARY_RATE = 0.024  # 2% + 20% VAT ≈ 2.4%
AGENT_RATE = 0.036  # 3% + 20% VAT = 3.6%
BANK_PROCESSING_RATE = 0.03
LAND_REGISTRY_RATE = 0.011
MORTGAGE_REGISTRY_RATE = 0.012
FIXED_ADMIN_FEES = 81 + 47  # land registry admin + electronic lien fees
BASE_INTEREST_RATE = 0.034
MIN_DOWN_PAYMENT_RATIO = 0.20
STANDARD_TERM_YEARS = 25
ANNUAL_EXTRA_LIMIT_WITHOUT_PENALTY = 10000.0
NOTICE_MONTHS_FOR_PREPAY = 6
TYPICAL_PRICE_FOR_COSTS = 500000.0
TYPICAL_APARTMENT_SIZE_M2 = 80.0
RENT_PER_M2 = 21.0  # based on 2025 data, approx €21 per m² including costs


def _upfront_costs(purchase_price: float, mortgage_amount: float) -> float:
    # initial costs in addition to the minimum down payment

    def _land_registry_fee(purchase_price: float) -> float:
        if purchase_price <= 500000.0:
            return 0.0
        elif purchase_price <= 2000000.0:
            return (purchase_price - 500000.0) * LAND_REGISTRY_RATE
        else:
            return purchase_price * LAND_REGISTRY_RATE

    def _mortgage_registration_fee(mortgage_amount: float) -> float:
        if mortgage_amount <= 500000.0:
            return 0.0
        elif mortgage_amount <= 2000000.0:
            return (mortgage_amount - 500000.0) * MORTGAGE_REGISTRY_RATE
        else:
            return mortgage_amount * MORTGAGE_REGISTRY_RATE

    transfer_tax = TRANSFER_TAX_RATE * purchase_price
    land_reg = _land_registry_fee(purchase_price)
    mort_reg = _mortgage_registration_fee(mortgage_amount)
    notary = NOTARY_RATE * purchase_price
    agent = AGENT_RATE * purchase_price
    bank_processing = BANK_PROCESSING_RATE * mortgage_amount
    return transfer_tax + land_reg + mort_reg + notary + agent + bank_processing + FIXED_ADMIN_FEES


def _mortgage_amount(purchase_price: float, cash_savings: float) -> float:
    # how much we need to borrow
    if purchase_price <= 0 or cash_savings <= 0:
        return 0.0
    min_down = purchase_price * MIN_DOWN_PAYMENT_RATIO

    # Initial assumption for mortgage
    assumed_mortgage = purchase_price * (1 - MIN_DOWN_PAYMENT_RATIO)
    upfront = _upfront_costs(purchase_price, assumed_mortgage)
    available_down = cash_savings - upfront
    if available_down < min_down:
        raise ValueError("cash savings insufficient for minimum down payment and costs")
    mortgage = purchase_price - available_down

    # iterate once for better accuracy
    upfront = _upfront_costs(purchase_price, mortgage)
    available_down = cash_savings - upfront
    if available_down < min_down:
        raise ValueError("cash savings insufficient for minimum down payment and costs")
    mortgage = purchase_price - available_down

    return mortgage


def _interest_rate(down_payment_ratio: float) -> float:
    # interest rate is better with higher down payment
    if down_payment_ratio >= 0.40:
        return BASE_INTEREST_RATE - 0.005
    elif down_payment_ratio >= 0.30:
        return BASE_INTEREST_RATE - 0.0025
    elif down_payment_ratio >= 0.20:
        return BASE_INTEREST_RATE
    else:
        return BASE_INTEREST_RATE + 0.005


def _monthly_ownership_costs(purchase_price: float) -> float:
    # property maintenance, regardless of mortgage
    scale_factor = purchase_price / TYPICAL_PRICE_FOR_COSTS
    apartment_size = TYPICAL_APARTMENT_SIZE_M2 * scale_factor
    operating_costs = 4.0 * apartment_size  # €4/m² average
    maintenance_reserve = 1.06 * apartment_size  # €1.06/m² mandatory
    property_tax = 100.0 * scale_factor  # €80-120 typical, scaled
    insurance = 45.0 * scale_factor  # €35-60 average, scaled
    utilities = 250.0 * scale_factor  # €200-300 average, scaled
    return operating_costs + maintenance_reserve + property_tax + insurance + utilities


def _monthly_mortgage_payment(principal: float, annual_rate: float, years: int) -> float:
    # how much to pay monthly to pay off the loan in given years
    #
    # formula: M = P * [r(1+r)^n] / [(1+r)^n - 1]
    # where M = monthly payment, P = principal, r = monthly rate, n = number of payments
    if annual_rate == 0:
        return principal / (years * 12)
    monthly_rate = annual_rate / 12.0
    num_payments = years * 12
    return principal * (monthly_rate * (1 + monthly_rate) ** num_payments) / ((1 + monthly_rate) ** num_payments - 1)


def simulate_payoff_years(
    mortgage_amount: float,
    annual_interest_rate: float,
    monthly_savings: float,
    monthly_ownership_costs: float,
) -> tuple[float, float]:
    # simulate month-by-month payoff considering prepayment rules and 10-year option to fully pay off with notice
    # returns (years, total_interest_paid)
    if mortgage_amount <= 0:
        return 0.0, 0.0

    monthly_interest_rate = annual_interest_rate / 12.0
    monthly_mortgage_payment = _monthly_mortgage_payment(mortgage_amount, annual_interest_rate, STANDARD_TERM_YEARS)
    available_for_mortgage = monthly_savings - monthly_ownership_costs
    if available_for_mortgage < monthly_mortgage_payment:
        raise ValueError("monthly savings insufficient for mortgage and ownership costs")

    extra_available = available_for_mortgage - monthly_mortgage_payment
    monthly_extra_max = ANNUAL_EXTRA_LIMIT_WITHOUT_PENALTY / 12.0

    balance = mortgage_amount
    accumulated_savings = 0.0
    month = 0
    total_interest = 0.0

    while balance > 0:
        month += 1
        if month > 1000 * 12:
            raise ValueError("simulation did not converge")

        # monthly interest and principal from standard payment
        interest = balance * monthly_interest_rate
        total_interest += interest
        principal = monthly_mortgage_payment - interest
        principal = max(principal, 0.0)  # prevent negative if rate=0
        balance -= principal
        if balance <= 0:
            break

        # apply extra principal without penalty (capped)
        extra_applied = min(extra_available, monthly_extra_max, balance)
        balance -= extra_applied
        if balance <= 0:
            break

        # accumulate savings beyond what can be applied without penalty
        excess_saved = max(0.0, extra_available - monthly_extra_max)
        accumulated_savings += excess_saved

        # after 10 years, check for penalty-free full prepayment with notice
        if month >= 120:
            excess_per_month = max(0.0, extra_available - monthly_extra_max)
            projected_lump = accumulated_savings + NOTICE_MONTHS_FOR_PREPAY * excess_per_month

            # simulate balance during notice period with continued payments
            temp_balance = balance
            temp_interest = 0.0
            for _ in range(NOTICE_MONTHS_FOR_PREPAY):
                if temp_balance <= 0:
                    break
                temp_interest_month = temp_balance * monthly_interest_rate
                temp_interest += temp_interest_month
                temp_principal = monthly_mortgage_payment - temp_interest_month
                temp_principal = max(temp_principal, 0.0)
                temp_extra = min(monthly_extra_max, temp_balance - temp_principal)
                temp_balance -= temp_principal + temp_extra

            if projected_lump >= max(temp_balance, 0.0):
                total_interest += temp_interest
                return (month + NOTICE_MONTHS_FOR_PREPAY) / 12.0, total_interest

    return month / 12.0, total_interest


def estimate_mortgage_payoff_years(
    annual_savings: float,
    purchase_price: float = 500_000.0,
    cash_savings: float = 200_000.0,
) -> float:
    monthly_savings = annual_savings / 12.0
    if purchase_price <= 0 or cash_savings < 0 or monthly_savings <= 0:
        return float("inf")

    # could we buy outright?
    cash_upfront = _upfront_costs(purchase_price, 0.0)
    remaining = purchase_price + cash_upfront - cash_savings
    if remaining <= 0:
        return 0.0

    # could we save up instead of getting a mortgage?
    scale_factor = purchase_price / TYPICAL_PRICE_FOR_COSTS
    apartment_size = TYPICAL_APARTMENT_SIZE_M2 * scale_factor
    rent = RENT_PER_M2 * apartment_size
    effective_monthly_save = monthly_savings - rent
    if effective_monthly_save > 0:
        save_months = remaining / effective_monthly_save
        save_years = save_months / 12.0
    else:
        save_years = float("inf")

    try:
        # simulate mortgage payoff
        mortgage_amount = _mortgage_amount(purchase_price, cash_savings)
        if mortgage_amount <= 0:
            return float("inf")
        upfront = _upfront_costs(purchase_price, mortgage_amount)
        down_payment = cash_savings - upfront
        down_payment_ratio = down_payment / purchase_price
        annual_interest_rate = _interest_rate(down_payment_ratio)
        monthly_ownership_costs = _monthly_ownership_costs(purchase_price)
        payoff_years, total_interest = simulate_payoff_years(
            mortgage_amount,
            annual_interest_rate,
            monthly_savings,
            monthly_ownership_costs,
        )

        extra_fees = upfront - cash_upfront
        mortgage_cost = total_interest + extra_fees
        save_benefit = (rent - monthly_ownership_costs) * (save_months if save_years < float("inf") else 0)
        if mortgage_cost > save_benefit:
            return save_years if save_years < float("inf") else payoff_years
        else:
            return payoff_years

    except ValueError:
        # fall back to other option if mortgage simulation fails
        return save_years if save_years < float("inf") else float("inf")
