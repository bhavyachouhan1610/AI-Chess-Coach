const path = window.location.pathname;
const params = new URLSearchParams(window.location.search);

const gameMode =
    path === "/local" ? "local" :
    path === "/online-game" ? "online" :
    "computer";

const roomCode = (params.get("room") || "").trim().toUpperCase();
const playerColor = (params.get("color") || "white").toLowerCase();

let gameId = null;
let gameState = null;
let selectedSquare = null;
let legalMoves = [];
let loading = false;
let hintSquares = [];
let roomPoller = null;
let lastOnlineError = "";

const $ = (id) => document.getElementById(id);

async function api(url, options = {}) {
    const response = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(
            data.error || data.message || `Request failed (${response.status})`
        );
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
    return files[index % 8] + (8 - Math.floor(index / 8));
}

function getPieceAt(square) {
    return gameState?.pieces?.[square] || null;
}

function getPieceCode(pieceData) {
    if (!pieceData) return "";

    const color = pieceData.color === "white" ? "w" : "b";
    const type = String(pieceData.piece || "").toLowerCase();

    return color + type;
}

function isLegalDestination(from, to) {
    return legalMoves.some(move => move.from === from && move.to === to);
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

function showMessage(message) {
    const feedback = $("feedback");
    if (feedback) feedback.textContent = message || "";
}

function renderBoard() {
    const boardElement = $("board");
    if (!boardElement || !gameState) return;

    boardElement.innerHTML = "";

    // Black player ke liye board ko opposite direction se dikhao.
    for (let visualIndex = 0; visualIndex < 64; visualIndex++) {
        const index = gameMode === "online" && playerColor === "black"
            ? 63 - visualIndex
            : visualIndex;

        const square = squareName(index);
        const row = Math.floor(index / 8);
        const col = index % 8;

        const element = document.createElement("button");
        element.type = "button";
        element.className =
            "square " + ((row + col) % 2 === 0
                ? "light-square"
                : "dark-square");

        element.dataset.square = square;
        element.setAttribute("aria-label", square);

        if (gameState.last_move) {
            const lastFrom = gameState.last_move.slice(0, 2);
            const lastTo = gameState.last_move.slice(2, 4);

            if (square === lastFrom || square === lastTo) {
                element.classList.add("last-move");
            }
        }

        if (selectedSquare === square) {
            element.classList.add("selected");
        }

        if (hintSquares.includes(square)) {
            element.classList.add("hint-square");
        }

        const pieceData = getPieceAt(square);

        if (pieceData) {
            const pieceElement = document.createElement("span");
            pieceElement.className = "piece";
            pieceElement.textContent = pieceSymbol(getPieceCode(pieceData));
            element.appendChild(pieceElement);
        }

        if (selectedSquare && isLegalDestination(selectedSquare, square)) {
            const dot = document.createElement("span");
            dot.className = pieceData ? "capture-dot" : "legal-dot";
            element.appendChild(dot);
        }

        element.addEventListener("click", () => handleSquareClick(square));
        boardElement.appendChild(element);
    }
}

function handleSquareClick(square) {
    if (loading || !gameState || gameState.game_over) return;

    // Online mein sirf apni turn par move kar sakte ho.
    if (gameMode === "online" && gameState.turn !== playerColor) {
        showMessage("Opponent ki turn hai. Uski move ka wait karo.");
        return;
    }

    const piece = getPieceAt(square);

    if (!selectedSquare) {
        if (!piece) return;

        if (gameMode === "computer") {
            if (gameState.turn !== "white" || piece.color !== "white") return;
        } else if (gameMode === "online") {
            if (piece.color !== playerColor) return;
        } else {
            if (piece.color !== gameState.turn) return;
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
        const canSelect =
            gameMode === "online"
                ? piece.color === playerColor
                : piece.color === gameState.turn &&
                  (gameMode !== "computer" || piece.color === "white");

        if (canSelect) {
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
    hintSquares = [];

    sendMove(from, square);
}

function getState(data) {
    return data.state || data;
}

async function sendMove(from, to) {
    try {
        loading = true;

        let data;

        if (gameMode === "online") {
            data = await api(
                `/api/rooms/${encodeURIComponent(roomCode)}/move`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        color: playerColor,
                        from,
                        to
                    })
                }
            );
        } else {
            data = await api(`/api/game/${gameId}/move`, {
                method: "POST",
                body: JSON.stringify({ from, to })
            });
        }

        gameState = getState(data);
        lastOnlineError = "";
        updateInterface();
    } catch (error) {
        showMessage(error.message);

        // Online move fail hone par latest shared board reload karo.
        if (gameMode === "online") {
            await loadRoom(true);
        }
    } finally {
        loading = false;
        renderBoard();
    }
}

function updateInterface() {
    if (!gameState) return;

    normalizeLegalMoves();
    renderBoard();

    const turnLabel = $("turn-label");

    if (turnLabel) {
        if (gameState.game_over) {
            turnLabel.textContent =
                `Game Over${gameState.result ? ": " + gameState.result : ""}`;
        } else if (gameMode === "online") {
            const turn = gameState.turn === "white" ? "White" : "Black";
            turnLabel.textContent =
                gameState.turn === playerColor
                    ? `Your turn (${turn})`
                    : `Opponent's turn (${turn})`;
        } else {
            turnLabel.textContent =
                `Turn: ${gameState.turn === "white" ? "White" : "Black"}`;
        }
    }

    const computerMessage = $("computer-message");

    if (computerMessage) {
        computerMessage.textContent = gameMode === "online"
            ? `Online Room: ${roomCode} | You are ${playerColor}.`
            : (gameState.ai_message || "");
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

    if (difficulty) {
        difficulty.textContent = gameMode === "online"
            ? "Multiplayer"
            : (gameState.difficulty || "Easy");
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

    const hintButton = $("hint-btn");

    if (hintButton) {
        hintButton.hidden = gameMode === "online";
    }

    const hintBox = $("hint-box");

    if (hintBox && gameMode === "online") {
        hintBox.textContent = "Online game: apne friend ke against khelo.";
    }

    const resetButton = $("reset-btn");

    if (resetButton) {
        resetButton.textContent = gameMode === "online"
            ? "↻ Reset Shared Game"
            : "↻ New Game (R)";
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

// ---------------- ONLINE MULTIPLAYER ----------------

async function loadRoom(silent = false) {
    if (gameMode !== "online" || !roomCode) return;

    try {
        const data = await api(
            `/api/rooms/${encodeURIComponent(roomCode)}`
        );

        gameState = getState(data);
        lastOnlineError = "";
        normalizeLegalMoves();
        updateInterface();

        const players = data.players || gameState.players || {};
        const opponentJoined = playerColor === "white"
            ? Boolean(players.black)
            : Boolean(players.white);

        if (!opponentJoined && !gameState.game_over) {
            showMessage(
                `Room ${roomCode} ready. Friend ke join karne ka wait ho raha hai.`
            );
        } else if (gameState.turn === playerColor && !gameState.game_over) {
            showMessage("Opponent connected. Tumhari turn hai!");
        } else if (!gameState.game_over) {
            showMessage("Opponent ki turn hai. Move ka wait karo.");
        }
    } catch (error) {
        if (!silent || lastOnlineError !== error.message) {
            showMessage("Online room error: " + error.message);
        }

        lastOnlineError = error.message;
    }
}

function startRoomPolling() {
    if (roomPoller) clearInterval(roomPoller);

    // Shared board ko regularly refresh karo taaki opponent ki move dikhe.
    roomPoller = setInterval(() => {
        if (!loading) loadRoom(true);
    }, 1500);
}

// ---------------- GAME START / RESET ----------------

async function startNewGame() {
    try {
        loading = true;
        selectedSquare = null;
        hintSquares = [];

        if (gameMode === "online") {
            if (!roomCode) {
                showMessage(
                    "Room code missing hai. Online lobby se room create ya join karo."
                );
                return;
            }

            if (!["white", "black"].includes(playerColor)) {
                showMessage("Player color invalid hai. Room dobara open karo.");
                return;
            }

            const title = $("game-title");
            if (title) title.textContent = "Online Multiplayer Chess";

            const subtitle = $("mode-subtitle");
            if (subtitle) subtitle.textContent = "Play chess with your friend";

            await loadRoom();
            startRoomPolling();
            return;
        }

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
    if (gameMode === "online") {
        showMessage("Online mode mein AI hints available nahi hain.");
        return;
    }

    if (!gameId || loading) return;

    try {
        const data = await api(`/api/game/${gameId}/hint`, {
            method: "POST",
            body: JSON.stringify({})
        });

        gameState = getState(data);
        normalizeLegalMoves();
        hintSquares = [];

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

        renderBoard();
    } catch (error) {
        showMessage(error.message);
    }
}

async function resetGame() {
    if (gameMode === "online") {
        if (!roomCode || loading) return;

        const confirmed = window.confirm(
            "Shared game reset hoga aur dono players ka board restart ho jayega. Continue?"
        );

        if (!confirmed) return;

        try {
            loading = true;

            const data = await api(
                `/api/rooms/${encodeURIComponent(roomCode)}/reset`,
                {
                    method: "POST",
                    body: JSON.stringify({ color: playerColor })
                }
            );

            gameState = getState(data);
            selectedSquare = null;
            hintSquares = [];
            lastOnlineError = "";
            updateInterface();
            showMessage("Shared game reset ho gaya.");
        } catch (error) {
            showMessage("Reset nahi hua: " + error.message);
        } finally {
            loading = false;
        }

        return;
    }

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

        gameState = getState(data);
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

// ---------------- INITIALIZE ----------------

document.addEventListener("DOMContentLoaded", () => {
    const hintButton = $("hint-btn");
    const resetButton = $("reset-btn");

    if (hintButton) {
        hintButton.addEventListener("click", requestHint);
    }

    if (resetButton) {
        resetButton.addEventListener("click", resetGame);
    }

    window.addEventListener("beforeunload", () => {
        if (roomPoller) clearInterval(roomPoller);
    });

    startNewGame();
});