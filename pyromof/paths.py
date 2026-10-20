from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT_PATH / "results"
PREPROCESSING_DIR = ROOT_PATH / "preprocessing"
INPUT_DATA_FILE = ROOT_PATH / "input_data.xlsx"


def scenario_path(scenario: str) -> Path:
    return RESULTS_DIR / scenario


def scenario_results_path(scenario: str) -> Path:
    return scenario_path(scenario) / "results"


def scenario_dumping_space_path(scenario: str) -> Path:
    return scenario_path(scenario) / "dumping_space"


def scenario_meta_info_path(scenario: str) -> Path:
    return scenario_path(scenario) / "meta_info"


def ensure_scenario_directories(scenario: str):
    scenario_dir = scenario_path(scenario)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    meta_info = scenario_dir / "meta_info"
    meta_info.mkdir(exist_ok=True)

    dumping_space = scenario_dir / "dumping_space"
    dumping_space.mkdir(exist_ok=True)

    scenario_results = scenario_dir / "results"
    scenario_results.mkdir(exist_ok=True)

    return scenario_dir, meta_info, dumping_space
