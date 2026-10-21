
import sys
import random
import pygame
import chess

pygame.init()

# ==================== SETTINGS ====================
WIDTH = 760
BOARD_SIZE = 640
HEIGHT = 830
SQ_SIZE = BOARD_SIZE // 8
BOARD_X = (WIDTH - BOARD_SIZE) // 2

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("AI Chess Coach - Smart Edition")

FONT = pygame.font.SysFont("segoeuisymbol", 48)
SMALL_FONT = pygame.font.SysFont("arial", 15)
STATUS_FONT = pygame.font.SysFont("arial", 17)
TITLE_FONT = pygame.font.SysFont("arial", 25, bold=True)

LIGHT = (238, 238, 210)
DARK = (118, 150, 86)
GREEN = (35, 180, 85)
BLUE = (65, 135, 225)
YELLOW = (255, 215, 60)
PURPLE = (155, 90, 210)
WHITE = (255, 255, 255)
BLACK = (25, 25, 25)
GREY = (240, 243, 248)
RED = (200, 55, 55)

PIECES = {
    "P": "♙", "N": "♘", "B": "♗",
    "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝",
    "r": "♜", "q": "♛", "k": "♚"
}

VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

board = chess.Board()
selected_square = None
legal_targets = []
last_move = None
hint_move = None

feedback = "Welcome! You play White. Press H for a hint."
difficulty = 1

player_moves = 0
player_captures = 0
ai_captures = 0
mistakes = 0
good_moves = 0
performance_score = 0

move_history = []
feedback_history = []


# ==================== RESET GAME ====================
def reset_game():
    global board, selected_square, legal_targets
    global last_move, hint_move, feedback, difficulty
    global player_moves, player_captures, ai_captures
    global mistakes, good_moves, performance_score
    global move_history, feedback_history

    board = chess.Board()
    selected_square = None
    legal_targets = []
    last_move = None
    hint_move = None

    feedback = "New game! You play White. Press H for a hint."
    difficulty = 1

    player_moves = 0
    player_captures = 0
    ai_captures = 0
    mistakes = 0
    good_moves = 0
    performance_score = 0

    move_history = []
    feedback_history = []


# ==================== POSITION EVALUATION ====================
# Positive score = better for Black/computer.
# Negative score = better for White/player.
def evaluate_position(position):
    if position.is_checkmate():
        return -100000 if position.turn == chess.BLACK else 100000

    if position.is_game_over():
        return 0

    score = 0

    for square, piece in position.piece_map().items():
        value = VALUES[piece.piece_type]
        file_no = chess.square_file(square)
        rank_no = chess.square_rank(square)

        centre_bonus = int(
            (7 - abs(3.5 - file_no) - abs(3.5 - rank_no)) * 3
        )

        if piece.piece_type != chess.KING:
            value += centre_bonus

        # Encourage pawns to advance.
        if piece.piece_type == chess.PAWN:
            if piece.color == chess.WHITE:
                value += rank_no * 5
            else:
                value += (7 - rank_no) * 5

        if piece.color == chess.BLACK:
            score += value
        else:
            score -= value

    return score


def move_order_score(position, move):
    score = 0
    captured = position.piece_at(move.to_square)

    if position.is_en_passant(move):
        score += VALUES[chess.PAWN] * 10
    elif captured:
        moving = position.piece_at(move.from_square)
        moving_value = VALUES[moving.piece_type] if moving else 0
        score += VALUES[captured.piece_type] * 10 - moving_value

    if move.promotion:
        score += VALUES[move.promotion]

    return score


def minimax(position, depth, alpha, beta, maximizing):
    if depth == 0 or position.is_game_over():
        return evaluate_position(position), None

    moves = list(position.legal_moves)
    moves.sort(
        key=lambda m: move_order_score(position, m),
        reverse=True
    )

    best_move = None

    if maximizing:
        best_score = -float("inf")

        for move in moves:
            position.push(move)
            score, _ = minimax(
                position, depth - 1, alpha, beta, False
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

    for move in moves:
        position.push(move)
        score, _ = minimax(
            position, depth - 1, alpha, beta, True
        )
        position.pop()

        if score < best_score:
            best_score = score
            best_move = move

        beta = min(beta, best_score)
        if beta <= alpha:
            break

    return best_score, best_move


# ==================== SMART HINT ====================
def get_best_hint():
    global hint_move, feedback

    if board.is_game_over() or board.turn != chess.WHITE:
        feedback = "Hints are available on your turn."
        return

    feedback = "Coach is checking possible moves..."
    pygame.event.pump()

    # White minimizes the score because negative favours White.
    depth = 2 if difficulty == 1 else 3
    _, move = minimax(
        board, depth, -float("inf"), float("inf"), False
    )

    if move is None:
        feedback = "No suggested move available."
        hint_move = None
        return

    hint_move = move
    san = board.san(move)

    board.push(move)
    if board.is_checkmate():
        reason = "This move gives checkmate!"
    elif board.is_check():
        reason = "This move puts the opponent in check."
    elif board.is_capture(move):
        reason = "This move captures an opponent piece."
    else:
        reason = "This move scores well in the coach's search."
    board.pop()

    feedback = f"Suggested move: {san}. {reason}"


# ==================== PIECE SAFETY ====================
def get_piece_name(piece):
    names = {
        chess.PAWN: "Pawn",
        chess.KNIGHT: "Knight",
        chess.BISHOP: "Bishop",
        chess.ROOK: "Rook",
        chess.QUEEN: "Queen",
        chess.KING: "King"
    }
    return names[piece.piece_type]


def find_hanging_pieces():
    """
    Find White pieces attacked by Black.
    This is a simple warning, not complete engine analysis.
    """
    hanging = []

    for square, piece in board.piece_map().items():
        if piece.color != chess.WHITE:
            continue

        if piece.piece_type == chess.KING:
            continue

        attackers = board.attackers(chess.BLACK, square)

        if attackers:
            defenders = board.attackers(chess.WHITE, square)
            hanging.append((square, piece, len(defenders)))

    return hanging


def analyse_player_move():
    global feedback, mistakes, good_moves, performance_score

    if board.is_checkmate():
        feedback = "Excellent! You delivered checkmate!"
        good_moves += 1
    elif board.is_check():
        feedback = "Check! Your King is under attack. Find a safe move."
        mistakes += 1
        performance_score -= 2
    else:
        hanging = find_hanging_pieces()

        # Show the most valuable attacked White piece first.
        if hanging:
            square, piece, defenders = max(
                hanging,
                key=lambda item: VALUES[item[1].piece_type]
            )

            piece_name = get_piece_name(piece)
            square_name = chess.square_name(square)

            if defenders == 0:
                feedback = (
                    f"Warning: Your {piece_name} on {square_name} "
                    "is attacked and has no defender!"
                )
                mistakes += 1
                performance_score -= 1
            else:
                feedback = (
                    f"Careful: Your {piece_name} on {square_name} "
                    "is attacked. Check your defenders."
                )
                performance_score -= 0.5
        else:
            feedback = (
                "No directly attacked White piece detected. "
                "Check the opponent's threats too."
            )
            good_moves += 1
            performance_score += 1

    feedback_history.append(feedback)

    if len(feedback_history) > 6:
        feedback_history.pop(0)


# ==================== ADAPTIVE DIFFICULTY ====================
def update_difficulty():
    global difficulty

    if player_moves < 3:
        difficulty = 1
        return

    average = performance_score / max(player_moves, 1)

    if average >= 0.5:
        difficulty = 3
    elif average >= 0:
        difficulty = 2
    else:
        difficulty = 1


# ==================== COMPUTER MOVE ====================
def computer_move():
    global last_move, feedback, ai_captures, hint_move

    if board.is_game_over() or board.turn != chess.BLACK:
        return

    depth = {1: 1, 2: 2, 3: 3}[difficulty]

    if difficulty == 1 and random.random() < 0.25:
        move = random.choice(list(board.legal_moves))
    else:
        _, move = minimax(
            board, depth,
            -float("inf"), float("inf"), True
        )

    if move is None:
        return

    san = board.san(move)

    if board.is_capture(move):
        ai_captures += 1

    board.push(move)
    last_move = move
    hint_move = None

    move_history.append("Black: " + san)
    feedback = f"Computer played {san}. Your turn!"


# ==================== PLAYER MOVE ====================
def handle_click(position):
    global selected_square, legal_targets, last_move
    global player_moves, player_captures, feedback, hint_move

    if board.is_game_over() or board.turn != chess.WHITE:
        return

    x, y = position

    if y >= BOARD_SIZE:
        return

    if x < BOARD_X or x >= BOARD_X + BOARD_SIZE:
        return

    col = (x - BOARD_X) // SQ_SIZE
    row = y // SQ_SIZE
    square = chess.square(col, 7 - row)

    if selected_square is None:
        piece = board.piece_at(square)

        if piece and piece.color == chess.WHITE:
            selected_square = square
            legal_targets = [
                m.to_square for m in board.legal_moves
                if m.from_square == square
            ]
        return

    possible_moves = [
        m for m in board.legal_moves
        if m.from_square == selected_square
        and m.to_square == square
    ]

    if possible_moves:
        move = possible_moves[0]

        # Automatically promote to Queen.
        if move.promotion:
            queen_move = chess.Move(
                move.from_square,
                move.to_square,
                promotion=chess.QUEEN
            )
            if queen_move in board.legal_moves:
                move = queen_move

        san = board.san(move)

        if board.is_capture(move):
            player_captures += 1

        board.push(move)
        last_move = move
        hint_move = None

        player_moves += 1
        move_history.append("White: " + san)

        selected_square = None
        legal_targets = []

        if board.is_game_over():
            if board.is_checkmate():
                feedback = "Checkmate! You won!"
            else:
                feedback = "Game over! Check your report."
        else:
            analyse_player_move()
            update_difficulty()

    else:
        piece = board.piece_at(square)

        if piece and piece.color == chess.WHITE:
            selected_square = square
            legal_targets = [
                m.to_square for m in board.legal_moves
                if m.from_square == square
            ]
        else:
            selected_square = None
            legal_targets = []


# ==================== DRAW BOARD ====================
def draw_board():
    for row in range(8):
        for col in range(8):
            x = BOARD_X + col * SQ_SIZE
            y = row * SQ_SIZE

            color = LIGHT if (row + col) % 2 == 0 else DARK
            pygame.draw.rect(screen, color, (x, y, SQ_SIZE, SQ_SIZE))

            square = chess.square(col, 7 - row)

            if last_move and square in (
                last_move.from_square, last_move.to_square
            ):
                pygame.draw.rect(
                    screen, YELLOW, (x, y, SQ_SIZE, SQ_SIZE), 4
                )

            if hint_move and square in (
                hint_move.from_square, hint_move.to_square
            ):
                pygame.draw.rect(
                    screen, PURPLE, (x, y, SQ_SIZE, SQ_SIZE), 4
                )

            if selected_square == square:
                pygame.draw.rect(
                    screen, BLUE, (x, y, SQ_SIZE, SQ_SIZE), 4
                )

            piece = board.piece_at(square)

            if piece:
                symbol = PIECES[piece.symbol()]
                piece_text = FONT.render(symbol, True, BLACK)
                rect = piece_text.get_rect(
                    center=(x + SQ_SIZE // 2, y + SQ_SIZE // 2)
                )
                screen.blit(piece_text, rect)

    # Green circles = legal moves.
    for target in legal_targets:
        x = BOARD_X + chess.square_file(target) * SQ_SIZE
        y = (7 - chess.square_rank(target)) * SQ_SIZE
        centre = (x + SQ_SIZE // 2, y + SQ_SIZE // 2)

        if board.piece_at(target):
            pygame.draw.circle(
                screen, GREEN, centre, SQ_SIZE // 2 - 5, 4
            )
        else:
            pygame.draw.circle(screen, GREEN, centre, 9)


# ==================== GAME RESULT ====================
def get_result_text():
    if board.is_checkmate():
        if board.turn == chess.WHITE:
            return "Computer wins by checkmate"
        return "You win by checkmate!"

    if board.is_stalemate():
        return "Draw by stalemate"

    if board.is_insufficient_material():
        return "Draw: insufficient material"

    if board.is_game_over():
        return "Game drawn"

    return "Game in progress"


# ==================== REPORT ====================
def draw_report():
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((15, 20, 30, 220))
    screen.blit(overlay, (0, 0))

    panel = pygame.Rect(80, 145, WIDTH - 160, 500)
    pygame.draw.rect(screen, GREY, panel, border_radius=18)

    title = TITLE_FONT.render("AI CHESS COACH REPORT", True, BLACK)
    screen.blit(title, (panel.x + 22, panel.y + 20))

    level_name = {1: "Easy", 2: "Medium", 3: "Strong"}[difficulty]

    lines = [
        get_result_text(),
        "",
        f"Your moves: {player_moves}",
        f"Your captures: {player_captures}",
        f"Computer captures: {ai_captures}",
        f"Good moves detected: {good_moves}",
        f"Risk warnings: {mistakes}",
        f"Final AI level: {level_name}",
        "",
        "Recent coach feedback:"
    ]

    y = panel.y + 70

    for line in lines:
        color = RED if "warning" in line.lower() else BLACK
        text = STATUS_FONT.render(line, True, color)
        screen.blit(text, (panel.x + 22, y))
        y += 24

    for item in feedback_history[-3:]:
        # Wrap long feedback into readable lines.
        words = item.split()
        current = ""

        for word in words:
            test = current + " " + word if current else word

            if SMALL_FONT.size(test)[0] > panel.width - 45:
                screen.blit(
                    SMALL_FONT.render(current, True, BLACK),
                    (panel.x + 25, y)
                )
                y += 19
                current = word
            else:
                current = test

        if current and y < panel.bottom - 45:
            screen.blit(
                SMALL_FONT.render(current, True, BLACK),
                (panel.x + 25, y)
            )
            y += 20

        if y >= panel.bottom - 45:
            break

    hint = STATUS_FONT.render(
        "Press R to play again | ESC to exit", True, BLUE
    )
    screen.blit(hint, (panel.x + 22, panel.bottom - 35))


# ==================== STATUS AREA ====================
def draw_status():
    pygame.draw.rect(
        screen, (245, 245, 245),
        (0, BOARD_SIZE, WIDTH, HEIGHT - BOARD_SIZE)
    )

    if board.is_game_over():
        message = get_result_text()
    elif board.turn == chess.BLACK:
        message = "Computer is thinking..."
    else:
        message = feedback

    # Keep long feedback inside the screen.
    if STATUS_FONT.size(message)[0] > WIDTH - 24:
        message = message[:85] + "..."

    screen.blit(
        STATUS_FONT.render(message, True, BLACK),
        (12, BOARD_SIZE + 8)
    )

    level_name = {1: "Easy", 2: "Medium", 3: "Strong"}[difficulty]

    info = (
        f"AI: {level_name} | Good: {good_moves} | "
        f"Warnings: {mistakes} | Captures: {player_captures}"
    )
    screen.blit(
        SMALL_FONT.render(info, True, BLACK),
        (12, BOARD_SIZE + 35)
    )

    controls = "H = Hint    R = Restart    ESC = Exit"
    screen.blit(
        SMALL_FONT.render(controls, True, BLACK),
        (12, BOARD_SIZE + 56)
    )

    if hint_move:
        san = board.san(hint_move) if hint_move in board.legal_moves else ""
        hint_text = f"Hint: {san} (purple squares)"
        screen.blit(
            SMALL_FONT.render(hint_text, True, PURPLE),
            (12, BOARD_SIZE + 76)
        )


# ==================== MAIN LOOP ====================
def main():
    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    reset_game()
                elif event.key == pygame.K_h:
                    get_best_hint()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    handle_click(event.pos)

        # Computer plays Black automatically.
        if not board.is_game_over() and board.turn == chess.BLACK:
            computer_move()

        screen.fill(WHITE)
        draw_board()
        draw_status()

        if board.is_game_over():
            draw_report()

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
