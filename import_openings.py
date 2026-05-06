import json
import re
from pathlib import Path

import sys

DEFAULT_INPUT_FILE = "raw-openings-sample.json"
DEFAULT_OUTPUT_FILE = "openings-imported-batch.json"


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def build_id(opening: dict) -> str:
    eco = str(opening.get("eco", "")).strip().lower()
    name = str(opening.get("name", "")).strip()
    slug = slugify(name)
    return f"{eco}-{slug}" if eco and slug else slug or "unknown-opening"


def load_raw_openings(filename: str) -> list:
    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {filename}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of openings")

    return data


def clean_str(value, default=""):
    if value is None:
        return default
    return str(value).strip()

def normalize_family(value: str) -> str:
    value = clean_str(value, "Unknown Family").lower()

    family_map = {
        "open game": "Open Game",
        "semi-open game": "Semi-Open Game",
        "sicilian defense": "Sicilian Defense",
        "queens gambit": "Queen's Gambit",
        "queen's gambit": "Queen's Gambit",
        "queens pawn": "Queen's Pawn",
        "queen's pawn": "Queen's Pawn",
        "indian defense": "Indian Defense",
        "english opening": "English Opening",
        "flank opening": "Flank Opening"
    }

    return family_map.get(value, value.title())


def normalize_style(value: str) -> str:
    value = clean_str(value, "Flexible").lower()

    style_map = {
        "solid": "Solid",
        "aggressive": "Aggressive",
        "positional": "Positional",
        "classical": "Classical",
        "dynamic": "Dynamic",
        "flexible": "Flexible",
        "balanced": "Balanced",
        "hypermodern": "Hypermodern",
        "unorthodox": "Unorthodox",
        "system": "System",
        "direct": "Direct"
    }

    return style_map.get(value, value.title())


def normalize_color(value: str) -> str:
    value = clean_str(value, "White").lower()

    color_map = {
        "white": "White",
        "black": "Black"
    }

    return color_map.get(value, "White")


def normalize_level(value: str) -> str:
    value = clean_str(value, "Intermediate").lower()

    level_map = {
        "beginner": "Beginner",
        "intermediate": "Intermediate",
        "advanced": "Advanced"
    }

    return level_map.get(value, "Intermediate")


def normalize_variation(value: str) -> str:
    value = clean_str(value, "Main Line")
    return value if value else "Main Line"


def normalize_opening(raw: dict) -> dict:
    name = clean_str(raw.get("name"))
    eco = clean_str(raw.get("eco")).upper()
    family = normalize_family(raw.get("family"))
    variation = normalize_variation(raw.get("variation"))
    level = normalize_level(raw.get("level"))
    color = normalize_color(raw.get("color"))
    style = normalize_style(raw.get("style"))
    description = clean_str(raw.get("description"), "No description available.")
    moves_preview = clean_str(raw.get("movesPreview"), "No moves preview available.")

    if not name:
        raise ValueError("Missing opening name")

    if not eco:
        raise ValueError(f"Missing ECO code for opening '{name}'")

    return {
        "id": build_id({
            "eco": eco,
            "name": name
        }),
        "name": name,
        "eco": eco,
        "family": family,
        "variation": variation,
        "level": level,
        "color": color,
        "style": style,
        "description": description,
        "movesPreview": moves_preview
    }


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT_FILE
    output_file = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT_FILE

    raw_openings = load_raw_openings(input_file)

    normalized = []
    skipped = []

    for index, item in enumerate(raw_openings, start=1):
        try:
            opening = normalize_opening(item)
            normalized.append(opening)
        except Exception as e:
            skipped.append({
                "index": index,
                "error": str(e),
                "raw": item
            })

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)

    print(f"\nImported {len(normalized)} openings into {output_file}")

    if skipped:
        print(f"Skipped {len(skipped)} invalid openings:\n")
        for entry in skipped:
            print(f"- Item {entry['index']}: {entry['error']}")
    else:
        print("No invalid openings were skipped.")


if __name__ == "__main__":
    main()