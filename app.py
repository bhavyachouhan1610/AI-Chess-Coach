
from flask import Flask, render_template, jsonify, request
import chess
import random
import string
import threading
import time

app = Flask(__name__)
app.secret_key = "ai-chess-coach-project-secret"

# ==================================================
# GAME STORAGE
# ==================================================

games = {}
rooms = {}
game_lock = threading.RLock()

# ==================================================
# CHESS SETTINGS
# ==================================================

VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

PIECE_NAMES = {
    chess.PAWN: "Pawn",
    chess.KNIGHT: "Knight",
    chess.BISHOP: "Bishop",
    chess.ROOK: "Rook",
    chess.QUEEN: "Queen",
    chess.KING: "King"
}


# ==================================================
# CREATE NEW GAME
# ==================================================

def new_game(mode="computer"):
    return {
        "board": chess.Board(),
        "mode": mode,
        "difficulty": "Easy",
        "player_moves": 0,
        "player_captures": 0,
        "ai_captures": 0,
        "mistakes": 0,
        "good_moves": 0,
        "performance_score": 50,
        "feedback": "Welcome! White pieces se game start karo.",
        "ai_message": "Main tumhara AI Chess Coach hoon!",
        "hint_move": None,
        "last_move": None,
        "move_history": [],
        "feedback_history": [],
        "updated": time.time()
    }


# ==================================================
# CHESS AI: POSITION EVALUATION
# ==================================================

def evaluate_position(position):
    """
    Positive score = Black ke liye achha.
    Negative score = White ke liye achha.
    """

    if position.is_checkmate():
        if position.turn == chess.WHITE:
            return 100000
        return -100000

    if position.is_game_over():
        return 0

    score = 0

    # Material value
    for piece_type, value in VALUES.items():
        score += len(
            position.pieces(piece_type, chess.BLACK)
        ) * value

        score -= len(
            position.pieces(piece_type, chess.WHITE)
        ) * value

    # Centre control
    centre_squares = [
        chess.D4, chess.E4, chess.D5, chess.E5
    ]

    for square in centre_squares:
        piece = position.piece_at(square)

        if piece:
            if piece.color == chess.BLACK:
                score += 15
            else:
                score -= 15

    # Pawn advancement
    for square in position.pieces(chess.PAWN, chess.BLACK):
        score += chess.square_rank(square) * 5

    for square in position.pieces(chess.PAWN, chess.WHITE):
        score -= (7 - chess.square_rank(square)) * 5

    return score


# ==================================================
# MOVE ORDERING
# ==================================================

def move_order_score(position, move):
    score = 0

    if position.is_capture(move):
        captured = position.piece_at(move.to_square)

        # En passant mein captured pawn destination par nahi hota
        if captured:
            score += VALUES[captured.piece_type]
        elif position.is_en_passant(move):
            score += VALUES[chess.PAWN]

        attacker = position.piece_at(move.from_square)

        if attacker:
            score -= VALUES[attacker.piece_type] // 10

    if move.promotion:
        score += VALUES.get(move.promotion, 0)

    position.push(move)

    if position.is_check():
        score += 40

    position.pop()

    return score


# ==================================================
# MINIMAX AI WITH ALPHA-BETA PRUNING
# ==================================================

def minimax(position, depth, alpha, beta, maximizing):
    if depth == 0 or position.is_game_over():
        return evaluate_position(position), None

    legal_moves = list(position.legal_moves)

    legal_moves.sort(
        key=lambda move: move_order_score(position, move),
        reverse=maximizing
    )

    best_move = None

    if maximizing:
        best_score = float("-inf")

        for move in legal_moves:
            position.push(move)

            score, _ = minimax(
                position,
                depth - 1,
                alpha,
                beta,
                False
            )

            position.pop()

            if score > best_score:
                best_score = score
                best_move = move

            alpha = max(alpha, best_score)

            if beta <= alpha:
                break

        return best_score, best_move

    best_score = float("inf")

    for move in legal_moves:
        position.push(move)

        score, _ = minimax(
            position,
            depth - 1,
            alpha,
            beta,
            True
        )

        position.pop()

        if score < best_score:
            best_score = score
            best_move = move

        beta = min(beta, best_score)

        if beta <= alpha:
            break

    return best_score, best_move


# ==================================================
# GAME RESULT
# ==================================================

def get_result(board, mode):
    if not board.is_game_over():
        return None

    if board.is_checkmate():
        winner = "Black" if board.turn == chess.WHITE else "White"

        if mode == "computer":
            if winner == "Black":
                return "AI wins by checkmate!"

            return "You win by checkmate!"

        return f"{winner} wins by checkmate!"

    if board.is_stalemate():
        return "Draw by stalemate!"

    if board.is_insufficient_material():
        return "Draw: insufficient material!"

    if board.is_fifty_moves():
        return "Draw by fifty-move rule!"

    if board.is_repetition():
        return "Draw by repetition!"

    return "Game drawn!"


# ==================================================
# GAME STATE FOR FRONTEND
# ==================================================

def get_state(game, player_color=None, room_code=None):
    board = game["board"]
    pieces = {}

    for square, piece in board.piece_map().items():
        pieces[chess.square_name(square)] = {
            "piece": piece.symbol(),
            "color": (
                "white"
                if piece.color == chess.WHITE
                else "black"
            ),
            "name": PIECE_NAMES[piece.piece_type]
        }

    return {
        "pieces": pieces,

        "legal_moves": [
            move.uci() for move in board.legal_moves
        ],

        "turn": (
            "white"
            if board.turn == chess.WHITE
            else "black"
        ),

        "difficulty": game["difficulty"],
        "feedback": game["feedback"],
        "ai_message": game["ai_message"],
        "hint_move": game["hint_move"],
        "last_move": game["last_move"],

        "game_over": board.is_game_over(),
        "result": get_result(board, game["mode"]),

        "player_moves": game["player_moves"],
        "player_captures": game["player_captures"],
        "ai_captures": game["ai_captures"],
        "mistakes": game["mistakes"],
        "good_moves": game["good_moves"],
        "performance_score": game["performance_score"],

        "feedback_history": game["feedback_history"],
        "move_history": game["move_history"],

        "mode": game["mode"],
        "player_color": player_color,
        "room_code": room_code
    }


# ==================================================
# ADAPTIVE DIFFICULTY
# ==================================================

def update_difficulty(game):
    if game["player_moves"] < 3:
        game["difficulty"] = "Easy"

    elif game["performance_score"] >= 75:
        game["difficulty"] = "Strong"

    elif game["performance_score"] >= 50:
        game["difficulty"] = "Medium"

    else:
        game["difficulty"] = "Easy"


# ==================================================
# PLAYER MOVE FEEDBACK
# ==================================================

def analyse_player_move(game, was_capture):
    board = game["board"]

    if board.is_checkmate():
        message = "Checkmate! Excellent game!"
        game["good_moves"] += 1

    elif board.is_check():
        message = "Check! Tumne opponent ke King ko check diya."
        game["good_moves"] += 1

    elif was_capture:
        message = "Good capture! Tumne opponent ka piece capture kiya."
        game["good_moves"] += 1

    else:
        attacked_piece = None

        for square, piece in board.piece_map().items():
            if piece.color == chess.WHITE:
                if board.is_attacked_by(chess.BLACK, square):
                    attacked_piece = piece
                    break

        if attacked_piece:
            message = (
                f"Careful! Tumhara "
                f"{PIECE_NAMES[attacked_piece.piece_type]} "
                "attack mein ho sakta hai."
            )
            game["mistakes"] += 1

        else:
            message = (
                "Nice move! Centre aur apne pieces par "
                "nazar rakho."
            )
            game["good_moves"] += 1

    game["performance_score"] = max(
        0,
        min(
            100,
            50
            + game["good_moves"] * 5
            - game["mistakes"] * 8
        )
    )

    game["feedback"] = message
    game["feedback_history"].append(message)
    game["feedback_history"] = game["feedback_history"][-10:]


# ==================================================
# VALIDATE A MOVE
# ==================================================

def parse_move(board, data):
    source = data.get("from")
    target = data.get("to")

    if not isinstance(source, str) or not isinstance(target, str):
        raise ValueError("Move details missing.")

    try:
        move = chess.Move.from_uci(source + target)

    except (ValueError, TypeError):
        raise ValueError("Invalid move format.")

    piece = board.piece_at(move.from_square)

    # Automatically promote pawn to Queen
    if (
        piece
        and piece.piece_type == chess.PAWN
        and chess.square_rank(move.to_square) in (0, 7)
    ):
        move = chess.Move(
            move.from_square,
            move.to_square,
            promotion=chess.QUEEN
        )

    if move not in board.legal_moves:
        raise ValueError("Ye legal move nahi hai.")

    return move


# ==================================================
# RECORD A CHESS MOVE
# ==================================================

def record_move(game, move):
    board = game["board"]

    san_move = board.san(move)
    was_capture = board.is_capture(move)
    mover_color = board.turn

    if was_capture and game["mode"] == "computer":
        if mover_color == chess.WHITE:
            game["player_captures"] += 1
        else:
            game["ai_captures"] += 1

    board.push(move)

    game["last_move"] = move.uci()
    game["hint_move"] = None

    move_number = (len(game["move_history"]) // 2) + 1

    if mover_color == chess.WHITE:
        game["player_moves"] += 1

        game["move_history"].append({
            "number": move_number,
            "white": san_move,
            "black": None
        })

        if game["mode"] == "computer":
            analyse_player_move(game, was_capture)
            update_difficulty(game)

    else:
        if (
            game["move_history"]
            and game["move_history"][-1]["black"] is None
        ):
            game["move_history"][-1]["black"] = san_move

        else:
            game["move_history"].append({
                "number": move_number,
                "white": None,
                "black": san_move
            })

    game["updated"] = time.time()

    return was_capture


# ==================================================
# COMPUTER AI MOVE
# ==================================================

def make_computer_move(game):
    board = game["board"]

    if board.is_game_over():
        return

    game["hint_move"] = None

    if game["difficulty"] == "Easy":
        depth = 1
        random_chance = 0.25

    elif game["difficulty"] == "Medium":
        depth = 2
        random_chance = 0.08

    else:
        depth = 3
        random_chance = 0

    legal_moves = list(board.legal_moves)

    if not legal_moves:
        return

    if random.random() < random_chance:
        move = random.choice(legal_moves)

    else:
        _, move = minimax(
            board,
            depth,
            float("-inf"),
            float("inf"),
            True
        )

        if move is None:
            move = random.choice(legal_moves)

    san_move = board.san(move)
    was_capture = board.is_capture(move)

    if was_capture:
        game["ai_captures"] += 1

    board.push(move)

    game["last_move"] = move.uci()

    if (
        game["move_history"]
        and game["move_history"][-1]["black"] is None
    ):
        game["move_history"][-1]["black"] = san_move

    else:
        game["move_history"].append({
            "number": (len(game["move_history"]) // 2) + 1,
            "white": None,
            "black": san_move
        })

    game["ai_message"] = f"AI played {san_move}. Tumhari baari!"

    if board.is_check():
        game["ai_message"] += " Check!"

    update_difficulty(game)
    game["updated"] = time.time()


# ==================================================
# WEB PAGES
# ==================================================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/computer")
def computer_page():
    return render_template("game.html", mode="computer")


@app.route("/local")
def local_page():
    return render_template("game.html", mode="local")


@app.route("/online")
def online_page():
    return render_template("online.html")


@app.route("/online-game")
def online_game_page():
    return render_template("game.html", mode="online")


# ==================================================
# START A NEW COMPUTER OR LOCAL GAME
# ==================================================

@app.route("/api/new-game", methods=["POST"])
def api_new_game():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "computer")

    if mode not in ("computer", "local"):
        return jsonify({"error": "Unknown game mode."}), 400

    game_id = "".join(
        random.choices(string.ascii_lowercase + string.digits, k=16)
    )

    with game_lock:
        games[game_id] = new_game(mode)
        state = get_state(games[game_id])

    return jsonify({
        "game_id": game_id,
        "state": state
    })


# ==================================================
# GET GAME STATE
# ==================================================

@app.route("/api/game/<game_id>")
def api_game_state(game_id):
    with game_lock:
        game = games.get(game_id)

        if not game:
            return jsonify({
                "error": "Game nahi mili. New Game start karo."
            }), 404

        return jsonify(get_state(game))


# ==================================================
# PLAYER MOVE API
# ==================================================

@app.route("/api/game/<game_id>/move", methods=["POST"])
def api_game_move(game_id):
    data = request.get_json(silent=True) or {}

    with game_lock:
        game = games.get(game_id)

        if not game:
            return jsonify({"error": "Game nahi mili."}), 404

        board = game["board"]

        if board.is_game_over():
            return jsonify({
                "error": "Game over! New Game start karo."
            }), 400

        if game["mode"] == "computer" and board.turn != chess.WHITE:
            return jsonify({"error": "Abhi AI ki baari hai."}), 400

        try:
            move = parse_move(board, data)

        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        record_move(game, move)

        if game["mode"] == "computer" and not board.is_game_over():
            make_computer_move(game)

        elif game["mode"] == "local":
            if not board.is_game_over():
                game["feedback"] = (
                    "White ki baari."
                    if board.turn == chess.WHITE
                    else "Black ki baari."
                )

                game["ai_message"] = (
                    "Same-device two-player game."
                )

        return jsonify(get_state(game))


# ==================================================
# AI HINT API
# ==================================================

@app.route("/api/game/<game_id>/hint", methods=["POST"])
def api_game_hint(game_id):
    with game_lock:
        game = games.get(game_id)

        if not game:
            return jsonify({"error": "Game nahi mili."}), 404

        if game["mode"] != "computer":
            return jsonify({
                "error": "Hints sirf Computer mode mein available hain."
            }), 400

        board = game["board"]

        if board.is_game_over():
            return jsonify({"error": "Game khatam ho chuka hai."}), 400

        if board.turn != chess.WHITE:
            return jsonify({"error": "AI ki baari hai."}), 400

        # White tries to minimise the score
        _, best_move = minimax(
            board,
            2,
            float("-inf"),
            float("inf"),
            False
        )

        if best_move:
            game["hint_move"] = best_move.uci()
            san_move = board.san(best_move)

            game["feedback"] = f"Hint: {san_move} try karo!"
            game["ai_message"] = (
                "Hint ready! Purple squares ko dekho."
            )

        return jsonify(get_state(game))


# ==================================================
# RESET COMPUTER OR LOCAL GAME
# ==================================================

@app.route("/api/game/<game_id>/reset", methods=["POST"])
def api_game_reset(game_id):
    with game_lock:
        game = games.get(game_id)

        if not game:
            return jsonify({"error": "Game nahi mili."}), 404

        mode = game["mode"]
        games[game_id] = new_game(mode)

        return jsonify(get_state(games[game_id]))


# ==================================================
# ONLINE ROOM HELPERS
# ==================================================

def make_room_code():
    for _ in range(100):
        code = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )

        if code not in rooms:
            return code

    raise RuntimeError("Room create nahi hua. Dobara try karo.")


# ==================================================
# CREATE ONLINE ROOM
# ==================================================

@app.route("/api/rooms", methods=["POST"])
def create_room():
    with game_lock:
        code = make_room_code()

        game_id = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=16)
        )

        games[game_id] = new_game("online")

        rooms[code] = {
            "game_id": game_id,
            "players": {
                "white": True,
                "black": False
            },
            "created": time.time()
        }

    return jsonify({
        "code": code,
        "color": "white"
    })


# ==================================================
# JOIN ONLINE ROOM
# ==================================================

@app.route("/api/rooms/join", methods=["POST"])
def join_room():
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip().upper()

    if not code:
        return jsonify({"error": "Room code enter karo."}), 400

    with game_lock:
        room = rooms.get(code)

        if not room:
            return jsonify({
                "error": "Room code nahi mila. Code check karo."
            }), 404

        if room["players"]["black"]:
            return jsonify({
                "error": "Room full hai. Friend se naya room banwao."
            }), 409

        room["players"]["black"] = True

    return jsonify({
        "code": code,
        "color": "black"
    })


# ==================================================
# GET ONLINE ROOM STATE
# ==================================================

@app.route("/api/rooms/<code>")
def room_state(code):
    code = code.upper()

    with game_lock:
        room = rooms.get(code)

        if not room:
            return jsonify({"error": "Room nahi mila."}), 404

        game = games.get(room["game_id"])

        if not game:
            return jsonify({"error": "Game nahi mili."}), 404

        state = get_state(game, room_code=code)
        state["players"] = room["players"].copy()

        return jsonify(state)


# ==================================================
# ONLINE MOVE API
# ==================================================

@app.route("/api/rooms/<code>/move", methods=["POST"])
def room_move(code):
    data = request.get_json(silent=True) or {}
    color = str(data.get("color", "")).lower()
    code = code.upper()

    with game_lock:
        room = rooms.get(code)

        if not room:
            return jsonify({"error": "Room nahi mila."}), 404

        if color not in ("white", "black"):
            return jsonify({"error": "Player color missing."}), 400

        if not room["players"].get(color):
            return jsonify({
                "error": "Is color ka player join nahi hua."
            }), 403

        game = games.get(room["game_id"])

        if not game:
            return jsonify({"error": "Game nahi mili."}), 404

        board = game["board"]

        if board.is_game_over():
            return jsonify({"error": "Game over ho gaya."}), 400

        expected_color = (
            "white"
            if board.turn == chess.WHITE
            else "black"
        )

        if color != expected_color:
            return jsonify({
                "error": "Abhi opponent ki baari hai."
            }), 409

        try:
            move = parse_move(board, data)

        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        record_move(game, move)

        if not board.is_game_over():
            game["feedback"] = (
                "White ki baari."
                if board.turn == chess.WHITE
                else "Black ki baari."
            )

        game["ai_message"] = (
            "Online chess room. Opponent ki move ka wait karo."
        )

        state = get_state(
            game,
            player_color=color,
            room_code=code
        )

        return jsonify(state)


# ==================================================
# RESET ONLINE ROOM GAME
# ==================================================

@app.route("/api/rooms/<code>/reset", methods=["POST"])
def room_reset(code):
    code = code.upper()

    with game_lock:
        room = rooms.get(code)

        if not room:
            return jsonify({"error": "Room nahi mila."}), 404

        game_id = room["game_id"]
        games[game_id] = new_game("online")

        return jsonify(
            get_state(
                games[game_id],
                room_code=code
            )
        )


# ==================================================
# START FLASK SERVER
# ==================================================

if __name__ == "__main__":
    print("\n====================================")
    print("       AI CHESS COACH APP")
    print("====================================")
    print("Open browser: http://127.0.0.1:5000")
    print("Stop server: Ctrl + C")
    print("Online rooms need public hosting for distant friends.")
    print("====================================\n")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
