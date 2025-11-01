import functools
import itertools
from enum import Enum, auto
from pathlib import Path

import pandas as pd
import plotnine as p9

#
# params
#


class Country(str, Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name

    GBR = auto()  # united kingdom
    CHE = auto()  # switzerland
    LIE = auto()  # liechtenstein
    AUT = auto()  # austria
    DEU = auto()  # germany


class DevExperience(str, Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name

    P10 = auto()  # 10th percentile
    P25 = auto()  # 25th percentile
    P50 = auto()  # 50th percentile
    P75 = auto()  # 75th percentile
    P90 = auto()  # 90th percentile


#
# retrieval
#


GROSS_INCOME_BY_PERCENTILE = {
    # data from levels.fyi
    Country.GBR: {
        "10th": 48_100,
        "25th": 66_000,
        "50th": 98_500,
        "75th": 145_000,
        "90th": 210_000,
    },
    Country.CHE: {
        "10th": 77_300,
        "25th": 101_000,
        "50th": 125_000,
        "75th": 179_000,
        "90th": 296_000,
    },
    Country.LIE: {
        # insufficient data, using switzerland's values
        # salaries are mostly the same
        "10th": 77_300,
        "25th": 101_000,
        "50th": 125_000,
        "75th": 179_000,
        "90th": 296_000,
    },
    Country.DEU: {
        "10th": 54_300,
        "25th": 65_700,
        "50th": 80_200,
        "75th": 99_100,
        "90th": 129_000,
    },
    Country.AUT: {
        "10th": 28_600,
        "25th": 43_000,
        "50th": 58_300,
        "75th": 74_100,
        "90th": 91_300,
    },
}

EXPENSES = {
    # mostly from numbeo.com
    # adapt to your lifestyle as needed!
    Country.GBR: {  # london
        "Housing": 2776.95,
        "Utilities": 263.93,
        "Groceries": 286.88,
        "Transportation": 218.03,
        "Subscriptions": 57.38,
        "Discretionary": 114.75,
        "Miscellaneous": 68.85,
    },
    Country.CHE: {  # zurich
        "Housing": 2854.00,
        "Utilities": 248.00,
        "Groceries": 474.00,
        "Transportation": 331.00,
        "Subscriptions": 81.00,
        "Discretionary": 108.00,
        "Miscellaneous": 162.00,
    },
    Country.LIE: {  # vaduz
        "Housing": 1620.00,
        "Utilities": 216.00,
        "Groceries": 810.00,
        "Transportation": 199.80,
        "Subscriptions": 54.00,
        "Discretionary": 108.00,
        "Miscellaneous": 75.60,
    },
    Country.DEU: {  # munich
        "Housing": 1700.00,
        "Utilities": 150.00,
        "Groceries": 350.00,
        "Transportation": 50.00,
        "Subscriptions": 60.00,
        "Discretionary": 100.00,
        "Miscellaneous": 100.00,
    },
    Country.AUT: {  # vienna
        "Housing": 800.00,
        "Utilities": 150.00,
        "Groceries": 280.00,
        "Transportation": 40.00,
        "Subscriptions": 40.00,
        "Discretionary": 70.00,
        "Miscellaneous": 50.00,
    },
}


from tax.austria import net_salary as aut_net_salary
from tax.germany import net_salary as deu_net_salary
from tax.liechtenstein import net_salary as lie_net_salary
from tax.switzerland import net_salary as che_net_salary
from tax.united_kingdom import net_salary as gbr_net_salary

TAX_FUNCTION_BY_COUNTRY = {
    Country.GBR: gbr_net_salary,
    Country.CHE: che_net_salary,
    Country.LIE: lie_net_salary,
    Country.DEU: deu_net_salary,
    Country.AUT: aut_net_salary,
}


def net_savings(country_code: Country, dev_experience: DevExperience) -> float:
    gross_income = GROSS_INCOME_BY_PERCENTILE[country_code][
        {
            DevExperience.P10: "10th",
            DevExperience.P25: "25th",
            DevExperience.P50: "50th",
            DevExperience.P75: "75th",
            DevExperience.P90: "90th",
        }[dev_experience]
    ]

    net_salary_function = TAX_FUNCTION_BY_COUNTRY[country_code]
    annual_net_income = net_salary_function(gross_income)

    monthly_expenses = sum(EXPENSES[country_code].values())
    annual_expenses = monthly_expenses * 12

    annual_savings = annual_net_income - annual_expenses
    return annual_savings


def get_plot() -> p9.ggplot:
    rows = []
    for country in Country:
        for experience in DevExperience:
            label_map = {
                DevExperience.P10: ("10th", "10th percentile"),
                DevExperience.P25: ("25th", "25th percentile"),
                DevExperience.P50: ("50th", "Median (50th)"),
                DevExperience.P75: ("75th", "75th percentile"),
                DevExperience.P90: ("90th", "90th percentile"),
            }
            key, label = label_map[experience]

            gross_income = GROSS_INCOME_BY_PERCENTILE[country][key]
            net_income = TAX_FUNCTION_BY_COUNTRY[country](gross_income)
            tax_deductions = gross_income - net_income
            living_costs = sum(EXPENSES[country].values()) * 12
            net_savings = net_income - living_costs

            rows.append(
                {
                    "country": country.value,
                    "experience_label": label,
                    "tax_deductions": float(tax_deductions),
                    "living_costs": float(living_costs),
                    "net_savings": float(net_savings),
                }
            )

    df = pd.DataFrame(rows)
    label_order = [
        "10th percentile",
        "25th percentile",
        "Median (50th)",
        "75th percentile",
        "90th percentile",
    ]
    df["experience_label"] = pd.Categorical(df["experience_label"], categories=label_order, ordered=True)

    breakdown = df.melt(
        id_vars=["country", "experience_label"],
        value_vars=["tax_deductions", "living_costs", "net_savings"],
        var_name="component",
        value_name="amount",
    )
    breakdown["component"] = breakdown["component"].map(
        {
            "tax_deductions": "Tax & social deductions",
            "living_costs": "Cost of living",
            "net_savings": "Net savings",
        }
    )

    return (
        p9.ggplot(breakdown, p9.aes("experience_label", "amount", fill="component"))
        + p9.geom_col(width=0.75)
        + p9.geom_hline(yintercept=0, linetype="solid", color="#2c2c2c", size=0.5)
        + p9.facet_wrap("~country", ncol=2)
        + p9.scale_fill_manual(
            values={
                "Tax & social deductions": "#c44e52",
                "Cost of living": "#4c72b0",
                "Net savings": "#55a868",
            }
        )
        + p9.scale_y_continuous(labels=lambda l: [f"{v / 1000:.0f}k" for v in l])
        + p9.labs(
            title="Developer Compensation Analysis Across European Countries",
            subtitle="Income breakdown by experience level showing tax burden, living costs and net savings potential",
            x="Experience Level (Levels.fyi percentile)",
            y="Annual Amount (€)",
            fill="",
        )
        + p9.theme_minimal()
        + p9.theme(
            figure_size=(14, 10),
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


if __name__ == "__main__":
    # print savings
    combos = itertools.product(Country, DevExperience)
    compute = functools.partial(net_savings)
    results = [(c, e, compute(c, e)) for c, e in combos]
    results = sorted(results, key=lambda x: x[2], reverse=True)

    from mortgage.austria import estimate_mortgage_payoff_years

    max_country_len = max(len(str(c)) for c, _, _ in results)
    max_exp_len = max(len(str(e)) for _, e, _ in results)
    max_savings_len = max(len(f"{s:,.2f}") for _, _, s in results)

    for country, experience, savings in results:
        yrs = estimate_mortgage_payoff_years(savings)
        yrs_str = f" ({yrs:.1f} yrs for mortgage)" if yrs != float("inf") else ""
        country_str = country.value[:3]
        exp_str = experience.value[:3]
        savings_str = f"{savings:,.2f}".rjust(max_savings_len)
        print(f"{country_str} [{exp_str}]: {savings_str} EUR/yr saved" + yrs_str)

    # plot
    output_dir = Path(__file__).resolve().parent.parent / "plots"
    output_dir.mkdir(exist_ok=True)
    get_plot().save(str(output_dir / "savings.png"), dpi=300, verbose=False)
