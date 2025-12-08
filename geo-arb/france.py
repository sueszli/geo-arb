# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "openfisca-core==43.4.2",
#   "openfisca-france==174.2.8",
# ]
# ///

GROSS_INCOME_BY_PERCENTILE = {
    # data from levels.fyi
    "10th": 35_400,
    "25th": 43_600,
    "50th": 56_400,
    "75th": 74_100,
    "90th": 102_500,
}
EXPENSES_BREAKDOWN = {
    # paris
    # adjusted from numbeo.com: single, central 1bedroom
    "Housing": 1800.00,
    "Utilities": 160.00,
    "Groceries": 400.00,
    "Transportation": 88.80,
    "Subscriptions": 60.00,
    "Discretionary": 120.00,
    "Miscellaneous": 100.00,
}

ANNUAL_EXPENSES = sum(EXPENSES_BREAKDOWN.values()) * 12


#
# income tax
#


from datetime import date
from functools import lru_cache
from typing import Optional, Union

from openfisca_france import CountryTaxBenefitSystem


@lru_cache(maxsize=None)
def _tax_benefit_system() -> CountryTaxBenefitSystem:
    return CountryTaxBenefitSystem()


def _professional_expense_deduction(
    annual_gross_salary: float,
    year: int,
) -> float:
    # compute the 10% professional expense deduction (min / max capped)
    if annual_gross_salary <= 0:
        return 0.0

    parameters = _tax_benefit_system().parameters.impot_revenu.calcul_revenus_imposables.deductions.abatpro
    instant = f"{year}-01-01"
    rate = float(parameters.taux.get_at_instant(instant))
    minimum = float(parameters.min.get_at_instant(instant))
    maximum = float(parameters.max.get_at_instant(instant))

    deduction = annual_gross_salary * rate
    deduction = max(deduction, minimum)
    deduction = min(deduction, maximum)
    return min(deduction, annual_gross_salary)


def _build_simulation(
    annual_gross_salary: float,
    year: int,
    birth_year: Optional[int] = None,
):
    assert year > 0
    birth_year = birth_year or year - 30
    scenario_data = {
        "period": str(year),
        "individus": {
            "individu": {
                "date_naissance": f"{birth_year}-01-01",
                "salaire_de_base": float(annual_gross_salary),
            }
        },
        "foyers_fiscaux": {
            "foyer": {
                "declarants": ["individu"],
                "personnes_a_charge": [],
            }
        },
        "menages": {
            "menage": {
                "personne_de_reference": "individu",
                "enfants": [],
            }
        },
        "familles": {
            "famille": {
                "parents": ["individu"],
                "enfants": [],
            }
        },
    }

    system = _tax_benefit_system()
    scenario = system.new_scenario().init_from_dict(scenario_data)
    simulation = scenario.new_simulation()

    professional_deduction = _professional_expense_deduction(annual_gross_salary, year)
    net_taxable_income = float(annual_gross_salary - professional_deduction)
    simulation.set_input("traitements_salaires_pensions_rentes", str(year), [net_taxable_income])

    return simulation


def _read_variable(simulation, variable: str, period: str, *, add: bool = False) -> float:
    calculator = simulation.calculate_add if add else simulation.calculate
    values = calculator(variable, period)
    return float(values[0]) if getattr(values, "size", 0) else 0.0


def employer_social_contributions(
    annual_gross_salary: Union[int, float],
    *,
    year: int = 2024,
    birth_year: Optional[int] = None,
) -> int:
    if annual_gross_salary <= 0:
        return 0

    salary = float(annual_gross_salary)
    assert salary > 0.0
    assert isinstance(year, int)
    period = str(year)
    simulation = _build_simulation(salary, year, birth_year)
    amount = -_read_variable(simulation, "cotisations_employeur", period, add=True)
    return int(amount)


def employer_total_cost(
    annual_gross_salary: Union[int, float],
    *,
    year: int = 2024,
    birth_year=date.today().year - 30,
) -> int:
    # explanation: https://mycompanyinfrance.urssaf.fr/documentation/salari%C3%A9/co%C3%BBt-total-employeur
    if annual_gross_salary <= 0:
        return 0

    salary = float(annual_gross_salary)
    assert salary > 0.0
    assert isinstance(year, int)
    period = str(year)
    simulation = _build_simulation(salary, year, birth_year)
    contributions = -_read_variable(
        simulation,
        "cotisations_employeur",
        period,
        add=True,
    )
    return int(salary + contributions)


def compute_income_tax(
    annual_gross_salary: Union[int, float],
    *,
    year: int,
    birth_year: Optional[int] = None,
) -> dict[str, float]:
    simulation = _build_simulation(float(annual_gross_salary), year, birth_year)
    period = str(year)

    deduction = _professional_expense_deduction(float(annual_gross_salary), year)
    net_taxable_income = float(annual_gross_salary) - deduction

    reference_tax_income = _read_variable(simulation, "rfr", period)
    shares = _read_variable(simulation, "nbptr", period)
    gross_tax = _read_variable(simulation, "ir_brut", period)
    tax_due = -_read_variable(simulation, "impot_revenu_restant_a_payer", period)
    net_salary_before_tax = _read_variable(simulation, "salaire_net", period, add=True)

    return {
        "gross_income": float(annual_gross_salary),
        "professional_expense_deduction": deduction,
        "net_taxable_income": net_taxable_income,
        "reference_tax_income": reference_tax_income,
        "shares": shares,
        "dependents": 0,
        "gross_tax": gross_tax,
        "tax_due": tax_due,
        "net_salary_before_tax": net_salary_before_tax,
    }


def net_salary(
    annual_gross_salary: int,
    *,
    year: int = 2025,
    birth_year: Optional[int] = None,
) -> int:
    # based on: https://simulateur-ir-ifi.impots.gouv.fr/calcul_impot/2025/complet/index.htm
    # same as: compute_income_tax(GROSS)["net_salary_before_tax"] - compute_income_tax(GROSS)["tax_due"]
    if annual_gross_salary <= 0:
        return 0

    salary = float(annual_gross_salary)
    assert salary > 0.0
    assert isinstance(year, int)
    period = str(year)
    simulation = _build_simulation(salary, year, birth_year)
    annual_net = _read_variable(simulation, "salaire_net", period, add=True)
    income_tax = -_read_variable(simulation, "impot_revenu_restant_a_payer", period)

    return int(annual_net - income_tax)
