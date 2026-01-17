# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "click",
#   "currency-converter",
#   "currencyconverter",
#   "openfisca-core",
#   "openfisca-france",
#   "numpy",
#   "polars",
#   "plotnine",
#   "pyarrow",
# ]
# ///

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "geo-arb"))

import importlib

import click


# usage example:
# $ uv run ./calc.py "united_kingdom" "100_000"
@click.command()
@click.argument("country")
@click.argument("gross_salary", type=float)
def get_savings(country: str, gross_salary: float):
    country = country.lower()
    module = importlib.import_module(country)
    net_salary = module.net_salary(gross_salary)
    annual_expenses = module.ANNUAL_EXPENSES
    net_savings = net_salary - annual_expenses
    click.echo(f"net savings:\t{net_savings:,.2f} EUR")


if __name__ == "__main__":
    get_savings()
