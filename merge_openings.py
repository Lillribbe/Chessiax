import json
from pathlib import Path

# 🔹 Vilka filer som ska slås ihop
SOURCE_FILES = [
    "openings-eco-expanded.json",
    "openings-eco-batch1.json",
    "openings-eco-batch2.json",
    "openings-imported-batch.json",
    "openings-imported-batch3.json",
    "openings-imported-batch4.json",
    "openings-imported-batch5.json",
    "openings-imported-batch6.json",
    "openings-imported-batch7.json",
    "openings-imported-batch8.json",
    "openings-imported-lichess.json",
    "openings-imported-lichess-full.json"
]

# 🔹 Utfil
OUTPUT_FILE = "openings-eco-master.json"


def load_json_file(filename):
    path = Path(filename)

    if not path.exists():
        print(f"File not found: {filename}")
        return []

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            print(f"Invalid format in {filename}: expected a list")
            return []

        return data

    except Exception as e:
        print(f"Could not load {filename}: {e}")
        return []


def make_key(opening):
    """
    Unique key for deduplication.
    Try id first, otherwise fallback to name + eco.
    """
    opening_id = opening.get("id")
    if opening_id:
        return ("id", opening_id.strip().lower())

    name = opening.get("name", "").strip().lower()
    eco = opening.get("eco", "").strip().lower()
    return ("fallback", name, eco)


def merge_openings():
    merged = []
    seen = set()

    for filename in SOURCE_FILES:
        openings = load_json_file(filename)
        print(f"Loaded {len(openings)} openings from {filename}")

        for opening in openings:
            key = make_key(opening)

            if key in seen:
                continue

            seen.add(key)
            merged.append(opening)

    # Sortera snyggt: först ECO, sen namn
    merged.sort(key=lambda x: (
        x.get("eco", ""),
        x.get("name", "")
    ))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(merged)} unique openings to {OUTPUT_FILE}")


if __name__ == "__main__":
    merge_openings()