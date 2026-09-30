from flask import Flask, request, jsonify, render_template_string, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
import secrets

app = Flask(__name__)

BASE = Path(__file__).resolve().parent
DB = BASE / "gamehub.db"
UPLOADS = BASE / "uploads"

UPLOADS.mkdir(exist_ok=True)

TOKENS = {}

ALLOWED_IMAGES = {
    "png",
    "jpg",
    "jpeg",
    "webp",
    "gif"
}


# =========================================================
# DATABASE
# =========================================================

def db():

    connection = sqlite3.connect(DB)

    connection.row_factory = sqlite3.Row

    return connection


def init_database():

    connection = db()

    connection.executescript("""

        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL,

            is_admin INTEGER DEFAULT 0,

            created_at TEXT NOT NULL

        );


        CREATE TABLE IF NOT EXISTS games (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT NOT NULL,

            description TEXT DEFAULT '',

            category TEXT DEFAULT 'Other',

            image TEXT DEFAULT '',

            game_url TEXT DEFAULT '',

            is_closed INTEGER DEFAULT 0,

            closed_until TEXT DEFAULT NULL,

            created_at TEXT NOT NULL

        );

    """)

    # -----------------------------------------------------
    # ADMIN
    # -----------------------------------------------------

    admin = connection.execute(
        """
        SELECT id
        FROM users
        WHERE email=?
        """,
        ("admin@gamehub.local",)
    ).fetchone()


    if not admin:

        connection.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password,
                is_admin,
                created_at
            )

            VALUES (?, ?, ?, ?, ?)
            """,

            (
                "Admin",

                "admin@gamehub.local",

                generate_password_hash(
                    "Admin123!"
                ),

                1,

                datetime.utcnow().isoformat()
            )
        )


    # -----------------------------------------------------
    # 100 GAMES
    # -----------------------------------------------------

    count = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM games
        """
    ).fetchone()["count"]


    if count == 0:

        categories = [

            "Action",

            "Adventure",

            "Racing",

            "Sports",

            "RPG",

            "Sandbox"

        ]


        special_games = [

            (
                "GTA VI",

                "Grand Theft Auto VI",

                "Action"
            ),

            (
                "GTA V",

                "Grand Theft Auto V",

                "Action"
            ),

            (
                "Minecraft",

                "Build and explore",

                "Sandbox"
            ),

            (
                "EA SPORTS FC 26",

                "Football game",

                "Sports"
            ),

            (
                "Roblox",

                "Play and create",

                "Adventure"
            ),

            (
                "Fortnite",

                "Battle Royale",

                "Action"
            ),

            (
                "Red Dead Redemption 2",

                "Western open world",

                "Adventure"
            ),

            (
                "Cyberpunk 2077",

                "Futuristic RPG",

                "RPG"
            ),

            (
                "Forza Horizon 5",

                "Open world racing",

                "Racing"
            ),

            (
                "Need for Speed Heat",

                "Street racing",

                "Racing"
            )

        ]


        for i in range(100):

            if i < len(special_games):

                title = special_games[i][0]

                description = special_games[i][1]

                category = special_games[i][2]

            else:

                title = f"Game {i + 1}"

                description = (
                    f"GameHub game #{i + 1}"
                )

                category = categories[
                    i % len(categories)
                ]


            connection.execute(
                """
                INSERT INTO games
                (
                    title,
                    description,
                    category,
                    created_at
                )

                VALUES (?, ?, ?, ?)
                """,

                (
                    title,

                    description,

                    category,

                    datetime.utcnow().isoformat()
                )
            )


    connection.commit()

    connection.close()


# =========================================================
# AUTH
# =========================================================

def current_user(admin=False):

    authorization = request.headers.get(
        "Authorization",
        ""
    )


    token = authorization.replace(
        "Bearer ",
        ""
    )


    user_id = TOKENS.get(token)


    if not user_id:

        return None


    connection = db()


    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE id=?
        """,

        (user_id,)
    ).fetchone()


    connection.close()


    if not user:

        return None


    if admin and not user["is_admin"]:

        return None


    return user


# =========================================================
# MAIN PAGE
# =========================================================

@app.route("/")
def home():

    return render_template_string(
        HTML
    )


# =========================================================
# ADMIN PAGE
# =========================================================

@app.route("/admin")
def admin_page():

    return render_template_string(
        ADMIN_HTML
    )


# =========================================================
# UPLOADS
# =========================================================

@app.route("/uploads/<path:filename>")
def uploads(filename):

    return send_from_directory(
        UPLOADS,
        filename
    )


# =========================================================
# GET GAMES
# =========================================================

@app.route("/api/games")
def get_games():

    connection = db()


    games = connection.execute(
        """
        SELECT *
        FROM games
        ORDER BY id DESC
        """
    ).fetchall()


    connection.close()


    now = datetime.utcnow()


    result = []


    for game in games:

        item = dict(game)


        if (
            item["is_closed"]
            and
            item["closed_until"]
        ):

            try:

                until = datetime.fromisoformat(
                    item["closed_until"]
                )


                if until <= now:

                    connection = db()


                    connection.execute(
                        """
                        UPDATE games

                        SET
                            is_closed=0,
                            closed_until=NULL

                        WHERE id=?
                        """,

                        (item["id"],)
                    )


                    connection.commit()

                    connection.close()


                    item["is_closed"] = 0

                    item["closed_until"] = None


            except ValueError:

                pass


        result.append(item)


    return jsonify(result)


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/api/register",
    methods=["POST"]
)
def register():

    data = request.json or {}


    name = data.get(
        "name",
        ""
    ).strip()


    email = data.get(
        "email",
        ""
    ).strip().lower()


    password = data.get(
        "password",
        ""
    )


    if not name:

        return jsonify({
            "error":
                "Գրիր անունը։"
        }), 400


    if not email:

        return jsonify({
            "error":
                "Գրիր email-ը։"
        }), 400


    if len(password) < 6:

        return jsonify({
            "error":
                "Գաղտնաբառը պետք է լինի առնվազն 6 նիշ։"
        }), 400


    connection = db()


    try:

        cursor = connection.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password,
                created_at
            )

            VALUES (?, ?, ?, ?)
            """,

            (
                name,

                email,

                generate_password_hash(
                    password
                ),

                datetime.utcnow().isoformat()
            )
        )


        connection.commit()


        user_id = cursor.lastrowid


    except sqlite3.IntegrityError:

        connection.close()


        return jsonify({
            "error":
                "Այս email-ով հաշիվ արդեն կա։"
        }), 409


    connection.close()


    token = secrets.token_urlsafe(32)


    TOKENS[token] = user_id


    return jsonify({

        "token": token,

        "user": {

            "id": user_id,

            "name": name,

            "email": email,

            "is_admin": 0

        }

    })


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/api/login",
    methods=["POST"]
)
def login():

    data = request.json or {}


    email = data.get(
        "email",
        ""
    ).strip().lower()


    password = data.get(
        "password",
        ""
    )


    connection = db()


    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE email=?
        """,

        (email,)
    ).fetchone()


    connection.close()


    if not user:

        return jsonify({
            "error":
                "Սխալ email կամ գաղտնաբառ։"
        }), 401


    if not check_password_hash(
        user["password"],
        password
    ):

        return jsonify({
            "error":
                "Սխալ email կամ գաղտնաբառ։"
        }), 401


    token = secrets.token_urlsafe(32)


    TOKENS[token] = user["id"]


    return jsonify({

        "token": token,

        "user": {

            "id": user["id"],

            "name": user["name"],

            "email": user["email"],

            "is_admin":
                user["is_admin"]

        }

    })


# =========================================================
# CURRENT USER
# =========================================================

@app.route("/api/me")
def me():

    user = current_user()


    if not user:

        return jsonify({
            "error":
                "Մուտք չկա։"
        }), 401


    return jsonify({

        "user": {

            "id": user["id"],

            "name": user["name"],

            "email": user["email"],

            "is_admin":
                user["is_admin"]

        }

    })


# =========================================================
# ADD GAME
# =========================================================

@app.route(
    "/api/admin/games",
    methods=["POST"]
)
def add_game():

    user = current_user(
        admin=True
    )


    if not user:

        return jsonify({
            "error":
                "Admin մուտք է պետք։"
        }), 403


    title = request.form.get(
        "title",
        ""
    ).strip()


    description = request.form.get(
        "description",
        ""
    )


    category = request.form.get(
        "category",
        "Other"
    )


    game_url = request.form.get(
        "game_url",
        ""
    )


    if not title:

        return jsonify({
            "error":
                "Խաղի անունը պարտադիր է։"
        }), 400


    image = ""


    file = request.files.get(
        "image"
    )


    if file and file.filename:

        extension = file.filename.rsplit(
            ".",
            1
        )[-1].lower()


        if extension not in ALLOWED_IMAGES:

            return jsonify({
                "error":
                    "Նկարի այս ձևաչափը թույլատրված չէ։"
            }), 400


        filename = (
            secrets.token_hex(10)
            +
            "."
            +
            extension
        )


        file.save(
            UPLOADS / filename
        )


        image = (
            "/uploads/"
            +
            filename
        )


    connection = db()


    cursor = connection.execute(
        """
        INSERT INTO games
        (
            title,
            description,
            category,
            image,
            game_url,
            created_at
        )

        VALUES (?, ?, ?, ?, ?, ?)
        """,

        (
            title,

            description,

            category,

            image,

            game_url,

            datetime.utcnow().isoformat()
        )
    )


    connection.commit()


    game_id = cursor.lastrowid


    connection.close()


    return jsonify({

        "ok": True,

        "id": game_id

    })


# =========================================================
# EDIT GAME
# =========================================================

@app.route(
    "/api/admin/games/<int:game_id>",
    methods=["PUT"]
)
def edit_game(game_id):

    user = current_user(
        admin=True
    )


    if not user:

        return jsonify({
            "error":
                "Admin մուտք է պետք։"
        }), 403


    data = request.json or {}


    title = data.get(
        "title",
        ""
    )


    description = data.get(
        "description",
        ""
    )


    category = data.get(
        "category",
        "Other"
    )


    game_url = data.get(
        "game_url",
        ""
    )


    connection = db()


    connection.execute(
        """
        UPDATE games

        SET
            title=?,
            description=?,
            category=?,
            game_url=?

        WHERE id=?
        """,

        (
            title,

            description,

            category,

            game_url,

            game_id
        )
    )


    connection.commit()

    connection.close()


    return jsonify({
        "ok": True
    })


# =========================================================
# DELETE GAME
# =========================================================

@app.route(
    "/api/admin/games/<int:game_id>",
    methods=["DELETE"]
)
def delete_game(game_id):

    user = current_user(
        admin=True
    )


    if not user:

        return jsonify({
            "error":
                "Admin մուտք է պետք։"
        }), 403


    connection = db()


    game = connection.execute(
        """
        SELECT image
        FROM games
        WHERE id=?
        """,

        (game_id,)
    ).fetchone()


    connection.execute(
        """
        DELETE FROM games
        WHERE id=?
        """,

        (game_id,)
    )


    connection.commit()

    connection.close()


    return jsonify({
        "ok": True
    })


# =========================================================
# CLOSE GAME
# =========================================================

@app.route(
    "/api/admin/games/<int:game_id>/close",
    methods=["POST"]
)
def close_game(game_id):

    user = current_user(
        admin=True
    )


    if not user:

        return jsonify({
            "error":
                "Admin մուտք է պետք։"
        }), 403


    data = request.json or {}


    minutes = int(
        data.get(
            "minutes",
            60
        )
    )


    until = (
        datetime.utcnow()
        +
        timedelta(
            minutes=max(
                1,
                minutes
            )
        )
    ).isoformat()


    connection = db()


    connection.execute(
        """
        UPDATE games

        SET
            is_closed=1,
            closed_until=?

        WHERE id=?
        """,

        (
            until,

            game_id
        )
    )


    connection.commit()

    connection.close()


    return jsonify({

        "ok": True,

        "closed_until":
            until

    })


# =========================================================
# OPEN GAME
# =========================================================

@app.route(
    "/api/admin/games/<int:game_id>/open",
    methods=["POST"]
)
def open_game(game_id):

    user = current_user(
        admin=True
    )


    if not user:

        return jsonify({
            "error":
                "Admin մուտք է պետք։"
        }), 403


    connection = db()


    connection.execute(
        """
        UPDATE games

        SET
            is_closed=0,
            closed_until=NULL

        WHERE id=?
        """,

        (game_id,)
    )


    connection.commit()

    connection.close()


    return jsonify({
        "ok": True
    })


# =========================================================
# HTML
# =========================================================

HTML = r"""

<!DOCTYPE html>

<html lang="hy">

<head>

<meta charset="UTF-8">

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>GameHub</title>

<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">

<style>

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

html {
    scroll-behavior: smooth;
}

body {
    font-family: 'Poppins', sans-serif;
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    background-attachment: fixed;
    color: #e0e0e0;
    min-height: 100vh;
}

header {
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 6%;
    background: rgba(10, 10, 20, 0.95);
    backdrop-filter: blur(10px);
    border-bottom: 2px solid rgba(102, 126, 234, 0.3);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    position: sticky;
    top: 0;
    z-index: 100;
}

.logo {
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -1px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

nav {
    display: flex;
    gap: 30px;
    align-items: center;
}

nav a {
    color: #e0e0e0;
    text-decoration: none;
    font-weight: 500;
    font-size: 15px;
    transition: all 0.3s ease;
    position: relative;
}

nav a::after {
    content: '';
    position: absolute;
    bottom: -5px;
    left: 0;
    width: 0;
    height: 2px;
    background: linear-gradient(90deg, #667eea, #764ba2);
    transition: width 0.3s ease;
}

nav a:hover::after {
    width: 100%;
}

#account {
    color: #667eea;
    font-weight: 600;
    font-size: 14px;
}

.hero {
    text-align: center;
    padding: 100px 20px 80px;
    background: linear-gradient(180deg, rgba(102, 126, 234, 0.1) 0%, transparent 100%);
    position: relative;
    overflow: hidden;
}

.hero::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 500px;
    height: 500px;
    background: radial-gradient(circle, rgba(102, 126, 234, 0.1) 0%, transparent 70%);
    border-radius: 50%;
}

.hero h1 {
    font-size: 56px;
    font-weight: 800;
    margin: 0 0 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    position: relative;
    z-index: 1;
    letter-spacing: -2px;
}

.hero p {
    color: #a0a0a0;
    font-size: 18px;
    position: relative;
    z-index: 1;
    font-weight: 500;
}

.auth {
    max-width: 1000px;
    margin: 50px auto;
    padding: 30px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 30px;
}

.box {
    background: rgba(20, 20, 40, 0.8);
    backdrop-filter: blur(20px);
    padding: 35px;
    border-radius: 20px;
    border: 1px solid rgba(102, 126, 234, 0.2);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    transition: all 0.3s ease;
}

.box:hover {
    border-color: rgba(102, 126, 234, 0.5);
    box-shadow: 0 15px 45px rgba(102, 126, 234, 0.15);
    transform: translateY(-5px);
}

.box h2 {
    font-size: 22px;
    margin-bottom: 25px;
    color: #e0e0e0;
    font-weight: 700;
}

input, select {
    width: 100%;
    padding: 14px 16px;
    margin: 10px 0;
    border-radius: 12px;
    border: 1px solid rgba(102, 126, 234, 0.2);
    background: rgba(10, 10, 20, 0.6);
    color: #e0e0e0;
    font-family: 'Poppins', sans-serif;
    font-size: 14px;
    transition: all 0.3s ease;
}

input:focus, select:focus {
    outline: none;
    border-color: #667eea;
    background: rgba(10, 10, 20, 0.9);
    box-shadow: 0 0 20px rgba(102, 126, 234, 0.2);
}

input::placeholder {
    color: #666;
}

button {
    width: 100%;
    padding: 14px 16px;
    margin: 10px 0;
    border-radius: 12px;
    border: none;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    cursor: pointer;
    font-weight: 600;
    font-family: 'Poppins', sans-serif;
    font-size: 15px;
    transition: all 0.3s ease;
    box-shadow: 0 5px 20px rgba(102, 126, 234, 0.3);
}

button:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 30px rgba(102, 126, 234, 0.5);
}

button:active {
    transform: translateY(0);
}

.tools {
    max-width: 1200px;
    margin: 40px auto;
    padding: 0 30px;
    display: flex;
    gap: 15px;
    flex-wrap: wrap;
}

#search {
    flex: 1;
    min-width: 250px;
}

#category {
    min-width: 150px;
}

.games {
    max-width: 1300px;
    margin: 30px auto;
    padding: 0 30px 50px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 25px;
}

.card {
    background: rgba(20, 20, 40, 0.8);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(102, 126, 234, 0.2);
    border-radius: 16px;
    padding: 18px;
    transition: all 0.3s ease;
    cursor: pointer;
    overflow: hidden;
}

.card:hover {
    transform: translateY(-8px);
    border-color: rgba(102, 126, 234, 0.5);
    box-shadow: 0 15px 40px rgba(102, 126, 234, 0.2);
}

.card img {
    width: 100%;
    height: 160px;
    object-fit: cover;
    border-radius: 12px;
    margin-bottom: 12px;
}

.placeholder {
    height: 160px;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
    border-radius: 12px;
    display: grid;
    place-items: center;
    font-size: 50px;
    margin-bottom: 12px;
    border: 1px solid rgba(102, 126, 234, 0.2);
}

.tag {
    display: inline-block;
    margin-bottom: 12px;
    padding: 6px 12px;
    border-radius: 20px;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
    color: #667eea;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid rgba(102, 126, 234, 0.3);
}

.card h3 {
    font-size: 18px;
    margin: 12px 0 8px;
    color: #e0e0e0;
    font-weight: 700;
}

.card p {
    font-size: 13px;
    color: #a0a0a0;
    margin-bottom: 15px;
    line-height: 1.5;
}

.card button {
    width: 100%;
    margin-top: 10px;
}

.closed {
    opacity: 0.6;
}

.closed b {
    display: block;
    color: #ff6b6b;
    font-size: 13px;
    margin-top: 10px;
}

@media(max-width:768px) {

    .auth {
        grid-template-columns: 1fr;
        margin: 30px auto;
        padding: 20px;
    }

    .tools {
        flex-direction: column;
        padding: 0 20px;
    }

    .games {
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        padding: 0 20px 30px;
    }

    .hero h1 {
        font-size: 36px;
    }

    header {
        padding: 0 4%;
        height: 70px;
    }

    nav {
        gap: 15px;
    }

    .logo {
        font-size: 22px;
    }

}

</style>

</head>

<body>

<header>

<div class="logo">
🎮 GAMEHUB
</div>

<nav>

<a href="/">
Խաղեր
</a>

<a href="/admin">
Admin
</a>

</nav>

<div id="account"></div>

</header>

<section class="hero">

<h1>
100 ԽԱՂ՝ ՄԵԿ ԿԱՅՔՈՒՄ
</h1>

<p>
Գտիր քո սիրած խաղը
</p>

</section>

<section class="auth">

<div class="box">

<h2>
Մուտք
</h2>

<input id="loginEmail" placeholder="Email">

<input id="loginPassword" type="password" placeholder="Գաղտնաբառ">

<button onclick="login()">
Մուտք գործել
</button>

</div>

<div class="box">

<h2>
Գրանցում
</h2>

<input id="registerName" placeholder="Անուն">

<input id="registerEmail" placeholder="Email">

<input id="registerPassword" type="password" placeholder="Գաղտնաբառ">

<button onclick="register()">
Գրանցվել
</button>

</div>

</section>

<section class="tools">

<input id="search" placeholder="🔎 Փնտրել խաղ..." oninput="renderGames()">

<select id="category" onchange="renderGames()">
<option value="">Բոլորը</option>
</select>

</section>

<section id="games" class="games"></section>

<script>

let games = [];

function token() {
    return localStorage.getItem("gamehub_token") || "";
}

async function loadGames() {
    const response = await fetch("/api/games");
    games = await response.json();
    const categories = [...new Set(games.map(game => game.category))];
    document.getElementById("category").innerHTML = '<option value="">Բոլորը</option>' + categories.map(category => `<option value="${category}">${category}</option>`).join("");
    renderGames();
}

function renderGames() {
    const search = document.getElementById("search").value.toLowerCase();
    const category = document.getElementById("category").value;
    const filtered = games.filter(game => (!search || game.title.toLowerCase().includes(search)) && (!category || game.category === category));
    document.getElementById("games").innerHTML = filtered.map(game => `
        <article class="card ${game.is_closed ? "closed" : ""}">
            ${game.image ? `<img src="${game.image}">` : `<div class="placeholder">🎮</div>`}
            <span class="tag">${game.category}</span>
            <h3>${game.title}</h3>
            <p>${game.description}</p>
            ${game.is_closed ? `<b>🔒 Ժամանակավորապես փակ է</b>` : `<button onclick="playGame(${game.id})">Խաղալ</button>`}
        </article>
    `).join("");
}

function playGame(id) {
    const game = games.find(item => item.id === id);
    if (!game) return;
    if (game.game_url) {
        window.open(game.game_url, "_blank");
    } else {
        alert("Այս խաղի հղումը դեռ չկա։");
    }
}

async function register() {
    const response = await fetch("/api/register", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            name: document.getElementById("registerName").value,
            email: document.getElementById("registerEmail").value,
            password: document.getElementById("registerPassword").value
        })
    });
    const data = await response.json();
    if (!response.ok) {
        alert(data.error);
        return;
    }
    localStorage.setItem("gamehub_token", data.token);
    alert("Գրանցումը հաջողվեց։");
}

async function login() {
    const response = await fetch("/api/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            email: document.getElementById("loginEmail").value,
            password: document.getElementById("loginPassword").value
        })
    });
    const data = await response.json();
    if (!response.ok) {
        alert(data.error);
        return;
    }
    localStorage.setItem("gamehub_token", data.token);
    document.getElementById("account").textContent = "👤 " + data.user.name;
    alert("Մուտքը հաջողվեց։");
}

loadGames();

</script>

</body>

</html>

"""


# =========================================================
# ADMIN HTML
# =========================================================

ADMIN_HTML = r"""

<!DOCTYPE html>

<html lang="hy">

<head>

<meta charset="UTF-8">

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>GameHub Admin</title>

<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">

<style>

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: 'Poppins', sans-serif;
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    background-attachment: fixed;
    color: #e0e0e0;
    min-height: 100vh;
}

header {
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 6%;
    background: rgba(10, 10, 20, 0.95);
    backdrop-filter: blur(10px);
    border-bottom: 2px solid rgba(102, 126, 234, 0.3);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    position: sticky;
    top: 0;
    z-index: 100;
}

.logo {
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -1px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

a {
    color: #e0e0e0;
    text-decoration: none;
    font-weight: 600;
    transition: color 0.3s ease;
}

a:hover {
    color: #667eea;
}

main {
    max-width: 1200px;
    margin: 40px auto;
    padding: 0 30px 50px;
}

.panel {
    background: rgba(20, 20, 40, 0.8);
    backdrop-filter: blur(20px);
    padding: 40px;
    border-radius: 20px;
    border: 1px solid rgba(102, 126, 234, 0.2);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.panel h1 {
    font-size: 32px;
    margin-bottom: 10px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

#status {
    font-size: 16px;
    margin-bottom: 30px;
    padding: 12px 16px;
    background: rgba(102, 126, 234, 0.1);
    border-left: 3px solid #667eea;
    border-radius: 8px;
    font-weight: 500;
}

.panel h2 {
    font-size: 22px;
    margin: 30px 0 20px;
    color: #e0e0e0;
}

input, select {
    width: 100%;
    padding: 14px 16px;
    margin: 10px 0;
    border-radius: 12px;
    border: 1px solid rgba(102, 126, 234, 0.2);
    background: rgba(10, 10, 20, 0.6);
    color: #e0e0e0;
    font-family: 'Poppins', sans-serif;
    font-size: 14px;
    transition: all 0.3s ease;
}

input:focus, select:focus {
    outline: none;
    border-color: #667eea;
    background: rgba(10, 10, 20, 0.9);
    box-shadow: 0 0 20px rgba(102, 126, 234, 0.2);
}

input::placeholder {
    color: #666;
}

button {
    width: 100%;
    padding: 14px 16px;
    margin: 10px 0;
    border-radius: 12px;
    border: none;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    cursor: pointer;
    font-weight: 600;
    font-family: 'Poppins', sans-serif;
    font-size: 15px;
    transition: all 0.3s ease;
    box-shadow: 0 5px 20px rgba(102, 126, 234, 0.3);
}

button:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 30px rgba(102, 126, 234, 0.5);
}

.game {
    margin-top: 20px;
    padding: 20px;
    background: rgba(30, 30, 50, 0.8);
    border: 1px solid rgba(102, 126, 234, 0.2);
    border-radius: 16px;
    transition: all 0.3s ease;
}

.game:hover {
    border-color: rgba(102, 126, 234, 0.5);
    box-shadow: 0 8px 20px rgba(102, 126, 234, 0.1);
}

.game h3 {
    font-size: 20px;
    margin-bottom: 8px;
    color: #e0e0e0;
}

.game p {
    font-size: 14px;
    color: #a0a0a0;
    margin-bottom: 8px;
}

.game small {
    color: #667eea;
    font-weight: 600;
}

.actions {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-top: 15px;
}

button.delete {
    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
}

button.delete:hover {
    box-shadow: 0 10px 30px rgba(255, 107, 107, 0.4);
}

button.open {
    background: linear-gradient(135deg, #51cf66 0%, #37b24d 100%);
}

button.open:hover {
    box-shadow: 0 10px 30px rgba(81, 207, 102, 0.4);
}

@media(max-width:768px) {

    main {
        padding: 0 20px 30px;
        margin: 20px auto;
    }

    .panel {
        padding: 25px;
    }

    .actions {
        grid-template-columns: 1fr;
    }

    header {
        padding: 0 4%;
        height: 70px;
    }

    .logo {
        font-size: 22px;
    }

}

</style>

</head>

<body>

<header>

<div class="logo">
🎮 GAMEHUB ADMIN
</div>

<a href="/">
Կայք
</a>

</header>

<main>

<div class="panel">

<h1>Admin Panel</h1>

<p id="status">
Ստուգում...
</p>

<h2>
Ավելացնել խաղ
</h2>

<input id="title" placeholder="Խաղի անուն">

<input id="description" placeholder="Նկարագրություն">

<input id="category" placeholder="Կատեգորիա">

<input id="gameUrl" placeholder="Խաղի հղում">

<input id="image" type="file" accept="image/*">

<button onclick="addGame()">
➕ Ավելացնել խաղ
</button>

</div>

<h2 style="margin-top: 40px; margin-bottom: 25px;">
Խաղերի կառավարում
</h2>

<div id="adminGames"></div>

</main>

<script>

function token() {
    return localStorage.getItem("gamehub_token") || "";
}

async function checkAdmin() {
    const response = await fetch("/api/me", {
        headers: {"Authorization": "Bearer " + token()}
    });
    if (!response.ok) {
        document.getElementById("status").textContent = "❌ Մուտք գործիր Admin հաշվով։";
        return;
    }
    const data = await response.json();
    if (!data.user.is_admin) {
        document.getElementById("status").textContent = "❌ Դու Admin չես։";
        return;
    }
    document.getElementById("status").textContent = "✅ Admin՝ " + data.user.name;
    loadAdminGames();
}

async function loadAdminGames() {
    const response = await fetch("/api/games");
    const games = await response.json();
    document.getElementById("adminGames").innerHTML = games.map(game => `
        <div class="game">
            <h3>${game.title}</h3>
            <p>${game.description}</p>
            <small>${game.category}</small>
            <br><br>
            ${game.is_closed ? "🔒 ՓԱԿ" : "🟢 ԲԱՑ"}
            <div class="actions">
                <button onclick="editGame(${game.id})">✏️ Խմբագրել</button>
                ${game.is_closed ? `<button class="open" onclick="openGame(${game.id})">🔓 Բացել</button>` : `<button onclick="closeGame(${game.id})">🔒 Փակել</button>`}
                <button class="delete" onclick="deleteGame(${game.id})">🗑️ Ջնջել</button>
            </div>
        </div>
    `).join("");
}

async function addGame() {
    const form = new FormData();
    form.append("title", document.getElementById("title").value);
    form.append("description", document.getElementById("description").value);
    form.append("category", document.getElementById("category").value || "Other");
    form.append("game_url", document.getElementById("gameUrl").value);
    const image = document.getElementById("image").files[0];
    if (image) form.append("image", image);
    const response = await fetch("/api/admin/games", {
        method: "POST",
        headers: {"Authorization": "Bearer " + token()},
        body: form
    });
    const data = await response.json();
    if (!response.ok) {
        alert(data.error);
        return;
    }
    alert("Խաղը ավելացվեց։");
    document.getElementById("title").value = "";
    document.getElementById("description").value = "";
    document.getElementById("category").value = "";
    document.getElementById("gameUrl").value = "";
    document.getElementById("image").value = "";
    loadAdminGames();
}

async function deleteGame(id) {
    if (!confirm("Ջնջե՞լ խաղը։")) return;
    await fetch("/api/admin/games/" + id, {
        method: "DELETE",
        headers: {"Authorization": "Bearer " + token()}
    });
    loadAdminGames();
}

async function closeGame(id) {
    const minutes = prompt("Քանի՞ րոպե փակել խաղը։", "60");
    if (!minutes) return;
    await fetch("/api/admin/games/" + id + "/close", {
        method: "POST",
        headers: {"Content-Type": "application/json", "Authorization": "Bearer " + token()},
        body: JSON.stringify({minutes: Number(minutes)})
    });
    loadAdminGames();
}

async function openGame(id) {
    await fetch("/api/admin/games/" + id + "/open", {
        method: "POST",
        headers: {"Authorization": "Bearer " + token()}
    });
    loadAdminGames();
}

async function editGame(id) {
    const title = prompt("Նոր անունը:");
    if (title === null) return;
    const description = prompt("Նոր նկարագրությունը:");
    const category = prompt("Նոր կատեգորիան:");
    const gameUrl = prompt("Նոր խաղի հղումը:");
    await fetch("/api/admin/games/" + id, {
        method: "PUT",
        headers: {"Content-Type": "application/json", "Authorization": "Bearer " + token()},
        body: JSON.stringify({title: title, description: description, category: category, game_url: gameUrl})
    });
    loadAdminGames();
}

checkAdmin();

</script>

</body>

</html>

"""


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    init_database()

    print()
    print("===================================")
    print("       GAMEHUB STARTED")
    print("===================================")
    print()
    print("Website:")
    print("http://localhost:5000")
    print()
    print("Admin:")
    print("http://localhost:5000/admin")
    print()
    print("Admin email:")
    print("admin@gamehub.local")
    print()
    print("Admin password:")
    print("Admin123!")
    print()
    print("===================================")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
