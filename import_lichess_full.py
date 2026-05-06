import csv
import json
import re
from pathlib import Path

INPUT_FILES = ["a.tsv", "b.tsv", "c.tsv", "d.tsv", "e.tsv"]
OUTPUT_FILE = "openings-imported-lichess-full.json"


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("'", "")
    text = text.replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("é", "e")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def infer_family(name: str) -> str:
    lower = name.lower()

    if "sicilian" in lower:
        return "Sicilian Defense"
    if any(k in lower for k in ["french", "caro-kann", "scandinavian", "alekhine", "pirc", "modern defense"]):
        return "Semi-Open Game"
    if any(k in lower for k in ["queen's gambit", "slav", "semi-slav", "chigorin", "tarrasch defense"]):
        return "Queen's Gambit"
    if any(k in lower for k in ["indian", "grunfeld", "grünfeld", "benoni", "benko", "budapest gambit", "nimzo"]):
        return "Indian Defense"
    if "english" in lower:
        return "English Opening"
    if any(k in lower for k in ["reti", "réti", "bird", "polish", "orangutan", "larsen"]):
        return "Flank Opening"
    if any(k in lower for k in ["london", "catalan", "stonewall attack", "queen's pawn"]):
        return "Queen's Pawn"
    return "Open Game"


def infer_style(name: str) -> str:
    lower = name.lower()

    if "gambit" in lower:
        return "Aggressive"
    if any(k in lower for k in ["dragon", "najdorf", "sveshnikov", "kalashnikov", "benko", "grunfeld", "grünfeld"]):
        return "Dynamic"
    if any(k in lower for k in ["exchange", "classical", "orthodox"]):
        return "Classical"
    if any(k in lower for k in ["system", "attack"]):
        return "System"
    if any(k in lower for k in ["fianchetto", "rubinstein", "capablanca", "petrosian"]):
        return "Positional"
    return "Flexible"


def infer_color(name: str) -> str:
    lower = name.lower()

    black_keywords = [
        "defense", "indian", "grunfeld", "grünfeld", "benoni", "benko",
        "caro-kann", "french", "scandinavian", "slav", "semi-slav"
    ]
    if any(k in lower for k in black_keywords):
        return "Black"
    return "White"


def infer_level(name: str) -> str:
    lower = name.lower()

    if any(k in lower for k in [
        "najdorf", "dragon", "winawer", "grunfeld", "grünfeld",
        "nimzo", "semi-slav", "botvinnik", "poisoned pawn",
        "richter-rauzer", "meran", "sveshnikov"
    ]):
        return "Advanced"

    if any(k in lower for k in [
        "gambit", "sicilian", "indian", "catalan", "english",
        "french", "caro-kann", "reti", "réti"
    ]):
        return "Intermediate"

    return "Beginner"


def infer_variation(name: str) -> str:
    if ":" in name:
        return name.split(":", 1)[1].strip()
    if "," in name:
        return name.split(",", 1)[1].strip()
    return "Main Line"


def build_id(eco: str, name: str) -> str:
    return f"{eco.lower()}-{slugify(name)}"


def normalize_opening(eco: str, name: str, pgn: str) -> dict:
    return {
        "id": build_id(eco, name),
        "name": name,
        "eco": eco.upper(),
        "family": infer_family(name),
        "variation": infer_variation(name),
        "level": infer_level(name),
        "color": infer_color(name),
        "style": infer_style(name),
        "description": f"Imported from Lichess TSV dataset: {name}.",
        "movesPreview": pgn
    }


def main():
    imported = []
    seen = set()

    for filename in INPUT_FILES:
        path = Path(filename)

        if not path.exists():
            print(f"Skipping missing file: {filename}")
            continue

        print(f"Reading {filename}...")

        with path.open("r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")

            for row in reader:
                if len(row) < 3:
                    continue

                eco = row[0].strip()
                name = row[1].strip()
                pgn = row[2].strip()

                if not eco or not name or not pgn:
                    continue

                opening = normalize_opening(eco, name, pgn)
                key = (opening["eco"], opening["name"].lower())

                if key in seen:
                    continue

                seen.add(key)
                imported.append(opening)

    imported.sort(key=lambda x: (x.get("eco", ""), x.get("name", "")))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(imported, f, indent=2, ensure_ascii=False)

    print(f"\nImported {len(imported)} openings into {OUTPUT_FILE}")


if __name__ == "__main__":
    main()