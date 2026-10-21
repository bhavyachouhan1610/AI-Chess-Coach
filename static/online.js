
const $ = (id) => document.getElementById(id);

let currentRoomCode = "";
let currentPlayerColor = "";

async function api(url, options = {}) {
    const response = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Something went wrong.");
    }

    return data;
}

function showMessage(message, isError = false) {
    const element = $("online-message");
    element.textContent = message;
    element.style.color = isError ? "#dc2626" : "";
}

function displayRoom(data, color) {
    currentRoomCode = data.code || data.room_code || "";
    currentPlayerColor = color || data.color || "";

    if (!currentRoomCode) {
        showMessage("Room code nahi mila. Please dobara try karo.", true);
        return;
    }

    $("room-details").hidden = false;
    $("display-room-code").textContent = currentRoomCode;
    $("player-color").textContent =
        `You are playing as ${currentPlayerColor || "White"}.`;

    $("open-game-link").href =
        `/online-game?room=${encodeURIComponent(currentRoomCode)}&color=${encodeURIComponent(currentPlayerColor)}`;

    showMessage("Room ready! Apne friend ko room code share karo.");
}

async function createRoom() {
    const button = $("create-room-btn");
    button.disabled = true;

    try {
        showMessage("Room create ho raha hai...");

        const data = await api("/api/rooms", {
            method: "POST",
            body: JSON.stringify({})
        });

        displayRoom(data, data.color || "white");
    } catch (error) {
        showMessage(error.message, true);
    } finally {
        button.disabled = false;
    }
}

async function joinRoom() {
    const button = $("join-room-btn");
    const code = $("room-code").value.trim().toUpperCase();

    if (!code) {
        showMessage("Pehle friend ka room code enter karo.", true);
        $("room-code").focus();
        return;
    }

    button.disabled = true;

    try {
        showMessage("Room join ho raha hai...");

        const data = await api("/api/rooms/join", {
            method: "POST",
            body: JSON.stringify({ code })
        });

        displayRoom(data, data.color || "black");
    } catch (error) {
        showMessage(error.message, true);
    } finally {
        button.disabled = false;
    }
}

async function copyRoomCode() {
    if (!currentRoomCode) return;

    try {
        await navigator.clipboard.writeText(currentRoomCode);
        showMessage("Room code copy ho gaya! Ab friend ko send karo.");
    } catch {
        showMessage(`Room code: ${currentRoomCode} — ise manually copy karo.`);
    }
}

$("create-room-btn").addEventListener("click", createRoom);
$("join-room-btn").addEventListener("click", joinRoom);
$("copy-code-btn").addEventListener("click", copyRoomCode);

$("room-code").addEventListener("input", (event) => {
    event.target.value = event.target.value
        .toUpperCase()
        .replace(/[^A-Z0-9]/g, "")
        .slice(0, 6);
});

$("room-code").addEventListener("keydown", (event) => {
    if (event.key === "Enter") joinRoom();
});
