# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "currency-converter==0.5.5",
#   "currencyconverter==0.18.11",
#   "numpy==1.26.4",
#   "polars==1.36.0",
# ]
# ///

import sys
from pathlib import Path
import polars as pl
pl.Config.set_tbl_rows(-1)

sys.path.append(str(Path(__file__).parent / "geo-arb"))
import lib
from utils import estimate_mortgage_payoff_years

countries = lib.load_countries()
countries.sort(key=lambda x: x.name)
percentiles = ["10th", "25th", "50th", "75th", "90th"]

results = []
for country in countries:
    for p in percentiles:
        if p in country.gross_income_by_percentile:
            gross = country.gross_income_by_percentile[p]
            net = country.net_salary_func(gross)
            savings = net - country.annual_expenses
            mortgage_years = estimate_mortgage_payoff_years(savings)
            results.append({"country": country.name, "pct": p, "gross": gross, "net": net, "savings": savings, "mortgage_yrs": mortgage_years})

df = pl.DataFrame(results).sort("savings", descending=True)
print(df)
