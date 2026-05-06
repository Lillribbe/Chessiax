import csv
import json
import re
from pathlib import Path

INPUT_FILE = "raw-openings-lichess-sample.tsv"
OUTPUT_FILE = "openings-imported-lichess.json"


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def infer_family(name: str) -> str:
    lower = name.lower()

    if "sicilian" in lower:
        return "Sicilian Defense"
    if "french" in lower or "caro-kann" in lower or "scandinavian" in lower or "alekhine" in lower:
        return "Semi-Open Game"
    if "queen's gambit" in lower or "slav" in lower or "semi-slav" in lower:
        return "Queen's Gambit"
    if "indian" in lower or "grunfeld" in lower or "benoni" in lower or "benko" in lower:
        return "Indian Defense"
    if "english" in lower:
        return "English Opening"
    if "reti" in lower or "bird" in lower or "polish" in lower:
        return "Flank Opening"
    if "london" in lower or "catalan" in lower or "queen's pawn" in lower:
        return "Queen's Pawn"
    return "Open Game"


def infer_style(name: str) -> str:
    lower = name.lower()

    if "gambit" in lower:
        return "Aggressive"
    if "dragon" in lower or "najdorf" in lower or "sveshnikov" in lower or "benko" in lower:
        return "Dynamic"
    if "exchange" in lower or "classical" in lower:
        return "Classical"
    if "system" in lower or "stonewall" in lower:
        return "System"
    return "Flexible"


def infer_color(name: str) -> str:
    lower = name.lower()

    black_keywords = [
        "defense", "indian", "grunfeld", "benoni", "benko",
        "caro-kann", "french", "scandinavian", "slav", "semi-slav"
    ]
    if any(k in lower for k in black_keywords):
        return "Black"
    return "White"


def infer_level(name: str) -> str:
    lower = name.lower()

    if any(k in lower for k in ["najdorf", "dragon", "winawer", "grunfeld", "nimzo", "semi-slav"]):
        return "Advanced"
    if any(k in lower for k in ["gambit", "sicilian", "indian", "catalan", "english"]):
        return "Intermediate"
    return "Beginner"


def infer_variation(name: str) -> str:
    if ":" in name:
        return name.split(":", 1)[1].strip()
    return "Main Line"


def build_id(eco: str, name: str) -> str:
    return f"{eco.lower()}-{slugify(name)}"


def main():
    path = Path(INPUT_FILE)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    openings = []

    with path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 3:
                continue

            eco = row[0].strip()
            name = row[1].strip()
            pgn = row[2].strip()

            if not eco or not name:
                continue

            opening = {
                "id": build_id(eco, name),
                "name": name,
                "eco": eco,
                "family": infer_family(name),
                "variation": infer_variation(name),
                "level": infer_level(name),
                "color": infer_color(name),
                "style": infer_style(name),
                "description": f"Imported from TSV source: {name}.",
                "movesPreview": pgn
            }

            openings.append(opening)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(openings, f, indent=2, ensure_ascii=False)

    print(f"Imported {len(openings)} openings into {OUTPUT_FILE}")


if __name__ == "__main__":
    main()