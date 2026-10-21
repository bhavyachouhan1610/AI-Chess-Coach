
const path = window.location.pathname;

const gameMode = path === "/local" ? "local" : "computer";

let gameId = null;
let gameState = null;
let selectedSquare = null;
let legalMoves = [];
let loading = false;

// AI hint ke purple highlighted squares
let hintSquares = [];

const $ = (id) => document.getElementById(id);

async function api(url, options = {}) {
    const response = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || data.message || "Something went wrong");
    }

    return data;
}

function pieceSymbol(piece) {
    const symbols = {
        wk: "♔", wq: "♕", wr: "♖", wb: "♗", wn: "♘", wp: "♙",
        bk: "♚", bq: "♛", br: "♜", bb: "♝", bn: "♞", bp: "♟"
    };

    return symbols[piece] || "";
}

function squareName(index) {
    const files = "abcdefgh";
    const row = Math.floor(index / 8);
    const col = index % 8;

    return files[col] + (8 - row);
}

function getPieceAt(square) {
    const pieces = gameState?.pieces || {};
    return pieces[square] || null;
}

function getPieceCode(pieceData) {
    if (!pieceData) return "";

    const color = pieceData.color === "white" ? "w" : "b";
    const type = String(pieceData.piece || "").toLowerCase();

    return color + type;
}

function isLegalDestination(from, to) {
    return legalMoves.some(move =>
        move.from === from && move.to === to
    );
}

function renderBoard() {
    const boardElement = $("board");
    if (!boardElement || !gameState) return;

    boardElement.innerHTML = "";

    for (let i = 0; i < 64; i++) {
        const square = squareName(i);
        const row = Math.floor(i / 8);
        const col = i % 8;

        const element = document.createElement("button");
        element.type = "button";

        element.className =
            "square " + ((row + col) % 2 === 0
                ? "light-square"
                : "dark-square");

        element.dataset.square = square;
        element.setAttribute("aria-label", square);

        // Last move highlight
        if (gameState.last_move) {
            const lastFrom = gameState.last_move.slice(0, 2);
            const lastTo = gameState.last_move.slice(2, 4);

            if (square === lastFrom || square === lastTo) {
                element.classList.add("last-move");
            }
        }

        // Selected square
        if (selectedSquare === square) {
            element.classList.add("selected");
        }

        // AI hint: purple guide squares
        if (hintSquares.includes(square)) {
            element.classList.add("hint-square");
        }

        const pieceData = getPieceAt(square);

        // Chess piece
        if (pieceData) {
            const pieceElement = document.createElement("span");
            pieceElement.className = "piece";
            pieceElement.textContent = pieceSymbol(
                getPieceCode(pieceData)
            );

            element.appendChild(pieceElement);
        }

        // Legal move dots and capture dots
        if (selectedSquare && isLegalDestination(selectedSquare, square)) {
            const dot = document.createElement("span");
            dot.className = pieceData ? "capture-dot" : "legal-dot";
            element.appendChild(dot);
        }

        element.addEventListener("click", () => handleSquareClick(square));

        boardElement.appendChild(element);
    }
}

function normalizeLegalMoves() {
    const moves = gameState?.legal_moves || [];

    legalMoves = moves.map(move => {
        if (typeof move === "string") {
            return {
                from: move.slice(0, 2),
                to: move.slice(2, 4),
                promotion: move.length > 4 ? move[4] : null
            };
        }

        return move;
    });
}

function handleSquareClick(square) {
    if (loading || !gameState || gameState.game_over) return;

    const piece = getPieceAt(square);

    if (!selectedSquare) {
        if (!piece) return;

        const isWhite = piece.color === "white";
        const isBlack = piece.color === "black";

        if (gameMode === "computer") {
            if (gameState.turn !== "white" || !isWhite) return;
        } else {
            if (
                (gameState.turn === "white" && !isWhite) ||
                (gameState.turn === "black" && !isBlack)
            ) return;
        }

        selectedSquare = square;
        renderBoard();
        return;
    }

    if (selectedSquare === square) {
        selectedSquare = null;
        renderBoard();
        return;
    }

    if (piece) {
        const correctColor =
            (gameState.turn === "white" && piece.color === "white") ||
            (gameState.turn === "black" && piece.color === "black");

        if (correctColor) {
            selectedSquare = square;
            renderBoard();
            return;
        }
    }

    if (!isLegalDestination(selectedSquare, square)) {
        selectedSquare = null;
        renderBoard();
        return;
    }

    const from = selectedSquare;

    selectedSquare = null;

    // Naya move karte waqt purana hint clear karo
    hintSquares = [];

    sendMove(from, square);
}

async function sendMove(from, to) {
    try {
        loading = true;

        const data = await api(`/api/game/${gameId}/move`, {
            method: "POST",
            body: JSON.stringify({ from, to })
        });

        gameState = data.state || data;

        normalizeLegalMoves();
        updateInterface();

    } catch (error) {
        showMessage(error.message);
    } finally {
        loading = false;
        renderBoard();
    }
}

function showMessage(message) {
    const feedback = $("feedback");

    if (feedback) {
        feedback.textContent = message || "";
    }
}

function updateInterface() {
    if (!gameState) return;

    normalizeLegalMoves();
    renderBoard();

    const turnLabel = $("turn-label");

    if (turnLabel) {
        turnLabel.textContent = gameState.game_over
            ? `Game Over${gameState.result ? ": " + gameState.result : ""}`
            : `Turn: ${gameState.turn === "white" ? "White" : "Black"}`;
    }

    showMessage(gameState.feedback || "");

    const computerMessage = $("computer-message");

    if (computerMessage) {
        computerMessage.textContent = gameState.ai_message || "";
    }

    const values = {
        "player-moves": gameState.player_moves,
        "player-captures": gameState.player_captures,
        "ai-captures": gameState.ai_captures,
        "good-moves": gameState.good_moves,
        "mistakes": gameState.mistakes,
        "performance-score": gameState.performance_score
    };

    for (const [id, value] of Object.entries(values)) {
        const element = $(id);

        if (element && value !== undefined) {
            element.textContent = value;
        }
    }

    const difficulty = $("difficulty");

    if (difficulty && gameState.difficulty) {
        difficulty.textContent = gameState.difficulty;
    }

    const history = $("move-history");

    if (history) {
        const moves = gameState.move_history || [];

        history.innerHTML = moves.length
            ? moves.map(move => {
                if (typeof move === "string") {
                    return `<div>${escapeHTML(move)}</div>`;
                }

                const number = move.number || "";
                const white = escapeHTML(move.white || "");
                const black = escapeHTML(move.black || "");

                return `<div>${number}. ${white} ${black}</div>`;
            }).join("")
            : "<div>No moves yet</div>";
    }

    const report = $("game-report");

    if (report) {
        report.textContent = gameState.game_over
            ? (gameState.result || "Game finished")
            : "";
    }
}

function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

async function startNewGame() {
    try {
        loading = true;
        selectedSquare = null;
        hintSquares = [];

        const data = await api("/api/new-game", {
            method: "POST",
            body: JSON.stringify({ mode: gameMode })
        });

        gameId = data.game_id;
        gameState = data.state;

        updateInterface();

        const hintBox = $("hint-box");
        if (hintBox) hintBox.textContent = "";

    } catch (error) {
        showMessage("Game start nahi hua: " + error.message);
    } finally {
        loading = false;
    }
}

async function requestHint() {
    if (!gameId || loading) return;

    try {
        const data = await api(`/api/game/${gameId}/hint`, {
            method: "POST",
            body: JSON.stringify({})
        });

        gameState = data.state || data;
        normalizeLegalMoves();

        // Purane purple squares clear karo
        hintSquares = [];

        // Backend ke hint move se source aur destination lo
        const hintMove = gameState.hint_move;

        if (typeof hintMove === "string" && hintMove.length >= 4) {
            hintSquares = [
                hintMove.slice(0, 2),
                hintMove.slice(2, 4)
            ];
        }

        updateInterface();

        const hintBox = $("hint-box");

        if (hintBox) {
            hintBox.textContent = hintSquares.length
                ? `Guide: ${hintSquares[0]} → ${hintSquares[1]}`
                : (gameState.feedback || "Abhi hint available nahi hai.");
        }

        // Purple guide squares dobara render karo
        renderBoard();

    } catch (error) {
        showMessage(error.message);
    }
}

async function resetGame() {
    if (!gameId) {
        await startNewGame();
        return;
    }

    try {
        loading = true;

        const data = await api(`/api/game/${gameId}/reset`, {
            method: "POST",
            body: JSON.stringify({})
        });

        gameState = data.state || data;
        selectedSquare = null;
        hintSquares = [];

        updateInterface();

        const hintBox = $("hint-box");
        if (hintBox) hintBox.textContent = "";

    } catch (error) {
        showMessage(error.message);
    } finally {
        loading = false;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const hintButton = $("hint-btn");
    const resetButton = $("reset-btn");

    if (hintButton) {
        hintButton.addEventListener("click", requestHint);
    }

    if (resetButton) {
        resetButton.addEventListener("click", resetGame);
    }

    startNewGame();
});
