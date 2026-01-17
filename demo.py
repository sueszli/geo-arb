# /// script
# requires-python = ">=3.13"
# dependencies = [
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

import pandas as pd
import plotnine as p9
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
            results.append(
                {
                    "country": country.name,
                    "pct": p,
                    "gross": gross,
                    "net": net,
                    "savings": savings,
                    "mortgage_yrs": mortgage_years,
                }
            )

df = pl.DataFrame(results).sort("savings", descending=True)
print(df)


def plot(df: pl.DataFrame):
    pdf = df.to_pandas()
    pdf["tax_deductions"] = pdf["gross"] - pdf["net"]
    pdf["living_costs"] = pdf["net"] - pdf["savings"]
    pdf["net_savings"] = pdf["savings"]
    pct_map = {
        "10th": ("10th percentile", 1),
        "25th": ("25th percentile", 2),
        "50th": ("Median (50th)", 3),
        "75th": ("75th percentile", 4),
        "90th": ("90th percentile", 5),
    }
    pdf["experience_label"] = pdf["pct"].map(lambda x: pct_map.get(x, (x, 0))[0])
    pdf["experience_numeric"] = pdf["pct"].map(lambda x: pct_map.get(x, (x, 0))[1])

    label_order = [
        "10th percentile",
        "25th percentile",
        "Median (50th)",
        "75th percentile",
        "90th percentile",
    ]
    pdf["experience_label"] = pd.Categorical(pdf["experience_label"], categories=label_order, ordered=True)

    # sort countries by highest net savings
    country_order = pdf.groupby("country")["net_savings"].max().sort_values(ascending=False).index.tolist()
    pdf["country"] = pd.Categorical(pdf["country"], categories=country_order, ordered=True)

    # label offset logic
    net_savings_top = pdf["tax_deductions"] + pdf["living_costs"] + pdf["net_savings"]
    label_offset = pdf["net_savings"].abs() * 0.04 + 1200
    signed_label_offset = label_offset.where(pdf["net_savings"] >= 0, -label_offset)

    def _format_thousands(value: float) -> str:
        value_k = value / 1000
        if abs(value_k) >= 100:
            formatted = f"{value_k:.0f}"
        elif abs(value_k) >= 10:
            formatted = f"{value_k:.1f}"
        else:
            formatted = f"{value_k:.2f}"
        formatted = formatted.rstrip("0").rstrip(".")
        return f"{formatted}k"

    pdf["label_text"] = pdf["net_savings"].apply(_format_thousands)
    pdf["label_y"] = net_savings_top + signed_label_offset

    # melt for stacked bar
    breakdown = pdf.melt(
        id_vars=["country", "experience_label", "experience_numeric"],
        value_vars=["tax_deductions", "living_costs", "net_savings"],
        var_name="component",
        value_name="amount",
    )

    # renaming components for legend
    component_map = {
        "tax_deductions": "Tax & social deductions",
        "living_costs": "Cost of living",
        "net_savings": "Net savings",
    }
    breakdown["component"] = breakdown["component"].map(component_map)
    component_order = ["Cost of living", "Tax & social deductions", "Net savings"]
    breakdown["component"] = pd.Categorical(breakdown["component"], categories=component_order, ordered=True)

    # add labels for bar sections
    breakdown["label_text"] = breakdown["amount"].apply(_format_thousands)

    p = (
        p9.ggplot(breakdown, p9.aes("experience_numeric", "amount", fill="component"))
        + p9.geom_col(width=0.75)
        # add labels inside the bars (only for Net savings)
        + p9.geom_text(
            data=breakdown[breakdown["component"] == "Net savings"],
            mapping=p9.aes(label="label_text"),
            position=p9.position_stack(vjust=0.5),
            size=8,
            color="#333333",
        )
        + p9.stat_smooth(
            data=pdf,
            mapping=p9.aes(
                x="experience_numeric",
                y="net_savings",
                group="country",
            ),
            inherit_aes=False,
            method="lm",
            formula="y ~ x + I(x**2) + I(x**3)",
            se=False,
            color="#1b9e77",
            size=1.1,
        )
        + p9.geom_hline(yintercept=0, linetype="solid", color="#2c2c2c", size=0.5)
        + p9.facet_wrap("~country", ncol=2)
        + p9.scale_fill_manual(
            values={
                "Cost of living": "#a6cee3",
                "Tax & social deductions": "#fbb4ae",
                "Net savings": "#b2df8a",
            },
            breaks=component_order,
        )
        + p9.scale_x_continuous(
            breaks=range(1, len(label_order) + 1),
            labels=label_order,
            expand=(0.02, 0),
        )
        + p9.scale_y_continuous(labels=lambda l: [f"{v / 1000:.0f}k" for v in l])
        + p9.labs(
            title="Developer Savings Potential by Country",
            subtitle="Net savings after tax and living costs across experience levels",
            x="Experience Level (Levels.fyi percentile)",
            y="Annual Amount (€)",
            fill="",
        )
        + p9.theme_minimal()
        + p9.theme(
            figure_size=(15, 13),
            plot_title=p9.element_text(size=14, weight="bold", margin={"b": 4}),
            plot_subtitle=p9.element_text(size=10, color="#4a4a4a", margin={"b": 6}),
            axis_text_x=p9.element_text(angle=45, ha="right", size=9),
            axis_text_y=p9.element_text(size=9),
            axis_title_x=p9.element_text(size=10, weight="bold", margin={"t": 4}),
            axis_title_y=p9.element_text(size=10, weight="bold", margin={"r": 4}),
            legend_position="top",
            legend_direction="horizontal",
            legend_text=p9.element_text(size=10),
            legend_title=p9.element_blank(),
            legend_margin=0,
            panel_spacing_x=0.02,
            panel_spacing_y=0.04,
            strip_text=p9.element_text(size=11, weight="bold", margin={"b": 2, "t": 2}),
            strip_background=p9.element_rect(fill="#f5f5f5", color="#e0e0e0"),
            panel_grid_major_y=p9.element_line(color="#e8e8e8", size=0.5),
            panel_grid_minor_y=p9.element_blank(),
            panel_grid_major_x=p9.element_blank(),
        )
    )
    p.save("savings.pdf", format="pdf", verbose=False)


plot(df)
