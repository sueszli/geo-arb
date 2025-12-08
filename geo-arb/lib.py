import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from utils import suppress_errors


@dataclass
class CountryData:
    name: str
    annual_expenses: float
    gross_income_by_percentile: Dict[str, int]
    net_salary_func: Callable[[int], float]


def load_countries() -> List[CountryData]:
    @suppress_errors
    def _load_country_module(path: Path) -> Optional[CountryData]:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)

        if not all(hasattr(module, k) for k in ("ANNUAL_EXPENSES", "GROSS_INCOME_BY_PERCENTILE", "net_salary")):
            return None

        return CountryData(
            name=path.stem.replace("_", " ").title(),
            annual_expenses=module.ANNUAL_EXPENSES,
            gross_income_by_percentile=module.GROSS_INCOME_BY_PERCENTILE,
            net_salary_func=module.net_salary,
        )

    paths = Path(__file__).parent.glob("*.py")
    countries = [_load_country_module(p) for p in paths if not p.name.startswith("_") and p.name not in ("lib.py", "utils.py")]
    return [c for c in countries if c]
