from flask_cors import CORS
from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI
import os
import json
import requests
import re
from datetime import datetime
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv
load_dotenv()  

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)
CORS(app)

COUNTRY_NAMES = {
    "SE": "Sweden",
    "US": "United States",
    "GB": "United Kingdom",
    "NO": "Norway",
    "DK": "Denmark",
    "FI": "Finland",
    "DE": "Germany",
    "FR": "France",
    "ES": "Spain",
    "IT": "Italy",
    "NL": "Netherlands",
    "PL": "Poland",
    "IN": "India",
    "CN": "China",
    "JP": "Japan",
    "KR": "South Korea",
    "BR": "Brazil",
    "CA": "Canada",
    "AU": "Australia",
    "RU": "Russia",
    "UA": "Ukraine"
}

OPENING_FAMILIES = [
    "Queen's Gambit",
    "King's Indian Defense",
    "Queen's Indian Defense",
    "Nimzo-Indian Defense",
    "Sicilian Defense",
    "French Defense",
    "Caro-Kann Defense",
    "Modern Defense",
    "Pirc Defense",
    "Scandinavian Defense",
    "Alekhine Defense",
    "Ruy Lopez",
    "Italian Game",
    "English Opening",
    "Queen's Pawn Opening",
    "King's Pawn Opening",
    "London System",
    "Scotch Game",
    "Four Knights Game",
    "Catalan Opening",
    "Dutch Defense",
    "Grunfeld Defense",
    "Slav Defense"
]

def clean_country(country_url):
    if not country_url:
        return "Unknown"

    country_code = country_url.rstrip("/").split("/")[-1].upper()

    return COUNTRY_NAMES.get(country_code, country_code)

def get_pgn_tag(pgn, tag_name):
    if not pgn:
        return None

    match = re.search(rf'\[{tag_name}\s+"([^"]+)"\]', pgn)
    if match:
        return match.group(1).strip()

    return None

def eco_url_to_opening_name(eco_url):
    if not eco_url:
        return None

    slug = unquote(urlparse(eco_url).path.rstrip("/").split("/")[-1])
    if not slug:
        return None

    readable = re.sub(r"[-_]+", " ", slug).strip()
    return readable.title() if readable else None

def extract_opening_name(pgn):
    opening = get_pgn_tag(pgn, "Opening")
    if opening:
        return opening

    eco_url = get_pgn_tag(pgn, "ECOUrl")
    opening_from_url = eco_url_to_opening_name(eco_url)
    if opening_from_url:
        return opening_from_url

    return "Unknown Opening"

def estimate_total_moves_from_pgn(pgn):
    if not isinstance(pgn, str) or not pgn.strip():
        return 0

    try:
        movetext = re.sub(r'^\s*\[.*?\]\s*$', ' ', pgn, flags=re.MULTILINE)
        movetext = re.sub(r'\{[^}]*\}', ' ', movetext, flags=re.DOTALL)
        movetext = re.sub(r';[^\n]*', ' ', movetext)

        previous = None
        while previous != movetext:
            previous = movetext
            movetext = re.sub(r'\([^()]*\)', ' ', movetext)

        move_numbers = [
            int(move_number)
            for move_number in re.findall(r'(?<!\d)(\d+)\s*\.(?:\.\.)?', movetext)
        ]
        if move_numbers:
            return max(move_numbers)

        tokens = re.split(r'\s+', movetext.strip())
        move_tokens = [
            token for token in tokens
            if token
            and token not in {"1-0", "0-1", "1/2-1/2", "*"}
            and not token.startswith("$")
        ]
        return (len(move_tokens) + 1) // 2
    except Exception:
        return 0

def estimate_phase_from_move_count(move_count):
    if move_count < 15:
        return "opening"
    if move_count <= 35:
        return "middlegame"
    return "endgame"

def pgn_result_for_player(result, player_color):
    if player_color not in {"white", "black"}:
        return None

    if result == "1/2-1/2":
        return "draw"
    if result == "1-0":
        return "win" if player_color == "white" else "loss"
    if result == "0-1":
        return "win" if player_color == "black" else "loss"

    return "unknown"

def build_pgn_recommended_training(estimated_phase, player_result, opening):
    recommendations = []

    if estimated_phase == "opening":
        recommendations.append("Study this opening")
    elif estimated_phase == "middlegame":
        recommendations.append("Practice tactics")
    elif estimated_phase == "endgame":
        recommendations.append("Review endgame technique")

    if player_result == "loss":
        if estimated_phase != "opening" and opening != "Unknown Opening":
            recommendations.append("Review how this opening led into the critical position")
        recommendations.append("Replay the game and find the first major turning point")
    elif player_result == "draw":
        recommendations.append("Review missed winning chances and conversion plans")
    elif player_result == "win":
        recommendations.append("Save the key idea that worked well")

    return list(dict.fromkeys(recommendations))

def build_pgn_coach_summary(move_count, estimated_phase, player_result, opening):
    opening_text = opening if opening and opening != "Unknown Opening" else "an unknown opening"

    if player_result == "loss":
        return (
            f"This game reached the {estimated_phase} after about {move_count} moves. "
            f"Since it was a loss, start by reviewing {opening_text} and the first moment your position became difficult."
        )
    if player_result == "win":
        return (
            f"This game reached the {estimated_phase} after about {move_count} moves. "
            "Review the key move that gave you control so you can repeat the pattern."
        )
    if player_result == "draw":
        return (
            f"This game reached the {estimated_phase} after about {move_count} moves. "
            "Look for missed chances to convert or simplify more clearly."
        )

    return (
        f"This game reached the {estimated_phase} after about {move_count} moves. "
        f"A useful first review target is {opening_text}, then the transition into the critical phase."
    )

def normalize_opening_text(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower().replace("'", "")).strip()

def normalize_opening_family(opening_name):
    if not opening_name or opening_name == "Unknown Opening":
        return "Unknown Opening"

    normalized_name = normalize_opening_text(opening_name)

    for family in OPENING_FAMILIES:
        normalized_family = normalize_opening_text(family)
        if normalized_name.startswith(normalized_family):
            return family

    opening_without_detail = re.split(r"[:;,]", opening_name, maxsplit=1)[0].strip()
    opening_without_moves = re.sub(r"\s+\d+\..*$", "", opening_without_detail).strip()

    return opening_without_moves or "Unknown Opening"

def chesscom_result_to_outcome(result):
    if result == "win":
        return "win"

    draw_results = {
        "agreed",
        "repetition",
        "stalemate",
        "insufficient",
        "50move",
        "timevsinsufficient"
    }

    if result in draw_results:
        return "draw"

    return "loss"

def outcome_to_stats_key(outcome):
    return {
        "win": "wins",
        "draw": "draws",
        "loss": "losses"
    }[outcome]

def calculate_score_percentage(stats):
    if stats["games"] == 0:
        return 0

    score = stats["wins"] + (stats["draws"] * 0.5)
    return round((score / stats["games"]) * 100, 1)

def confidence_for_games(games):
    if games == 1:
        return "low"
    if games <= 4:
        return "medium"
    return "high"

def stats_to_list(stats_by_name, name_key):
    items = []

    for name, stats in stats_by_name.items():
        items.append({
            name_key: name,
            "games": stats["games"],
            "wins": stats["wins"],
            "draws": stats["draws"],
            "losses": stats["losses"],
            "score_percentage": calculate_score_percentage(stats),
            "as_white": stats["as_white"],
            "as_black": stats["as_black"],
            "confidence": confidence_for_games(stats["games"])
        })

    return items

def opening_stats_to_list(opening_stats):
    return stats_to_list(opening_stats, "opening")

def family_stats_to_list(family_stats):
    return stats_to_list(family_stats, "family")

def select_weak_families(families, limit=5):
    def sort_weak(items):
        return sorted(items, key=lambda item: (item["score_percentage"], -item["games"]))

    selected = []
    repeat_families = [family for family in families if family["games"] >= 2]
    priority_families = sort_weak([
        family for family in repeat_families
        if family["score_percentage"] < 80
    ])

    selected.extend(priority_families)

    if len(selected) < 3:
        selected_names = {family["family"] for family in selected}
        fill_families = sort_weak([
            family for family in repeat_families
            if family["family"] not in selected_names
            and family["score_percentage"] < 100
        ])
        selected.extend(fill_families)

    if len(selected) < 3:
        selected_names = {family["family"] for family in selected}
        selected.extend(sort_weak([
            family for family in repeat_families
            if family["family"] not in selected_names
        ]))

    if not selected:
        selected = sort_weak([
            family for family in families
            if family["score_percentage"] < 100
        ]) or sort_weak(families)

    return selected[:limit]

@app.route("/")
def serve_home():
    return send_from_directory(".", "home.html")

@app.route("/home.html")
def serve_home_file():
    return send_from_directory(".", "home.html")

@app.route("/profile.html")
def serve_profile():
    return send_from_directory(".", "profile.html")

@app.route('/profile')
def profile():
    return send_from_directory(".", 'profile.html')

@app.route("/index.html")
def serve_index():
    return send_from_directory(".", "index.html")

@app.route("/openings.html")
def serve_openings():
    return send_from_directory(".", "openings.html")

@app.route("/opening.html")
def serve_opening():
    return send_from_directory(".", "opening.html")

@app.route("/tactics.html")
def serve_tactics():
    return send_from_directory(".", "tactics.html")

@app.route("/review.html")
def serve_review():
    return send_from_directory(".", "review.html")

@app.route("/style.css")
def serve_css():
    return send_from_directory(".", "style.css")

@app.route("/config.js")
def serve_config():
    return send_from_directory(".", "config.js")

@app.route("/<path:filename>")
def serve_static_files(filename):
    allowed_files = [
        "home.html",
        "index.html",
        "profile.html",
        "openings.html",
        "opening.html",
        "style.css",
        "config.js",
        "profile.js",
        "script.js",
        "favicon.ico"
    ]

    if filename in allowed_files:
        return send_from_directory(".", filename)

    return "File not found", 404

@app.route("/favicon.ico")
def favicon():
    return "", 204

#  AI-insight
def generate_insight(elo):
    prompt = f"""
    A chess player has an ELO of {elo}.
    Give 1 short, practical improvement tip.
    Be specific and actionable.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200
        )
    return response.choices[0].message.content

# VIKTIG ROUTE
@app.route("/get_openings", methods=["POST"])
def get_openings():
    data = request.get_json()
    elo = data.get("elo")

    if elo is None:
        return jsonify({"error": "Elo is required"}), 400
    
    try:
        elo = int(elo)
    except:
        return jsonify({"error": "Elo must be a number"}), 400

    # Fake data (första version) Byter sedan den mot datan som tas från Chess.com datan, alltså när jag samlar in stor mängd matcher och analyserar de.
    openings_data = {
        "beginner": [
            {
                "name": "London System",
                "winrate": 58,
                "reason": "Simple, solid and easy to learn"
            },
            {
                "name": "Italian Game",
                "winrate": 55,
                "reason": "Good for learning attacking ideas"
            },
            {
                "name": "Four Knights Game",
                "winrate": 52,
                "reason": "Symmetrical and logical; all pieces come out quickly without tricky traps."
            },
            {
                "name": "Scotch Game",
                "winrate": 53,
                "reason": "Opens the center early, teaching you to handle open lines and quick attacks."
             },
             {
                "name": "Queen's Gambit Declined",
                "winrate": 51,
                "reason": "Solid and positional - good for understanding pawn structures without losing immediately."
             }
        ],
        "intermediate": [
            {
                "name": "Ruy Lopez",
                "winrate": 54,
                "reason": "Strong positional opening"
            },
            {
                "name": "Sicilian Defense (Dragon Variation)",
                "winrate": 58,
                "reason": "Sharp and dynamic - learn to attack on the kingside with h4-h5 and sacrifices."
            },
            {
                "name": "Caro-Kann",
                "winrate": 56,
                "reason": "Very solid defense"
            },
            {
                "name": "King's Indian Defense (Classical)",
                "winrate": 57,
                "reason": "Hypermodern with a kingside counterattack - requires positional feel."
            },
            {
                "name": "Catalan Opening",
                "winrate": 54,
                "reason": "Slow buildup with long castling - good for practicing how to keep the initiative."
            }
        ],
        "expert": [
             {
                "name": "Najdorf Sicilian",
                "winrate": 60,
                "reason": "Sharpest Sicilian line - demands deep opening theory and tactical precision."
             },
             {
                "name": "Grunfeld Defense",
                "winrate": 59,
                "reason": "Dynamic and conceptually demanding; Black sacrifices the center for counterplay."
             },
             {
                "name": "Berlin Defense (Ruy López)",
                "winrate": 56,
                "reason": "Solid and 'invincible' for White - great for draws or technical endgames."
             },
             {
                "name": "English Opening (Symmetrical Variation)",
                "winrate": 55,
                "reason": "Rich in transpositions and positionally subtle - requires deep planning."
             },
             {
                "name": "Queen's Indian Defense (Petrosian Variation)",
                "winrate": 57,
                "reason": "Hypermodern with bindings and maneuvering - good for disrupting White's setup."
             }
        ]
    }

    avoid_data = {
    "beginner": [
        {
            "name": "Scholar's Mate Attempts",
            "reason": "Too predictable and easily countered"
        },
        {
            "name": "Random pawn pushes",
            "reason": "Leads to weak positions and no development"
        }
    ],
    "intermediate": [
        {
            "name": "Early Queen Attacks",
            "reason": "Can be punished easily by experienced players"
        }
    ],
    "expert": [
        {
            "name": "Dubious gambits",
            "reason": "Require deep preparation and are risky"
        }
    ]
    }

    tactics_data = {
    "beginner": [
        "Focus on forks and pins",
        "Always check for hanging pieces",
        "Solve simple puzzles daily"
    ],
    "intermediate": [
        "Practice combinations (2-3 moves ahead)",
        "Look for sacrifices on f7/f2",
        "Improve calculation accuracy"
    ],
    "expert": [
        "Deep calculation (4-6 moves)",
        "Recognize tactical patterns instantly",
        "Master initiative and tempo"
    ]
    }

    endgame_data = {
    "beginner": [
        "Learn king + queen vs king",
        "Activate your king early",
        "Avoid unnecessary pawn moves"
    ],
    "intermediate": [
        "Study rook endgames",
        "Understand opposition",
        "Improve pawn structure awareness"
    ],
    "expert": [
        "Master theoretical endgames",
        "Optimize piece coordination",
        "Play for zugzwang positions"
    ]
    }

    # Enkel logik baserat på ELO
    if elo < 1300:
        result = openings_data["beginner"]
        avoid = avoid_data["beginner"]
        tactics = tactics_data["beginner"]
        endgames = endgame_data["beginner"]
    elif 1300 <= elo <= 1800:
        result = openings_data["intermediate"]
        avoid = avoid_data["intermediate"]
        tactics = tactics_data["intermediate"]
        endgames = endgame_data["intermediate"]
    else:
        result = openings_data["expert"]
        avoid = avoid_data["expert"]
        tactics = tactics_data["expert"]
        endgames = endgame_data["expert"]

    result = sorted(result, key=lambda x: x["winrate"], reverse=True)
    insight = generate_insight(elo)

    return jsonify({
        "elo": elo,
        "recommendations": result,
        "avoid": avoid,
         "tactics": tactics,
        "endgames": endgames,
        "insight": insight
    })

@app.route("/get_opening_details", methods=["POST"])
def get_opening_details():
    data = request.get_json()
    opening_name = data.get("opening")

    prompt = f"""
    You are a chess coach.

    For the exact chess opening "{opening_name}", return ONLY valid JSON.

    Use this exact schema:

    {{
    "moves": [
        {{"move": "SAN_MOVE", "explanation": "short explanation"}}
    ],
    "how_to_play": "short explanation",
    "ideas": "short explanation",
    "traps": "short explanation"
    }}

    Rules:
    - The moves must represent the EXACT named opening, not a generic e4 e5 opening.
    - Include enough moves so the opening is clearly identified.
    - Use ONLY legal SAN notation, like e4, e5, Nf3, Nc6, Bc4, d4, Nc3, O-O.
    - Do NOT include move numbers.
    - Do NOT include annotations like !, ?, +, or #.
    - Max 8 half-moves in the moves list.
    - No markdown.
    - No text outside the JSON object.

    If the opening name contains a variation in parentheses, follow that exact variation.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    text = response.choices[0].message.content

    print("AI RAW RESPONSE:", text)

    clean_text = text.strip()

    if clean_text.startswith("```"):
        clean_text = clean_text.split("```")[1]

    clean_text = clean_text.replace("json", "").strip()

    try:
        parsed = json.loads(clean_text)
    except Exception as e:
        print("JSON ERROR:", e)
        parsed = {}

    moves = parsed.get("moves", [])

    details = {
        "how_to_play": parsed.get("how_to_play", ""),
        "ideas": parsed.get("ideas", ""),
        "traps": parsed.get("traps", "")
    }

    return jsonify({
        "opening": opening_name,
        "moves": moves,
        "details": details
    })

@app.route("/get_library_openings", methods=["GET"])
def get_library_openings():
    try:
        source = request.args.get("source", "master")

        if source == "base":
            filenames = ["openings-eco.json"]
        elif source == "expanded":
            filenames = ["openings-eco-expanded.json"]
        elif source == "batch1":
            filenames = ["openings-eco-expanded.json", "openings-eco-batch1.json"]
        elif source == "master":
            filenames = ["openings-eco-master.json"]
        else:
            filenames = ["openings-eco-master.json"]

        openings = []

        for filename in filenames:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                openings.extend(data)

        return jsonify(openings)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/analyze_games", methods=["POST"])
def analyze_games():
    try:
        data = request.get_json() or {}
        username = data.get("username", "").strip().lower()
        limit = data.get("limit", 20)

        if not username:
            return jsonify({"error": "Username is required"}), 400

        try:
            limit = int(limit)
        except:
            return jsonify({"error": "Limit must be a number"}), 400

        if limit <= 0:
            return jsonify({"error": "Limit must be greater than 0"}), 400

        headers = {
            "User-Agent": "ChessAITrainer/1.0 (contact: your-email@example.com)"
        }

        archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
        archives_response = requests.get(archives_url, headers=headers, timeout=10)

        if archives_response.status_code != 200:
            return jsonify({"error": f"Could not fetch game archives for '{username}'"}), 404

        archive_urls = archives_response.json().get("archives", [])
        games = []

        for archive_url in reversed(archive_urls):
            if len(games) >= limit:
                break

            archive_response = requests.get(archive_url, headers=headers, timeout=10)
            if archive_response.status_code != 200:
                continue

            archive_games = archive_response.json().get("games", [])
            for game in reversed(archive_games):
                if len(games) >= limit:
                    break
                games.append(game)

        overall = {
            "wins": 0,
            "draws": 0,
            "losses": 0
        }
        white_games = 0
        black_games = 0
        phase_losses = {
            "opening": 0,
            "middlegame": 0,
            "endgame": 0
        }
        opening_stats = {}
        family_stats = {}

        for game in games:
            white = game.get("white", {})
            black = game.get("black", {})
            white_username = white.get("username", "").lower()
            black_username = black.get("username", "").lower()

            if white_username == username:
                color = "white"
                result = white.get("result")
                white_games += 1
            elif black_username == username:
                color = "black"
                result = black.get("result")
                black_games += 1
            else:
                continue

            outcome = chesscom_result_to_outcome(result)
            outcome_key = outcome_to_stats_key(outcome)
            overall[outcome_key] += 1

            pgn = game.get("pgn", "")
            if outcome == "loss":
                total_moves = estimate_total_moves_from_pgn(pgn)
                if total_moves < 15:
                    phase_losses["opening"] += 1
                elif total_moves <= 35:
                    phase_losses["middlegame"] += 1
                else:
                    phase_losses["endgame"] += 1

            opening_name = extract_opening_name(pgn)
            family_name = normalize_opening_family(opening_name)

            if opening_name not in opening_stats:
                opening_stats[opening_name] = {
                    "games": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "as_white": 0,
                    "as_black": 0
                }

            if family_name not in family_stats:
                family_stats[family_name] = {
                    "games": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "as_white": 0,
                    "as_black": 0
                }

            for stats in (opening_stats[opening_name], family_stats[family_name]):
                stats["games"] += 1
                stats[outcome_key] += 1

                if color == "white":
                    stats["as_white"] += 1
                else:
                    stats["as_black"] += 1

        openings = opening_stats_to_list(opening_stats)
        families = family_stats_to_list(family_stats)
        most_played_openings = sorted(
            openings,
            key=lambda item: item["games"],
            reverse=True
        )[:5]
        top_openings = sorted(
            openings,
            key=lambda item: (item["score_percentage"], item["games"]),
            reverse=True
        )[:5]
        weak_openings = sorted(
            openings,
            key=lambda item: (item["score_percentage"], -item["games"])
        )[:5]
        family_performance = sorted(
            families,
            key=lambda item: item["games"],
            reverse=True
        )
        top_opening_families = sorted(
            families,
            key=lambda item: (item["score_percentage"], item["games"]),
            reverse=True
        )[:5]
        weak_opening_families = select_weak_families(families)

        study_candidates = [
            family for family in weak_opening_families
            if family["score_percentage"] < 100
        ]
        if not study_candidates:
            study_candidates = weak_opening_families

        recommended_study = [
            {
                "family": family["family"],
                "confidence": family["confidence"],
                "reason": f"Your score is {family['score_percentage']}% over {family['games']} games."
            }
            for family in study_candidates
            if family["games"] > 0
        ][:3]

        total_losses = overall["losses"]
        most_common_loss_phase = "none"
        if total_losses > 0:
            most_common_loss_phase = max(
                phase_losses,
                key=lambda phase: phase_losses[phase]
            )

        phase_summary = {
            "opening_losses": phase_losses["opening"],
            "middlegame_losses": phase_losses["middlegame"],
            "endgame_losses": phase_losses["endgame"],
            "total_losses": total_losses,
            "most_common_loss_phase": most_common_loss_phase
        }

        weakness_breakdown = [
            {
                "area": "Opening",
                "status": "Needs work" if phase_losses["opening"] > 0 else "Stable",
                "reason": (
                    f"{phase_losses['opening']} of your {total_losses} losses ended before move 15."
                    if phase_losses["opening"] > 0
                    else "No analyzed losses ended before move 15."
                )
            },
            {
                "area": "Middlegame",
                "status": "Needs work" if phase_losses["middlegame"] > 0 else "Stable",
                "reason": (
                    f"{phase_losses['middlegame']} of your {total_losses} losses ended between moves 15 and 35."
                    if phase_losses["middlegame"] > 0
                    else "No analyzed losses ended between moves 15 and 35."
                )
            },
            {
                "area": "Endgame",
                "status": "Needs work" if phase_losses["endgame"] > 0 else "Stable",
                "reason": (
                    f"{phase_losses['endgame']} of your {total_losses} losses ended after move 35."
                    if phase_losses["endgame"] > 0
                    else "No analyzed losses ended after move 35."
                )
            }
        ]

        return jsonify({
            "username": username,
            "games_analyzed": overall["wins"] + overall["draws"] + overall["losses"],
            "overall": overall,
            "white_games": white_games,
            "black_games": black_games,
            "most_played_openings": most_played_openings,
            "top_openings": top_openings,
            "weak_openings": weak_openings,
            "family_performance": family_performance,
            "top_opening_families": top_opening_families,
            "weak_opening_families": weak_opening_families,
            "recommended_study": recommended_study,
            "phase_summary": phase_summary,
            "weakness_breakdown": weakness_breakdown
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/analyze_pgn", methods=["POST"])
def analyze_pgn():
    try:
        data = request.get_json() or {}
        pgn = data.get("pgn", "")
        username = data.get("username", "")

        if not isinstance(pgn, str) or not pgn.strip():
            return jsonify({"error": "PGN is required"}), 400

        username_normalized = str(username or "").strip().lower()
        white = get_pgn_tag(pgn, "White") or "Unknown"
        black = get_pgn_tag(pgn, "Black") or "Unknown"
        result = get_pgn_tag(pgn, "Result") or "*"
        opening = extract_opening_name(pgn)
        eco = get_pgn_tag(pgn, "ECO") or ""
        date = get_pgn_tag(pgn, "Date") or ""
        move_count = estimate_total_moves_from_pgn(pgn)
        estimated_phase = estimate_phase_from_move_count(move_count)

        player_color = None
        if username_normalized:
            if white.lower() == username_normalized:
                player_color = "white"
            elif black.lower() == username_normalized:
                player_color = "black"

        player_result = pgn_result_for_player(result, player_color)
        coach_summary = build_pgn_coach_summary(
            move_count,
            estimated_phase,
            player_result,
            opening
        )
        recommended_training = build_pgn_recommended_training(
            estimated_phase,
            player_result,
            opening
        )

        return jsonify({
            "white": white,
            "black": black,
            "result": result,
            "opening": opening,
            "eco": eco,
            "date": date,
            "move_count": move_count,
            "estimated_phase": estimated_phase,
            "player_color": player_color,
            "player_result": player_result,
            "coach_summary": coach_summary,
            "recommended_training": recommended_training
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_chess_profile", methods=["POST"])
def get_chess_profile():
    try:
        data = request.get_json()
        username = data.get("username", "").strip().lower()

        if not username:
            return jsonify({"error": "Username is required"}), 400

        headers = {
            "User-Agent": "ChessAITrainer/1.0 (contact: your-email@example.com)"
        }

        profile_url = f"https://api.chess.com/pub/player/{username}"
        stats_url = f"https://api.chess.com/pub/player/{username}/stats"

        profile_response = requests.get(profile_url, headers=headers, timeout=10)
        stats_response = requests.get(stats_url, headers=headers, timeout=10)

        if profile_response.status_code != 200:
            return jsonify({"error": f"Could not fetch profile for '{username}'"}), 404

        profile = profile_response.json()

        stats = {}
        if stats_response.status_code == 200:
            stats = stats_response.json()

        recommended_openings = []

        joined_timestamp = profile.get("joined")
        joined_date = None

        if joined_timestamp:
            joined_date = datetime.utcfromtimestamp(joined_timestamp).strftime("%Y-%m-%d")

        chess_rapid = stats.get("chess_rapid", {})
        chess_blitz = stats.get("chess_blitz", {})
        chess_bullet = stats.get("chess_bullet", {})

        rapid_record = chess_rapid.get("record", {})
        blitz_record = chess_blitz.get("record", {})
        bullet_record = chess_bullet.get("record", {})

        rapid_rating = chess_rapid.get("last", {}).get("rating")
        blitz_rating = chess_blitz.get("last", {}).get("rating")
        bullet_rating = chess_bullet.get("last", {}).get("rating")

        profile_prompt = f"""
        You are a chess improvement coach.

        A player has these Chess.com ratings:
        - Rapid: {rapid_rating}
        - Blitz: {blitz_rating}
        - Bullet: {bullet_rating}

        Return ONLY valid JSON in this format:

        {{
        "summary": "A short 2-3 sentence summary of the player's profile",
        "recommendation": "One clear recommendation for what this player should focus on next",
        "openings": [
            {{
            "name": "London System",
            "reason": "Short reason why this opening fits the player"
            }},
            {{
            "name": "Italian Game",
            "reason": "Short reason why this opening fits the player"
            }},
            {{
            "name": "Queen's Gambit",
            "reason": "Short reason why this opening fits the player"
            }}
        ]
        }}

        Rules:
        - Return exactly 3 openings
        - Each opening name must be ONLY the exact opening name, nothing else
        - Each reason must be 1-2 short sentences max
        - Be practical
        - No text outside JSON
        """

        profile_ai_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": profile_prompt}],
            temperature=0.3
        )

        profile_ai_text = profile_ai_response.choices[0].message.content.strip()

        print("PROFILE AI RAW RESPONSE:", profile_ai_text)

        try:
            ai_data = json.loads(profile_ai_text)
        except Exception as e:
            print("PROFILE AI JSON ERROR:", e)
            ai_data = {
                "summary": "Could not generate profile summary.",
                "recommendation": "Keep practicing consistently and reviewing your games.",
                "openings": [
                    {
                        "name": "London System",
                        "reason": "Simple and structured, good for building consistency."
                    },
                    {
                        "name": "Italian Game",
                        "reason": "Helps you learn rapid development and attacking ideas."
                    },
                    {
                        "name": "Queen's Gambit",
                        "reason": "Strong for learning classical positional play."
                    }
                ]
            }

        print("PARSED AI DATA:", ai_data)

        if "openings" not in ai_data or not isinstance(ai_data.get("openings"), list):
            ai_data["openings"] = [
                {
                    "name": "London System",
                    "reason": "Simple and structured, good for building consistency."
                },
                {
                    "name": "Italian Game",
                    "reason": "Helps you learn development and basic attacking ideas."
                },
                {
                    "name": "Queen's Gambit",
                    "reason": "Strong for learning classical positional play."
                }
            ]

        try:
            try:
                with open("openings-eco-master.json", "r", encoding="utf-8") as f:
                    library_openings = json.load(f)
            except Exception as e:
                print("LIBRARY LOAD ERROR:", e)
                library_openings = []
        except Exception as e:
            print("LIBRARY LOAD ERROR:", e)
            library_openings = []

        for opening in ai_data.get("openings", []):
            opening_name = opening.get("name", "").strip().lower()

            matched = next(
                (
                    item for item in library_openings
                    if opening_name in item.get("name", "").strip().lower()
                    or item.get("name", "").strip().lower() in opening_name
                ),
                None
            )

            enriched_opening = {
                "name": opening.get("name"),
                "reason": opening.get("reason"),
                "eco": matched.get("eco") if matched else None,
                "level": matched.get("level") if matched else None,
                "style": matched.get("style") if matched else None,
                "family": matched.get("family") if matched else None
            }

            recommended_openings.append(enriched_opening)

        print("FINAL RECOMMENDED OPENINGS:", recommended_openings)

        if not recommended_openings:
            recommended_openings = ai_data.get("openings", [])

        return jsonify({
            "username": profile.get("username"),
            "avatar": profile.get("avatar"),
            "url": profile.get("url"),
            "followers": profile.get("followers"),
            "country": clean_country(profile.get("country")),
            "joined": joined_date,
            "status": profile.get("status"),
            "title": profile.get("title"),
            "ratings": {
                "rapid": rapid_rating,
                "blitz": blitz_rating,
                "bullet": bullet_rating
            },
            "records": {
                "rapid": rapid_record,
                "blitz": blitz_record,
                "bullet": bullet_record
            },
            "summary": ai_data.get("summary"),
            "recommendation": ai_data.get("recommendation"),
            "openings": recommended_openings
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
