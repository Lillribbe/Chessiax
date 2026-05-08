import json
import os
import re

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

OUTPUT_FILE = "openings-eco-master.json"


def normalize_name(name):
    if not name:
        return ""

    name = name.lower()
    name = name.replace("defence", "defense")
    name = name.replace("'", "")
    name = name.replace(":", " ")
    name = name.replace(",", " ")
    name = name.replace("-", " ")
    name = name.replace(".", " ")
    name = re.sub(r"\s+", " ", name).strip()

    return name


def opening_key(opening):
    name = normalize_name(opening.get("name", ""))
    eco = opening.get("eco", "").strip().upper()

    if not name:
        return None

    if eco:
        return f"{eco}_{name}"

    return name


def score_opening_quality(opening):
    score = 0

    important_fields = [
        "name",
        "eco",
        "family",
        "variation",
        "style",
        "level",
        "color",
        "movesPreview",
        "description"
    ]

    for field in important_fields:
        value = opening.get(field)
        if value and value != "N/A" and value != "No description available.":
            score += 1

    return score


def merge_opening(existing, new):
    existing_score = score_opening_quality(existing)
    new_score = score_opening_quality(new)

    if new_score > existing_score:
        merged = new.copy()
        fallback = existing
    else:
        merged = existing.copy()
        fallback = new

    for key, value in fallback.items():
        if key not in merged or not merged[key] or merged[key] == "N/A":
            merged[key] = value

    return merged


def load_json_file(filename):
    if not os.path.exists(filename):
        print(f"Skipping missing file: {filename}")
        return []

    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            print(f"Skipping invalid file format: {filename}")
            return []

        return data

    except Exception as e:
        print(f"Could not load {filename}: {e}")
        return []


def main():
    merged_by_key = {}

    total_loaded = 0

    for filename in SOURCE_FILES:
        openings = load_json_file(filename)
        print(f"Loaded {len(openings)} openings from {filename}")
        total_loaded += len(openings)

        for opening in openings:
            key = opening_key(opening)

            if not key:
                continue

            if key in merged_by_key:
                merged_by_key[key] = merge_opening(merged_by_key[key], opening)
            else:
                merged_by_key[key] = opening

    merged = list(merged_by_key.values())

    merged.sort(key=lambda o: (
        o.get("eco", ""),
        o.get("name", "")
    ))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print("")
    print(f"Loaded total: {total_loaded}")
    print(f"Unique openings: {len(merged)}")
    print(f"Removed duplicates: {total_loaded - len(merged)}")
    print(f"Created {OUTPUT_FILE}")


if __name__ == "__main__":
    main()