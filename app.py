from flask_cors import CORS
from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI
import os
import json
import requests
import re
from datetime import datetime
from urllib.parse import urlparse, unquote

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

def opening_stats_to_list(opening_stats):
    openings = []

    for name, stats in opening_stats.items():
        openings.append({
            "opening": name,
            "games": stats["games"],
            "wins": stats["wins"],
            "draws": stats["draws"],
            "losses": stats["losses"],
            "score_percentage": calculate_score_percentage(stats),
            "as_white": stats["as_white"],
            "as_black": stats["as_black"]
        })

    return openings

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
        opening_stats = {}

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

            opening_name = extract_opening_name(game.get("pgn", ""))

            if opening_name not in opening_stats:
                opening_stats[opening_name] = {
                    "games": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "as_white": 0,
                    "as_black": 0
                }

            stats = opening_stats[opening_name]
            stats["games"] += 1
            stats[outcome_key] += 1

            if color == "white":
                stats["as_white"] += 1
            else:
                stats["as_black"] += 1

        openings = opening_stats_to_list(opening_stats)
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

        recommended_study = [
            {
                "opening": opening["opening"],
                "reason": f"Your score is {opening['score_percentage']}% over {opening['games']} games."
            }
            for opening in weak_openings
            if opening["games"] > 0
        ][:3]

        return jsonify({
            "username": username,
            "games_analyzed": overall["wins"] + overall["draws"] + overall["losses"],
            "overall": overall,
            "white_games": white_games,
            "black_games": black_games,
            "most_played_openings": most_played_openings,
            "top_openings": top_openings,
            "weak_openings": weak_openings,
            "recommended_study": recommended_study
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
