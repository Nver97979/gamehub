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

<meta
name="viewport"
content="width=device-width, initial-scale=1.0"
>

<title>
GameHub
</title>

<style>

* {
    box-sizing: border-box;
}

body {

    margin: 0;

    font-family: Arial, sans-serif;

    background:
        #080d19;

    color: white;

}


header {

    height: 70px;

    display: flex;

    align-items: center;

    justify-content:
        space-between;

    padding:
        0 5%;

    background:
        #10182b;

    border-bottom:
        1px solid #293452;

}


.logo {

    font-size:
        25px;

    font-weight:
        900;

}


.logo span {

    color:
        #5d91ff;

}


nav {

    display:
        flex;

    gap:
        20px;

}


nav a {

    color:
        white;

    text-decoration:
        none;

}


.hero {

    text-align:
        center;

    padding:
        80px 20px;

    background:
        linear-gradient(
            135deg,
            #111d46,
            #172d61
        );

}


.hero h1 {

    font-size:
        45px;

    margin:
        0 0 15px;

}


.hero p {

    color:
        #b8c4df;

}


.auth {

    max-width:
        1000px;

    margin:
        30px auto;

    padding:
        20px;

    display:
        grid;

    grid-template-columns:
        1fr 1fr;

    gap:
        20px;

}


.box {

    background:
        #121c32;

    padding:
        20px;

    border-radius:
        15px;

    border:
        1px solid #293654;

}


input,
select,
button {

    width:
        100%;

    padding:
        12px;

    margin:
        6px 0;

    border-radius:
        8px;

    border:
        1px solid #354363;

    background:
        #091122;

    color:
        white;

}


button {

    background:
        #356de8;

    cursor:
        pointer;

    border:
        none;

    font-weight:
        bold;

}


.tools {

    max-width:
        1200px;

    margin:
        20px auto;

    padding:
        0 20px;

    display:
        flex;

    gap:
        10px;

}


.games {

    max-width:
        1200px;

    margin:
        auto;

    padding:
        20px;

    display:
        grid;

    grid-template-columns:
        repeat(
            auto-fill,
            minmax(
                220px,
                1fr
            )
        );

    gap:
        18px;

}


.card {

    background:
        #121c32;

    border:
        1px solid #293654;

    border-radius:
        15px;

    padding:
        15px;

}


.card img {

    width:
        100%;

    height:
        140px;

    object-fit:
        cover;

    border-radius:
        10px;

}


.placeholder {

    height:
        140px;

    background:
        #202c47;

    border-radius:
        10px;

    display:
        grid;

    place-items:
        center;

    font-size:
        45px;

}


.tag {

    display:
        inline-block;

    margin-top:
        10px;

    padding:
        5px 9px;

    border-radius:
        20px;

    background:
        #24365e;

    color:
        #abc5ff;

    font-size:
        12px;

}


.closed {

    opacity:
        0.5;

}


@media(max-width:700px) {

    .auth {

        grid-template-columns:
            1fr;

    }

    .tools {

        flex-direction:
            column;

    }

    .hero h1 {

        font-size:
            30px;

    }

}

</style>

</head>


<body>


<header>

<div class="logo">
GAME<span>HUB</span>
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

<input
id="loginEmail"
placeholder="Email"
>


<input
id="loginPassword"
type="password"
placeholder="Գաղտնաբառ"
>


<button onclick="login()">
Մուտք գործել
</button>

</div>


<div class="box">

<h2>
Գրանցում
</h2>

<input
id="registerName"
placeholder="Անուն"
>


<input
id="registerEmail"
placeholder="Email"
>


<input
id="registerPassword"
type="password"
placeholder="Գաղտնաբառ"
>


<button onclick="register()">
Գրանցվել
</button>

</div>


</section>


<section class="tools">

<input
id="search"
placeholder="🔎 Փնտրել խաղ..."
oninput="renderGames()"
>


<select
id="category"
onchange="renderGames()"
>

<option value="">
Բոլորը
</option>

</select>

</section>


<section
id="games"
class="games"
></section>


<script>

let games = [];


function token() {

    return localStorage.getItem(
        "gamehub_token"
    ) || "";

}


async function loadGames() {

    const response =
        await fetch(
            "/api/games"
        );


    games =
        await response.json();


    const categories =
        [
            ...new Set(
                games.map(
                    game =>
                        game.category
                )
            )
        ];


    document.getElementById(
        "category"
    ).innerHTML =
        `
        <option value="">
            Բոլորը
        </option>
        `

        +

        categories.map(
            category =>
                `
                <option value="${category}">
                    ${category}
                </option>
                `
        ).join("");


    renderGames();

}


function renderGames() {

    const search =
        document.getElementById(
            "search"
        ).value.toLowerCase();


    const category =
        document.getElementById(
            "category"
        ).value;


    const filtered =
        games.filter(
            game =>

                (
                    !search ||

                    game.title
                        .toLowerCase()
                        .includes(search)
                )

                &&

                (
                    !category ||

                    game.category ===
                        category
                )
        );


    document.getElementById(
        "games"
    ).innerHTML =

        filtered.map(
            game => `

            <article
                class="card
                ${game.is_closed
                    ? "closed"
                    : ""}"
            >

                ${
                    game.image

                    ?

                    `
                    <img
                        src="${game.image}"
                    >
                    `

                    :

                    `
                    <div
                        class="placeholder"
                    >
                        🎮
                    </div>
                    `
                }


                <span class="tag">
                    ${game.category}
                </span>


                <h3>
                    ${game.title}
                </h3>


                <p>
                    ${game.description}
                </p>


                ${
                    game.is_closed

                    ?

                    `
                    <b>
                        🔒 Ժամանակավորապես փակ է
                    </b>
                    `

                    :

                    `
                    <button
                        onclick="playGame(${game.id})"
                    >
                        Խաղալ
                    </button>
                    `
                }

            </article>

            `
        ).join("");

}


function playGame(id) {

    const game =
        games.find(
            item =>
                item.id === id
        );


    if (!game) return;


    if (game.game_url) {

        window.open(
            game.game_url,
            "_blank"
        );

    }

    else {

        alert(
            "Այս խաղի հղումը դեռ չկա։"
        );

    }

}


async function register() {

    const response =
        await fetch(
            "/api/register",
            {

                method:
                    "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify({

                        name:
                            document.getElementById(
                                "registerName"
                            ).value,

                        email:
                            document.getElementById(
                                "registerEmail"
                            ).value,

                        password:
                            document.getElementById(
                                "registerPassword"
                            ).value

                    })

            }
        );


    const data =
        await response.json();


    if (!response.ok) {

        alert(data.error);

        return;

    }


    localStorage.setItem(
        "gamehub_token",
        data.token
    );


    alert(
        "Գրանցումը հաջողվեց։"
    );

}


async function login() {

    const response =
        await fetch(
            "/api/login",
            {

                method:
                    "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify({

                        email:
                            document.getElementById(
                                "loginEmail"
                            ).value,

                        password:
                            document.getElementById(
                                "loginPassword"
                            ).value

                    })

            }
        );


    const data =
        await response.json();


    if (!response.ok) {

        alert(data.error);

        return;

    }


    localStorage.setItem(
        "gamehub_token",
        data.token
    );


    document.getElementById(
        "account"
    ).textContent =
        "👤 " +
        data.user.name;


    alert(
        "Մուտքը հաջողվեց։"
    );

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

<meta
name="viewport"
content="width=device-width, initial-scale=1.0"
>

<title>
GameHub Admin
</title>

<style>

* {
    box-sizing:
        border-box;
}


body {

    margin:
        0;

    background:
        #080d19;

    color:
        white;

    font-family:
        Arial;

}


header {

    height:
        70px;

    display:
        flex;

    align-items:
        center;

    justify-content:
        space-between;

    padding:
        0 5%;

    background:
        #10182b;

}


.logo {

    font-size:
        24px;

    font-weight:
        bold;

}


.logo span {

    color:
        #5d91ff;

}


a {

    color:
        white;

    text-decoration:
        none;

}


main {

    max-width:
        1100px;

    margin:
        auto;

    padding:
        30px 20px;

}


.panel {

    background:
        #121c32;

    padding:
        25px;

    border-radius:
        15px;

}


input,
button {

    width:
        100%;

    padding:
        12px;

    margin:
        6px 0;

    border-radius:
        8px;

    border:
        1px solid #354363;

    background:
        #091122;

    color:
        white;

}


button {

    background:
        #356de8;

    border:
        none;

    cursor:
        pointer;

}


.game {

    margin-top:
        10px;

    padding:
        15px;

    background:
        #121c32;

    border:
        1px solid #293654;

    border-radius:
        12px;

}


.actions {

    display:
        grid;

    grid-template-columns:
        repeat(
            3,
            1fr
        );

    gap:
        8px;

}


.delete {

    background:
        #b6384c;

}


.open {

    background:
        #23885a;

}


@media(max-width:700px) {

    .actions {

        grid-template-columns:
            1fr;

    }

}

</style>

</head>


<body>


<header>

<div class="logo">
GAME<span>HUB</span> ADMIN
</div>


<a href="/">
Հետ
</a>

</header>


<main>


<div class="panel">

<h1>
Admin Panel
</h1>


<p id="status">
Ստուգում...
</p>


<h2>
Ավելացնել խաղ
</h2>


<input
id="title"
placeholder="Խաղի անուն"
>


<input
id="description"
placeholder="Նկարագրություն"
>


<input
id="category"
placeholder="Կատեգորիա"
>


<input
id="gameUrl"
placeholder="Խաղի հղում"
>


<input
id="image"
type="file"
accept="image/*"
>


<button onclick="addGame()">
➕ Ավելացնել խաղ
</button>


</div>


<h2>
Խաղերի կառավարում
</h2>


<div id="adminGames"></div>


</main>


<script>


function token() {

    return localStorage.getItem(
        "gamehub_token"
    ) || "";

}


async function checkAdmin() {

    const response =
        await fetch(
            "/api/me",
            {
                headers: {
                    Authorization:
                        "Bearer " + token()
                }
            }
        );


    if (!response.ok) {

        document.getElementById(
            "status"
        ).textContent =
            "❌ Մուտք գործիր Admin հաշվով։";

        return;

    }


    const data =
        await response.json();


    if (!data.user.is_admin) {

        document.getElementById(
            "status"
        ).textContent =
            "❌ Դու Admin չես։";

        return;

    }


    document.getElementById(
        "status"
    ).textContent =
        "✅ Admin՝ " +
        data.user.name;


    loadAdminGames();

}


async function loadAdminGames() {

    const response =
        await fetch(
            "/api/games"
        );


    const games =
        await response.json();


    document.getElementById(
        "adminGames"
    ).innerHTML =

        games.map(
            game => `

            <div class="game">

                <h3>
                    ${game.title}
                </h3>

                <p>
                    ${game.description}
                </p>

                <small>
                    ${game.category}
                </small>

                <br><br>

                ${
                    game.is_closed

                    ?

                    "🔒 ՓԱԿ"

                    :

                    "🟢 ԲԱՑ"
                }


                <div class="actions">

                    <button
                        onclick="editGame(${game.id})"
                    >
                        ✏️ Խմբագրել
                    </button>


                    ${
                        game.is_closed

                        ?

                        `
                        <button
                            class="open"
                            onclick="openGame(${game.id})"
                        >
                            🔓 Բացել
                        </button>
                        `

                        :

                        `
                        <button
                            onclick="closeGame(${game.id})"
                        >
                            🔒 Փակել
                        </button>
                        `
                    }


                    <button
                        class="delete"
                        onclick="deleteGame(${game.id})"
                    >
                        🗑️ Ջնջել
                    </button>

                </div>

            </div>

            `
        ).join("");

}


async function addGame() {

    const form =
        new FormData();


    form.append(
        "title",
        document.getElementById(
            "title"
        ).value
    );


    form.append(
        "description",
        document.getElementById(
            "description"
        ).value
    );


    form.append(
        "category",
        document.getElementById(
            "category"
        ).value ||
        "Other"
    );


    form.append(
        "game_url",
        document.getElementById(
            "gameUrl"
        ).value
    );


    const image =
        document.getElementById(
            "image"
        ).files[0];


    if (image) {

        form.append(
            "image",
            image
        );

    }


    const response =
        await fetch(
            "/api/admin/games",
            {

                method:
                    "POST",

                headers: {

                    Authorization:
                        "Bearer " + token()

                },

                body:
                    form

            }
        );


    const data =
        await response.json();


    if (!response.ok) {

        alert(data.error);

        return;

    }


    alert(
        "Խաղը ավելացվեց։"
    );


    document.getElementById(
        "title"
    ).value = "";


    document.getElementById(
        "description"
    ).value = "";


    document.getElementById(
        "category"
    ).value = "";


    document.getElementById(
        "gameUrl"
    ).value = "";


    document.getElementById(
        "image"
    ).value = "";


    loadAdminGames();

}


async function deleteGame(id) {

    if (
        !confirm(
            "Ջնջե՞լ խաղը։"
        )
    ) {
        return;
    }


    await fetch(
        "/api/admin/games/" +
        id,
        {

            method:
                "DELETE",

            headers: {

                Authorization:
                    "Bearer " + token()

            }

        }
    );


    loadAdminGames();

}


async function closeGame(id) {

    const minutes =
        prompt(
            "Քանի՞ րոպե փակել խաղը։",
            "60"
        );


    if (!minutes) return;


    await fetch(
        "/api/admin/games/" +
        id +
        "/close",
        {

            method:
                "POST",

            headers: {

                "Content-Type":
                    "application/json",

                Authorization:
                    "Bearer " + token()

            },

            body:
                JSON.stringify({
                    minutes:
                        Number(minutes)
                })

        }
    );


    loadAdminGames();

}


async function openGame(id) {

    await fetch(
        "/api/admin/games/" +
        id +
        "/open",
        {

            method:
                "POST",

            headers: {

                Authorization:
                    "Bearer " + token()

            }

        }
    );


    loadAdminGames();

}


async function editGame(id) {

    const title =
        prompt(
            "Նոր անունը:"
        );


    if (title === null)
        return;


    const description =
        prompt(
            "Նոր նկարագրությունը:"
        );


    const category =
        prompt(
            "Նոր կատեգորիան:"
        );


    const gameUrl =
        prompt(
            "Նոր խաղի հղումը:"
        );


    await fetch(
        "/api/admin/games/" +
        id,
        {

            method:
                "PUT",

            headers: {

                "Content-Type":
                    "application/json",

                Authorization:
                    "Bearer " + token()

            },

            body:
                JSON.stringify({

                    title:
                        title,

                    description:
                        description,

                    category:
                        category,

                    game_url:
                        gameUrl

                })

        }
    );


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
