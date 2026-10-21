
const boardElement = document.getElementById("board");
const turnLabel = document.getElementById("turn-label");
const feedbackElement = document.getElementById("feedback");
const computerMessage = document.getElementById("computer-message");
const hintBox = document.getElementById("hint-box");

let game = null;
let selected = null;
let busy = false;

const pieceSymbols = {
    K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙",
    k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟"
};

async function api(url, body = null) {
    const options = {
        method: body === null ? "GET" : "POST",
        headers: { "Content-Type": "application/json" }
    };

    if (body !== null) {
        options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Request failed");
    }

    return data;
}

function showError(message) {
    feedbackElement.textContent = message;
}

function renderBoard() {
    boardElement.innerHTML = "";

    const legalMoves = game.legal_moves || [];
    const destinations = selected
        ? legalMoves
            .filter(move => move.slice(0, 2) === selected)
            .map(move => move.slice(2, 4))
        : [];

    const lastMove = game.last_move || "";
    const hint = game.hint_move || "";

    for (let rank = 7; rank >= 0; rank--) {
        for (let file = 0; file < 8; file++) {
            const squareName = "abcdefgh"[file] + (rank + 1);
            const square = document.createElement("button");

            square.type = "button";
            square.className = "square " +
                ((rank + file) % 2 === 0 ? "light" : "dark");

            square.setAttribute("aria-label", squareName);

            if (squareName === selected) {
                square.classList.add("selected");
            }

            if (
                lastMove &&
                (squareName === lastMove.slice(0, 2) ||
                 squareName === lastMove.slice(2, 4))
            ) {
                square.classList.add("last-move");
            }

            if (
                hint &&
                (squareName === hint.slice(0, 2) ||
                 squareName === hint.slice(2, 4))
            ) {
                square.classList.add("hint-square");
            }

            const pieceData = game.pieces[squareName];

            if (pieceData) {
                const piece = document.createElement("span");
                piece.className = "piece " +
                    (pieceData.color === "white"
                        ? "white-piece" : "black-piece");
                piece.textContent = pieceSymbols[pieceData.piece];
                square.appendChild(piece);
            }

            if (destinations.includes(squareName)) {
                const marker = document.createElement("span");

                if (pieceData) {
                    marker.className = "capture-dot";
                } else {
                    marker.className = "move-dot";
                }

                square.appendChild(marker);
            }

            square.addEventListener("click", () => {
                onSquareClick(squareName);
            });

            boardElement.appendChild(square);
        }
    }
}

function renderStats() {
    turnLabel.textContent = game.game_over
        ? game.result
        : game.turn === "white" ? "Your turn · White" : "AI thinking · Black";

    document.getElementById("difficulty").textContent = game.difficulty;
    document.getElementById("player-moves").textContent = game.player_moves;
    document.getElementById("player-captures").textContent = game.player_captures;
    document.getElementById("ai-captures").textContent = game.ai_captures;
    document.getElementById("good-moves").textContent = game.good_moves;
    document.getElementById("mistakes").textContent = game.mistakes;
    document.getElementById("performance-score").textContent =
        game.performance_score;

    feedbackElement.textContent = game.feedback;
    computerMessage.textContent = game.ai_message;

    hintBox.textContent = game.hint_move
        ? "Hint: " + game.hint_move.toUpperCase()
        : "";

    const history = document.getElementById("move-history");
    history.innerHTML = "";

    if (!game.move_history || game.move_history.length === 0) {
        history.textContent = "Your game will appear here.";
    } else {
        game.move_history.forEach((item, index) => {
            const row = document.createElement("div");
            row.className = "history-row";

            const number = document.createElement("span");
            number.textContent = item.number + ".";

            const white = document.createElement("span");
            white.textContent = item.white || "—";

            const black = document.createElement("span");
            black.textContent = item.black || "—";

            row.append(number, white, black);
            history.appendChild(row);
        });
    }

    document.getElementById("game-report").textContent =
        game.game_over
            ? game.result
            : "Game in progress. Keep playing to build your report.";

    document.getElementById("hint-btn").disabled =
        busy || game.game_over || game.turn !== "white";

    document.getElementById("reset-btn").disabled = busy;
}

function render() {
    renderBoard();
    renderStats();
}

async function refreshState() {
    game = await api("/api/state");
    render();
}

async function onSquareClick(squareName) {
    if (busy || !game || game.game_over || game.turn !== "white") {
        return;
    }

    const piece = game.pieces[squareName];

    if (selected) {
        const candidate = selected + squareName;

        const validMove = game.legal_moves.some(
            move => move.slice(0, 4) === candidate
        );

        if (validMove) {
            busy = true;
            renderStats();

            try {
                game = await api("/api/move", {
                    from: selected,
                    to: squareName
                });

                selected = null;
                hintBox.textContent = "";
            } catch (error) {
                showError(error.message);
            } finally {
                busy = false;
                await refreshState();
            }

            return;
        }
    }

    if (piece && piece.color === "white") {
        selected = squareName;
        hintBox.textContent = "";
    } else {
        selected = null;
    }

    renderBoard();
}

document.getElementById("hint-btn").addEventListener("click", async () => {
    if (busy) return;

    busy = true;
    renderStats();

    try {
        game = await api("/api/hint", {});
        selected = null;
        render();
    } catch (error) {
        showError(error.message);
    } finally {
        busy = false;
        render();
    }
});

document.getElementById("reset-btn").addEventListener("click", async () => {
    if (busy) return;

    busy = true;

    try {
        game = await api("/api/reset", {});
        selected = null;
        hintBox.textContent = "";
        render();
    } catch (error) {
        showError(error.message);
    } finally {
        busy = false;
        render();
    }
});

// Keyboard shortcuts: H = hint, R = restart
document.addEventListener("keydown", async event => {
    if (event.repeat || busy) return;

    if (event.key.toLowerCase() === "h") {
        document.getElementById("hint-btn").click();
    }

    if (event.key.toLowerCase() === "r") {
        document.getElementById("reset-btn").click();
    }
});

async function startApp() {
    try {
        await refreshState();
    } catch (error) {
        showError("App load nahi hui: " + error.message);
    }
}

startApp();
