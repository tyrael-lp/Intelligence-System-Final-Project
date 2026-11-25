"""Streamlit interface for the AgentPy card-driven king game.

Run with: streamlit run app.py
"""

import streamlit as st

from game_model import LEVEL_DESCRIPTIONS, LEVEL_NAMES, MAX_LEVEL, CardChessModel


st.set_page_config(page_title="King's Deck Ultima", page_icon="♔", layout="wide")

CARD_HELP = {
    "Pawn": "Move forward one square or capture diagonally. En passant works with any card.",
    "King": "Move one square in any direction.",
    "Rook": "Slide any distance horizontally or vertically.",
    "Bishop": "Slide any distance diagonally.",
    "Stag": "Slide vertically, or move one square in any direction.",
    "Ox": "Slide vertically or diagonally; not sideways.",
    "Boar": "Slide sideways or diagonally; not forward or backward.",
    "Lion": "Jump up to two squares, or take two adjacent steps. Can capture twice or return to its start.",
    "Elephant": "Jump exactly two squares diagonally.",
    "Camel": "Leap in a (3, 1) pattern.",
    "Knight": "Leap in an L shape: two squares, then one perpendicular.",
    "Centaur": "Leap like a knight or move one square diagonally.",
    "Okapi": "Leap like a knight or a zebra (2, 3).",
    "Zebra": "Leap in a (2, 3) pattern.",
    "Lancer": "Leap two squares orthogonally or in a (2, 1) pattern.",
    "Phoenix": "Move one square orthogonally or jump two squares diagonally.",
    "Kirin": "Move one square diagonally or jump two squares orthogonally.",
    "Wizard": "Move one square diagonally or leap in a (3, 1) orthogonal pattern.",
    "Checker": "Move one square diagonally forward, or jump diagonally over an enemy. Capture chains continue automatically.",
    "Queen": "Slide any distance horizontally, vertically, or diagonally.",
    "Zeus's Smite": "Teleport to any enemy-occupied square and capture that enemy.",
    "Dragon Horse": "Slide diagonally or move one square orthogonally.",
    "Dragon King": "Slide horizontally or vertically, or move one square diagonally.",
    "Princess": "Combine bishop slides and knight leaps.",
    "Empress": "Combine rook slides and knight leaps.",
    "Amazon": "Combine queen moves and knight leaps.",
}


def reset_game():
    level = st.session_state.game_model.level
    st.session_state.game_model = CardChessModel(level=level)
    st.session_state.last_move_id = None
    st.session_state.selected_card = 0
    st.session_state.replay_id = st.session_state.get("replay_id", 0) + 1


def select_level():
    level = st.session_state.selected_level
    st.session_state.game_model = CardChessModel(level=level)
    st.session_state.last_move_id = None
    st.session_state.selected_card = 0
    st.session_state.replay_id = st.session_state.get("replay_id", 0) + 1


def select_card(card_index):
    cards = st.session_state.game_model.cards
    if 0 <= card_index < len(cards) and not cards[card_index]["used"]:
        st.session_state.selected_card = card_index


def reshuffle_cards():
    game = st.session_state.game_model
    if game.reshuffle_remaining_cards():
        available = next(
            (index for index, card in enumerate(game.cards) if not card["used"]),
            0,
        )
        st.session_state.selected_card = available


def replay_winning_game():
    """Restart browser playback of the recorded winning game."""
    st.session_state.replay_id = st.session_state.get("replay_id", 0) + 1


def handle_board_move():
    """Send the board component's drag event to the AgentPy model."""
    component_state = st.session_state.get("king_board", {})
    event = component_state.get("move")
    if not isinstance(event, dict):
        return

    move_id = event.get("id")
    if not move_id or move_id == st.session_state.get("last_move_id"):
        return
    st.session_state.last_move_id = move_id

    card_index = st.session_state.get("selected_card", 0)
    moved = st.session_state.game_model.play_card_move(
        event.get("to"), card_index=card_index
    )
    if moved:
        next_available = next(
            (
                index
                for index, card in enumerate(st.session_state.game_model.cards)
                if not card["used"]
            ),
            0,
        )
        st.session_state.selected_card = next_available


def render_board(position, legal_destinations, pieces, replay_frames, replay_id):
    """Render the board and report drag-and-drop events to Streamlit."""
    board_component = st.components.v2.component(
        name="card_chess_drag_board",
        html='''
            <div id="board" aria-label="Chess board"></div>
            <div id="replay-status" aria-live="polite"></div>
            <div id="replay-controls" aria-label="Replay controls" hidden>
                <button id="replay-prev" type="button" aria-label="Previous turn">◀ Previous</button>
                <button id="replay-toggle" type="button">Pause</button>
                <button id="replay-next" type="button" aria-label="Next turn">Next ▶</button>
            </div>
        ''',
        css="""
            #board {
                display: grid;
                grid-template-columns: repeat(8, minmax(34px, 1fr));
                grid-template-rows: repeat(8, minmax(0, 1fr));
                width: min(100%, 560px);
                aspect-ratio: 1 / 1;
                margin: 0 auto;
                border: 4px solid #28313b;
                border-radius: 4px;
                overflow: hidden;
                user-select: none;
            }
            #replay-status {
                min-height: 1.5rem;
                margin: 0.5rem auto 0;
                width: min(100%, 560px);
                text-align: center;
                font-size: 0.9rem;
                color: var(--st-text-color);
            }
            #replay-controls {
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 0.5rem;
                width: min(100%, 560px);
                margin: 0 auto 0.5rem;
            }
            #replay-controls[hidden] { display: none; }
            #replay-controls button {
                border: 1px solid #87909b;
                border-radius: 0.4rem;
                padding: 0.35rem 0.7rem;
                cursor: pointer;
            }
            .square {
                display: flex;
                align-items: center;
                justify-content: center;
                position: relative;
                min-width: 0;
                min-height: 0;
            }
            .light { background: #eee4cf; }
            .dark { background: #77936f; }
            .legal-destination.light { background: #f2cf64; }
            .legal-destination.dark { background: #c8a93e; }
            .capture-destination { box-shadow: inset 0 0 0 5px #c44536; }
            .legal-destination::after {
                content: "";
                position: absolute;
                left: 50%;
                top: 50%;
                width: 22%;
                aspect-ratio: 1 / 1;
                border-radius: 50%;
                background: #24312466;
                transform: translate(-50%, -50%);
                pointer-events: none;
            }
            .capture-destination::after { display: none; }
            .piece, .square-spacer {
                display: block;
                font-size: clamp(1.25rem, 5vw, 2.3rem);
                line-height: 1;
            }
            .player { cursor: grab; filter: drop-shadow(0 2px 1px #3338); }
            .boss { color: #a31224; filter: drop-shadow(0 2px 2px #2229); }
            .player:active { cursor: grabbing; }
            .square-spacer { visibility: hidden; }
            .square.drop-target { outline: 4px solid #e8b949; outline-offset: -5px; }
        """,
        js="""
            export default function(component) {
                const { parentElement, data, setTriggerValue } = component;
                const board = parentElement.querySelector('#board');
                const status = parentElement.querySelector('#replay-status');
                const controls = parentElement.querySelector('#replay-controls');
                const previousButton = parentElement.querySelector('#replay-prev');
                const toggleButton = parentElement.querySelector('#replay-toggle');
                const nextButton = parentElement.querySelector('#replay-next');
                if (!board) return;

                const renderBoard = (pieceList, destinations = []) => {
                    const legalSquares = new Set(
                        destinations.map(([x, y]) => `${x},${y}`)
                    );
                    const pieceMap = new Map(
                        (pieceList || []).map((piece) => [`${piece.x},${piece.y}`, piece])
                    );
                    board.innerHTML = '';
                    for (let y = 0; y < 8; y++) {
                        for (let x = 0; x < 8; x++) {
                            const square = document.createElement('div');
                            square.className = `square ${(x + y) % 2 === 0 ? 'light' : 'dark'}`;
                            square.dataset.x = x;
                            square.dataset.y = y;
                            if (legalSquares.has(`${x},${y}`)) {
                                square.classList.add('legal-destination');
                            }
                            const pieceData = pieceMap.get(`${x},${y}`);
                            if (pieceData && pieceData.kind === 'enemy' && legalSquares.has(`${x},${y}`)) {
                                square.classList.add('capture-destination');
                            }
                            if (pieceData) {
                                const piece = document.createElement('span');
                                piece.className = `piece ${pieceData.kind}`;
                                piece.textContent = pieceData.symbol;
                                if (pieceData.kind === 'player') {
                                    piece.draggable = true;
                                    piece.title = 'Drag the king to a destination square';
                                    piece.addEventListener('dragstart', (event) => {
                                        event.dataTransfer.setData('text/plain', 'king');
                                        event.dataTransfer.effectAllowed = 'move';
                                    });
                                } else {
                                    piece.title = `Enemy ${pieceData.symbol}`;
                                }
                                square.appendChild(piece);
                            } else {
                                const spacer = document.createElement('span');
                                spacer.className = 'square-spacer';
                                spacer.textContent = '♔';
                                spacer.setAttribute('aria-hidden', 'true');
                                square.appendChild(spacer);
                            }
                            square.addEventListener('dragover', (event) => {
                                event.preventDefault();
                                event.dataTransfer.dropEffect = 'move';
                                square.classList.add('drop-target');
                            });
                            square.addEventListener('dragleave', () => square.classList.remove('drop-target'));
                            square.addEventListener('drop', (event) => {
                                event.preventDefault();
                                square.classList.remove('drop-target');
                                if (event.dataTransfer.getData('text/plain') !== 'king') return;
                                setTriggerValue('move', {
                                    id: `${Date.now()}-${Math.random()}`,
                                    to: [Number(square.dataset.x), Number(square.dataset.y)]
                                });
                            });
                            board.appendChild(square);
                        }
                    }
                };

                if (board._replayTimer) {
                    clearInterval(board._replayTimer);
                    board._replayTimer = null;
                }

                const frames = data.replayFrames || [];
                if (data.replayEnabled && frames.length > 0) {
                    const replayKey = String(data.replayId);
                    if (board.dataset.replayKey !== replayKey) {
                        board.dataset.replayKey = replayKey;
                        board._replayIndex = 0;
                        board.dataset.replayComplete = frames.length === 1 ? 'true' : 'false';
                        board._replayPlaying = frames.length > 1;
                    }
                    controls.hidden = false;

                    const showFrame = () => {
                        const frame = frames[board._replayIndex];
                        if (!frame) return;
                        renderBoard(frame.pieces);
                        status.textContent = board.dataset.replayComplete === 'true'
                            ? 'Replay complete'
                            : `${frame.label} (${board._replayIndex + 1}/${frames.length})`;
                        previousButton.disabled = board._replayIndex === 0;
                        nextButton.disabled = board._replayIndex === frames.length - 1;
                        toggleButton.textContent = board._replayPlaying ? 'Pause' : 'Play';
                    };
                    const stopReplay = () => {
                        if (board._replayTimer) clearInterval(board._replayTimer);
                        board._replayTimer = null;
                    };
                    const advance = () => {
                        if (board._replayIndex < frames.length - 1) {
                            board._replayIndex += 1;
                            showFrame();
                        }
                        if (board._replayIndex >= frames.length - 1) {
                            board._replayPlaying = false;
                            board.dataset.replayComplete = 'true';
                            stopReplay();
                            showFrame();
                        }
                    };
                    const startReplay = () => {
                        stopReplay();
                        if (board._replayPlaying && board._replayIndex < frames.length - 1) {
                            board._replayTimer = setInterval(advance, 700);
                        }
                    };

                    previousButton.onclick = () => {
                        board._replayPlaying = false;
                        stopReplay();
                        board.dataset.replayComplete = 'false';
                        board._replayIndex = Math.max(0, board._replayIndex - 1);
                        showFrame();
                    };
                    nextButton.onclick = () => {
                        board._replayPlaying = false;
                        stopReplay();
                        board.dataset.replayComplete = 'false';
                        advance();
                    };
                    toggleButton.onclick = () => {
                        if (board._replayPlaying) {
                            board._replayPlaying = false;
                            stopReplay();
                            showFrame();
                        } else {
                            if (board._replayIndex >= frames.length - 1) {
                                board._replayIndex = 0;
                                board.dataset.replayComplete = 'false';
                            }
                            board._replayPlaying = true;
                            showFrame();
                            startReplay();
                        }
                    };
                    showFrame();
                    startReplay();
                } else {
                    board.dataset.replayKey = '';
                    board.dataset.replayComplete = 'false';
                    board._replayIndex = 0;
                    board._replayPlaying = false;
                    if (controls) controls.hidden = true;
                    renderBoard(data.pieces || [], data.legalDestinations || []);
                    if (status) status.textContent = '';
                }

                return () => {
                    if (board._replayTimer) {
                        clearInterval(board._replayTimer);
                        board._replayTimer = null;
                    }
                };
            }
        """,
    )

    board_component(
        data={
            "position": position,
            "legalDestinations": legal_destinations,
            "pieces": pieces,
            "replayFrames": replay_frames,
            "replayEnabled": bool(replay_frames),
            "replayId": replay_id,
        },
        key="king_board",
        on_move_change=handle_board_move,
    )


if (
    "game_model" not in st.session_state
    or not hasattr(st.session_state.game_model, "enemies")
    or not hasattr(st.session_state.game_model, "level")
    or not hasattr(st.session_state.game_model, "reshuffle_remaining_cards")
):
    st.session_state.game_model = CardChessModel(level=1)
    st.session_state.last_move_id = None
    st.session_state.selected_card = 0
    st.session_state.replay_id = st.session_state.get("replay_id", 0)

if "selected_level" not in st.session_state:
    st.session_state.selected_level = st.session_state.game_model.level
elif st.session_state.selected_level not in range(1, MAX_LEVEL + 1):
    st.session_state.selected_level = st.session_state.game_model.level
elif st.session_state.selected_level != st.session_state.game_model.level:
    st.session_state.game_model = CardChessModel(level=st.session_state.selected_level)

game = st.session_state.game_model
selected_index = st.session_state.get("selected_card", 0)
if game.cards:
    if (
        not isinstance(selected_index, int)
        or not 0 <= selected_index < len(game.cards)
        or game.cards[selected_index]["used"]
    ):
        selected_index = next(
            (index for index, card in enumerate(game.cards) if not card["used"]),
            0,
        )
        st.session_state.selected_card = selected_index
    legal_destinations = game.legal_destinations(selected_index)
else:
    legal_destinations = []
if "replay_id" not in st.session_state:
    st.session_state.replay_id = 0
replay_frames = game.get_winning_replay()

st.title("♔ King's Deck Ultima")
st.selectbox(
    "Select level",
    options=list(range(1, MAX_LEVEL + 1)),
    format_func=lambda level: f"Level {level}: {LEVEL_NAMES[level]}",
    key="selected_level",
    on_change=select_level,
)
game = st.session_state.game_model
st.subheader(f"Level {game.level}: {LEVEL_NAMES[game.level]}")
st.caption(LEVEL_DESCRIPTIONS[game.level])
st.caption("Drag the king to move. Gold squares are legal moves; red borders mark enemy captures.")

st.subheader("Your five movement cards")
card_columns = st.columns(5)
for index, card in enumerate(game.cards):
    with card_columns[index]:
        st.caption(card["category"])
        label = f"✓ {card['name']}" if card["used"] else card["name"]
        st.button(
            label,
            key=f"movement_card_{index}",
            type="primary" if index == selected_index and not card["used"] else "secondary",
            disabled=card["used"] or game.game_over,
            on_click=select_card,
            args=(index,),
            use_container_width=True,
        )

if game.remaining_card_count:
    selected_card = game.cards[selected_index]
    st.info(
        f"**Selected: {selected_card['name']} ({selected_card['category']}).** "
        f"{CARD_HELP[selected_card['name']]}"
    )
else:
    st.info("All cards in this hand have been used.")

left, right = st.columns([1.35, 1], gap="large")
with left:
    render_board(
        game.player_position,
        legal_destinations,
        game.pieces_on_board(),
        replay_frames,
        st.session_state.replay_id,
    )
    if game.boss is not None:
        health = game.boss.health
        st.subheader("Card King")
        st.markdown(
            f"**Health:** {'❤️ ' * health}{'🖤 ' * (3 - health)} "
            f"({health} / 3 captures remaining)"
        )
        st.caption("Capture the boss three times. After each hit, it reappears on a random empty square.")
        st.subheader("Boss movement cards")
        boss_columns = st.columns(5)
        for index, card in enumerate(game.boss.cards):
            with boss_columns[index]:
                st.caption(card["category"])
                st.markdown(f"**{card['name']}**")
                st.caption(CARD_HELP[card["name"]])
                if card["used"]:
                    st.caption("Used")
with right:
    st.subheader("Hand controls")
    st.write(f"Cards remaining: {game.remaining_card_count} / 5")
    st.button(
        "Reshuffle remaining cards",
        key="reshuffle_cards",
        on_click=reshuffle_cards,
        disabled=game.reshuffle_used or game.remaining_card_count == 0 or game.game_over,
    )
    reshuffle_text = "Reshuffle already used this hand." if game.reshuffle_used else "One reshuffle is available per five-card hand."
    st.caption(reshuffle_text)

    st.metric("Player moves", game.move_count)
    st.metric("Enemy pieces remaining", len(game.living_enemies))
    st.caption("Enemy types: ♟ Pawn · ♜ Rook · ♞ Knight · ♝ Bishop · ♛ Queen · ♚ King")
    if game.outcome == "level_complete":
        if game.boss is not None:
            st.success("The Card King is defeated! You won the final level.")
        else:
            st.success(f"Level {game.level} cleared! Select another level or replay this one.")
        st.button("Replay winning game", on_click=replay_winning_game)
    elif game.outcome == "enemy_win":
        st.error("Your king was captured. The enemies win.")
    st.write(game.message)
    st.button("Restart level", on_click=reset_game, type="secondary")

st.divider()
st.caption(
    "Enemies read your hand and avoid squares your cards can capture when possible, while pursuing the king. "
    "Capture the enemy king or all enemy pieces to clear a level; defeat the final boss by capturing it three times. "
    "Lose if an enemy captures your king."
)
