# King's Deck Ultima — Project Documentation

## 1. Project overview

King's Deck Ultima is a chess-inspired, turn-based game built with Streamlit and AgentPy. The player controls one king and selects movement cards that change how it can move. Enemy pieces use chess movement rules and a rule-based agent to pursue the player's king, avoid immediate capture threats, and protect their own king when possible.

The project includes five curated enemy levels and a sixth, one-on-one boss level. In the final level, the Card King has a five-card movement hand and three health. The player must capture the boss three times; it respawns on a random unoccupied square after each non-final hit.

### How to Open
1. Open files on VS code workplace
2. Install python and create env. and then install the required extension (In the requirements.txt)
3. Type -m streamlit run app.py in Terminal or open run_game.bat

## 2. Features

### Player and movement cards

- The player controls a single king on an 8×8 board.
- Each hand contains five randomly selected cards: two Slider cards, two Leaper cards, and one Compound card.
- An unused card enables its movement pattern for the player's king. Used cards are disabled for the rest of the hand.
- The player may reshuffle the unused cards once per hand. Used cards keep their status.
- After all five cards are used, a new hand is dealt.
- The card pool includes standard chess patterns and custom patterns. Examples include Lion's two-step or jump movement, Checker capture chains, and Zeus's Smite teleport captures.
- En passant can be captured using any player card when its conditions are met.

### Levels and outcomes

| Level | Name | Layout or objective |
| --- | --- | --- |
| 1 | First Steps | Enemy king, pawn, and knight |
| 2 | Full Set | A rook, knight, bishop, queen, king, and pawn |
| 3 | Full Castle | Major chess pieces with a full pawn row |
| 4 | Guarded Castle | Expanded rooks, knights, and pawns, plus a queen and king |
| 5 | Queen's Gambit | Dense layout with extra pieces and two queens |
| 6 | The Card King | One-on-one boss fight; capture the boss three times |

Regular levels are cleared by capturing the enemy king or all enemy pieces. The boss level is cleared after the boss loses all three health points. The player loses if an enemy captures the player's king.

### Final boss

- The Card King draws five movement cards using the same slot categories as the player.
- The boss can move with any unused card that permits the selected move.
- A matching card is spent after the boss moves. After all five cards are spent, the boss draws a new hand.
- When captured, the boss loses one health point. If it still has health, it respawns on a random unoccupied board square.
- The interface displays boss health icons and descriptions of the boss's current cards below the board.

## 3. System design

### Main components

| Component | Responsibility |
| --- | --- |
| `app.py` | Streamlit interface, session state, level and card controls, board component, and replay presentation |
| `game_model.py` | AgentPy model, board state, agents, card pools, movement validation, capture resolution, enemy AI, level layouts, and replay snapshots |
| `requirements.txt` | Python package dependencies |
| `run_game.bat` | Windows launcher for the Streamlit app |

### Model structure

- `CardChessModel` is the central AgentPy model. It creates an AgentPy grid, initializes the player and enemy agents, owns card hands, validates moves, applies captures, and resolves turns.
- `KingAgent` represents the player-controlled king.
- `EnemyAgent` represents enemy chess pieces. In the final level, an `EnemyAgent` also carries boss health and a movement-card hand.
- The board state is authoritative in the model. The Streamlit component sends a requested destination to the model; the model checks that the move is legal before applying it.
- Replay history stores board snapshots and labels as moves happen. The interface uses these snapshots only after a win.

### Turn flow

1. The player selects an unused movement card.
2. The board shows destinations permitted by that card and current occupancy.
3. The player drags the king to a destination.
4. The model validates the move, applies captures, marks the card as used, and checks for a win.
5. If the game continues, the enemy AI evaluates its legal moves and executes one.
6. The interface rerenders the board and status. If the player's hand is exhausted, a new five-card hand is dealt according to the card rules.

## 4. Enemy AI: rule-based decision logic

### Design summary

The enemy is a heuristic, one-ply agent. It considers legal moves available in the current position, estimates immediate player capture threats after each candidate move, assigns priorities, and selects the highest-scoring candidate. It does not search several turns ahead or use minimax, a learned policy, or a neural network.

The core implementation is in `CardChessModel._enemy_destinations`, `CardChessModel._player_threat_count`, `CardChessModel._threat_counts_after_enemy_move`, and `CardChessModel._take_enemy_turn` in `game_model.py`.

### Candidate generation

1. Iterate through living enemies in round-robin order, starting from `enemy_turn_index`.
2. For each enemy, scan the board for destinations allowed by its movement rules.
3. Exclude its current square and squares occupied by another enemy. The player's king square remains a valid destination because it can be captured.
4. For ordinary enemies, movement rules cover the enemy piece types used by the levels: Pawn, King, Knight, Rook, Bishop, and Queen.
5. For the boss, a destination is legal when at least one unused boss card permits that movement.

If no living enemy has any legal destination, the model reports that every enemy piece is blocked and has no legal move.

### Threat estimation

For each candidate that does not capture the player:

- Temporarily move the candidate piece to the proposed destination.
- Count the player's unused cards that could capture the moved piece.
- If the enemy king or boss exists, also count the player's unused cards that could capture that king.
- Restore the original board position before evaluating another candidate.

The player threat count is based on the player's actual legal destinations for each unused card. For Checker, the threat check accounts for the longest available capture chain.

### Lexicographic move score

The AI scores each candidate with this tuple and chooses the maximum tuple in lexicographic order:

```text
(
    captures_player_king,
    king_defense_priority,
    -king_threats_after,
    not_threatened,
    moves_closer,
    -distance_to_player,
    -round_robin_offset,
)
```

Each field has the following meaning:

| Priority | Score field | Meaning |
| --- | --- | --- |
| 1 | `captures_player_king` | Prefer a move that captures the player's king above every other move. |
| 2 | `king_defense_priority` | When the enemy king or boss is threatened, prefer moves that protect it. |
| 3 | `-king_threats_after` | Prefer fewer player cards that can capture the enemy king after the move. |
| 4 | `not_threatened` | Prefer a destination the player's current hand cannot capture. |
| 5 | `moves_closer` | Prefer a move that reduces distance to the player's king. |
| 6 | `-distance_to_player` | If still tied, prefer a smaller distance to the player's king. |
| 7 | `-round_robin_offset` | Prefer the earliest enemy in the current rotation to break ties fairly. |

Distance uses the Chebyshev metric:

```text
distance(a, b) = max(abs(a.x - b.x), abs(a.y - b.y))
```

This treats diagonal and orthogonal king steps as equal distance.

### Enemy king defense priority

When the enemy king or boss is currently threatened by one or more unused player cards, each candidate gets a defense priority:

| Condition after candidate move | Priority |
| --- | ---: |
| Removes all threats to the enemy king | 3 |
| Reduces the number of threats | 2 |
| Moves the enemy king itself, but does not reduce threats | 1 |
| Does not improve king safety | 0 |

If the enemy king is not threatened before the move, all candidates receive defense priority 0.

### Decision pseudocode

```text
function take_enemy_turn:
    if there are no living enemies:
        return

    locate the player's king
    locate the enemy king or boss, if present
    count current player-card threats to the enemy king
    candidates = []

    for each living enemy in round-robin order:
        for each legal destination:
            if destination is the player's king:
                mark as a king capture
            else:
                simulate the move temporarily
                count threats to the moved piece and enemy king
                restore the board

            calculate king-defense priority
            calculate whether the move avoids capture
            calculate whether it moves closer and its distance
            append the move and its score to candidates

    if candidates is empty:
        report that all enemies are blocked
    else:
        choose the candidate with the highest lexicographic score
        advance the round-robin starting position
        if it captures the player's king:
            end the game as an enemy win
        otherwise:
            execute the move
            if the mover is the boss:
                spend a matching movement card
                draw a new boss hand after all five are spent
```

## 5. AI characteristics and evaluation notes

### Strengths

- The rules and priorities are explicit, explainable, and straightforward to evaluate.
- The AI checks legal movement rather than selecting arbitrary board squares.
- It balances pursuit with immediate safety and enemy-king defense.
- Its round-robin tie breaker prevents the same piece from always winning otherwise equal choices.
- The boss uses the same strategic scoring while being constrained by its card hand.

### Limitations

- The agent evaluates immediate candidate moves only; it does not plan a multi-turn sequence.
- Safety against the player's hand is estimated from currently unused cards. It does not model future draws or reshuffles.
- For ordinary threatened enemy pieces, the score distinguishes threatened from safe, but does not reward reducing the number of cards that threaten a piece. The enemy king/boss receives a separate threat-count priority.
- When every enemy piece is blocked, the AI cannot make a move and reports that condition.
- Tie-breaking is systematic rather than random; randomness is used for card draws and boss respawn placement.

## 6. Running the project

Install packages from `requirements.txt`, then run:

```bash
streamlit run app.py
```

On Windows, `run_game.bat` can be used as a launcher if Python and the required packages are installed.
