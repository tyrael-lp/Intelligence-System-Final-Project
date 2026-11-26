"""AgentPy model and agents for the card-driven king game."""

import agentpy as ap


BOARD_SIZE = 8
CARD_POOLS = {
    "Slider": ("Pawn", "Checker", "King", "Rook", "Bishop", 
               "Cannon", "Stag", "Dragon Horse", "Dragon King", "Lion"),
    "Leaper": (
        "Elephant", "Camel", "Knight", "Phoenix", "Kirin", 
        "Wizard", "Centaur", "Okapi", "Zebra", "Lancer",
    ),
    "Compound": (
        "Queen", "Zeus's Smite", "Ox", "Boar", "Princess", 
        "Empress", "Amazon", "Poseidon's Trident", "Hades' Underworld",
    ),
}
CARD_SLOT_CATEGORIES = ("Slider", "Slider", "Leaper", "Leaper", "Compound")
ENEMY_LAYOUT = (
    ("Rook", (0, 0)),
    ("Knight", (2, 1)),
    ("Bishop", (5, 0)),
    ("Queen", (7, 2)),
    ("King", (3, 0)),
    ("Pawn", (4, 3)),
)
LEVEL_LAYOUTS = {
    1: (
        ("King", (4, 0)),
        ("Pawn", (4, 2)),
        ("Knight", (1, 1)),
    ),
    2: ENEMY_LAYOUT,
    3: (
        ("Rook", (0, 0)), ("Knight", (1, 0)), ("Bishop", (2, 0)),
        ("Queen", (3, 0)), ("King", (4, 0)), ("Bishop", (5, 0)),
        ("Knight", (6, 0)), ("Rook", (7, 0)),
        *(("Pawn", (x, 1)) for x in range(8)), 
    ),
    4: (
        ("Rook", (0, 0)), ("Knight", (1, 0)), ("Bishop", (2, 0)),
        ("Queen", (3, 0)), ("King", (4, 0)), ("Bishop", (5, 0)),
        ("Knight", (6, 0)), ("Rook", (7, 0)),
        *(("Pawn", (x, 1)) for x in range(2, 6)),
        ("Rook", (0, 1)), ("Knight", (1, 1)), ("Knight", (7, 1)), ("Rook", (6, 1)),
    ),
    5: (
        ("Rook", (0, 0)), ("Knight", (1, 0)), ("Bishop", (2, 0)),
        ("Queen", (3, 0)), ("King", (4, 0)), ("Bishop", (5, 0)),
        ("Knight", (6, 0)), ("Rook", (7, 0)),
        *(("Pawn", (x, 1)) for x in range(2, 6)),
        ("Rook", (0, 2)), ("Knight", (2, 2)), ("Bishop", (5, 2)),
        ("Pawn", (1, 2)), ("Pawn", (6, 2)), ("Queen", (7, 3)),
    ),
    6: (("Boss", (4, 0)),),
}
LEVEL_NAMES = {
    1: "First Steps",
    2: "Full Set",
    3: "Full Castle",
    4: "Guarded Castle",
    5: "Queen's Gambit",
    6: "The Card King",
}
LEVEL_DESCRIPTIONS = {
    1: "An enemy king, pawn, and knight introduce enemy movement.",
    2: "One enemy of each chess piece type.",
    3: "Complete chess set with pawns in front.",
    4: "Four rooks, four knights, two bishops, four pawns, one queen, and one king.",
    5: "Three rooks, three knights, three bishops, ten pawns, two queens, and one king.",
    6: "Face the Card King alone. Capture the boss three times to win.",
}
MAX_LEVEL = max(LEVEL_LAYOUTS)
PIECE_SYMBOLS = {
    "Player": "♔",
    "Pawn": "♟",
    "Rook": "♜",
    "Knight": "♞",
    "Bishop": "♝",
    "Queen": "♛",
    "King": "♚",
    "Boss": "♚",
}
BOSS_LEVEL = 6
BOSS_MAX_HEALTH = 3


class KingAgent(ap.Agent):
    """The player-controlled king agent."""

    def setup(self, position=(4, 7)):
        self.position = tuple(position)
        self.role = "player"


class EnemyAgent(ap.Agent):
    """An enemy chess piece that pursues the player king."""

    def setup(self, piece_type, position):
        self.piece_type = piece_type
        self.position = tuple(position)
        self.role = "enemy"
        self.alive = True
        self.is_boss = piece_type == "Boss"
        self.health = BOSS_MAX_HEALTH if self.is_boss else None
        self.cards = []
        # Compound cards the Card King has actually used this level.
        self.played_compound_cards = []


class CardChessModel(ap.Model):
    """Owns the board, agents, movement rules, and turn resolution."""

    def __init__(self, seed=None, level=1):
        if level not in LEVEL_LAYOUTS:
            raise ValueError(f"Level must be between 1 and {MAX_LEVEL}.")
        parameters = {"seed": seed} if seed is not None else None
        super().__init__(parameters=parameters)
        if seed is not None:
            self.random.seed(seed)
        self.level = level
        # AgentPy normally calls setup when a simulation is run. The Streamlit
        # interface also needs an initialized model before any run() call.
        self.setup()

    def setup(self, **kwargs):
        if "level" in kwargs:
            self.level = kwargs["level"]
        self.grid = ap.Grid(self, (BOARD_SIZE, BOARD_SIZE))
        self.player = KingAgent(self, position=(4, 7))
        self.enemies = [
            EnemyAgent(self, piece_type=kind, position=position)
            for kind, position in LEVEL_LAYOUTS[self.level]
        ]
        self.boss = next((enemy for enemy in self.enemies if enemy.is_boss), None)
        if self.boss is not None:
            self.boss.cards = self._draw_hand()
        agents = [self.player, *self.enemies]
        positions = [agent.position for agent in agents]
        self.grid.add_agents(agents, positions=positions)
        self.cards = self._draw_hand()
        self.reshuffle_used = False
        self.shuffle_count = 1
        self.en_passant_target = None
        self.en_passant_victim = None
        # Compound cards that have actually been played this level. Hades'
        # Underworld can copy one of these cards on a later turn.
        self.played_compound_cards = []
        self.move_count = 0
        self.enemy_turn_index = 0
        self.message = "Drag the king to a highlighted square."
        self.game_over = False
        self.outcome = None
        # Details shown by the interface when an enemy captures the player king.
        self.loss_details = None
        self.history = []
        self._record_frame("Starting position")

    def _draw_hand(self):
        """Deal two slider, two leaper, and one compound card."""
        return [
            {
                "category": category,
                "name": self.random.choice(CARD_POOLS[category]),
                "used": False,
            }
            for category in CARD_SLOT_CATEGORIES
        ]

    @property
    def remaining_card_count(self):
        return sum(not card["used"] for card in self.cards)

    def reshuffle_remaining_cards(self):
        """Replace only unused cards, retaining their category slots."""
        if self.game_over:
            self.message = "The level is over; cards cannot be reshuffled."
            return False
        if self.reshuffle_used:
            self.message = "You have already reshuffled this hand."
            return False

        remaining = [card for card in self.cards if not card["used"]]
        if not remaining:
            self.message = "There are no remaining cards to reshuffle."
            return False

        for card in remaining:
            pool = CARD_POOLS[card["category"]]
            alternatives = [name for name in pool if name != card["name"]]
            card["name"] = self.random.choice(alternatives or pool)

        self.reshuffle_used = True
        self.message = f"Reshuffled {len(remaining)} remaining cards."
        return True

    @property
    def player_position(self):
        return list(self.grid.positions[self.player])

    @property
    def living_enemies(self):
        return [enemy for enemy in self.enemies if enemy.alive]

    def pieces_on_board(self):
        """Return JSON-friendly piece data for the Streamlit board."""
        pieces = [{
            "x": int(self.player_position[0]),
            "y": int(self.player_position[1]),
            "symbol": PIECE_SYMBOLS["Player"],
            "kind": "player",
        }]
        for enemy in self.living_enemies:
            x, y = self.grid.positions[enemy]
            pieces.append({
                "x": int(x),
                "y": int(y),
                "symbol": PIECE_SYMBOLS[enemy.piece_type],
                "kind": "boss" if enemy.is_boss else "enemy",
            })
        return pieces

    def _record_frame(self, label):
        """Save a board snapshot for playback after a level win."""
        self.history.append({"label": label, "pieces": self.pieces_on_board()})

    def get_winning_replay(self):
        """Return recorded moves only after the player has cleared the level."""
        if self.outcome != "level_complete":
            return []
        return self.history

    def _enemy_at(self, position):
        position = tuple(position)
        for enemy in self.living_enemies:
            if tuple(self.grid.positions[enemy]) == position:
                return enemy
        return None

    def _occupied(self, position, ignore=None):
        position = tuple(position)
        if position == tuple(self.grid.positions[self.player]) and ignore is not self.player:
            return self.player
        for enemy in self.living_enemies:
            if enemy is not ignore and tuple(self.grid.positions[enemy]) == position:
                return enemy
        return None

    @staticmethod
    def _inside(position):
        return all(0 <= value < BOARD_SIZE for value in position)

    def _path_is_clear(self, start, end, moving_agent):
        """Check intermediate cells for sliding piece movement."""
        x1, y1 = start
        x2, y2 = end
        dx, dy = x2 - x1, y2 - y1
        step_x = (dx > 0) - (dx < 0)
        step_y = (dy > 0) - (dy < 0)
        x, y = x1 + step_x, y1 + step_y
        while (x, y) != (x2, y2):
            if self._occupied((x, y), ignore=moving_agent):
                return False
            x += step_x
            y += step_y
        return True

    def _ray_move(self, start, end, directions, moving_agent=None):
        """Check a sliding move along one of the supplied direction vectors."""
        dx, dy = end[0] - start[0], end[1] - start[1]
        if dx == 0 and dy == 0:
            return False
        for direction_x, direction_y in directions:
            cross_product = dx * direction_y - dy * direction_x
            dot_product = dx * direction_x + dy * direction_y
            if cross_product == 0 and dot_product > 0:
                if self._path_is_clear(start, end, moving_agent or self.player):
                    return True
        return False

    def _cannon_allows_move(self, start, end, moving_agent=None):
        """Xiangqi Cannon: slide without a screen, or capture over one screen.

        A quiet move must have an empty destination and no intervening pieces.
        A capture must land on an opposing piece with exactly one intervening
        piece (the cannon's screen).
        """
        dx, dy = end[0] - start[0], end[1] - start[1]
        if (dx == 0 and dy == 0) or (dx != 0 and dy != 0):
            return False

        mover = moving_agent or self.player
        step_x = (dx > 0) - (dx < 0)
        step_y = (dy > 0) - (dy < 0)
        x, y = start[0] + step_x, start[1] + step_y
        screens = 0
        while (x, y) != end:
            if self._occupied((x, y), ignore=mover) is not None:
                screens += 1
            x += step_x
            y += step_y

        destination_occupant = self._occupied(end, ignore=mover)
        if destination_occupant is None:
            return screens == 0
        if mover is self.player:
            is_opponent = self._enemy_at(end) is not None
        else:
            is_opponent = end == tuple(self.grid.positions[self.player])
        return is_opponent and screens == 1

    @staticmethod
    def _leap_matches(dx, dy, offsets):
        return (dx, dy) in offsets

    def _lion_paths_to(self, destination):
        """Return legal one-jump or two-step Lion routes to a square."""
        start = tuple(self.grid.positions[self.player])
        destination = tuple(destination)
        paths = []
        distance = max(abs(destination[0] - start[0]), abs(destination[1] - start[1]))

        # The Lion's jump may cross occupied squares, but cannot land on itself.
        if 0 < distance <= 2:
            paths.append([destination])

        # A Lion may also make two adjacent steps. Returning to the start
        # square is allowed (jitto), after visiting a neighboring square.
        for step_x in (-1, 0, 1):
            for step_y in (-1, 0, 1):
                if (step_x, step_y) == (0, 0):
                    continue
                middle = (start[0] + step_x, start[1] + step_y)
                if not self._inside(middle):
                    continue
                middle_occupant = self._occupied(middle, ignore=self.player)
                if middle_occupant is not None and middle_occupant is not self._enemy_at(middle):
                    continue
                if max(abs(destination[0] - middle[0]), abs(destination[1] - middle[1])) != 1:
                    continue
                if destination != start:
                    end_occupant = self._occupied(destination, ignore=self.player)
                    if end_occupant is not None and end_occupant is not self._enemy_at(destination):
                        continue
                paths.append([middle, destination])

        return paths

    def _card_allows_move(self, start, end, card_name, moving_agent=None):
        dx_signed, dy_signed = end[0] - start[0], end[1] - start[1]
        dx, dy = abs(dx_signed), abs(dy_signed)
        if not self._inside(end):
            return False

        ortho = ((1, 0), (-1, 0), (0, 1), (0, -1))
        diag = ((1, 1), (1, -1), (-1, 1), (-1, -1))
        queen_rays = ortho + diag
        knight_offsets = {(2, 1), (1, 2)}

        if card_name == "Poseidon's Trident":
            # The Trident is evaluated from the moving agent's perspective:
            # the player cannot land on enemy pieces, and the Card King
            # cannot land on the player's king. Allied pieces remain blocked
            # by the normal destination-occupancy checks.
            mover = moving_agent or self.player
            origin = tuple(self.grid.positions[mover])
            if end == origin:
                return False
            if mover is self.player:
                return self._enemy_at(end) is None
            return end != tuple(self.grid.positions[self.player])
        if card_name == "Hades' Underworld":
            # Hades requires the UI/player to select a previously played
            # Compound card; its resolved movement is handled by the caller.
            return False
        if card_name == "Zeus's Smite":
            return self._enemy_at(end) is not None
        if card_name == "Lion":
            return bool(self._lion_paths_to(end))
        if card_name == "Checker":
            # On the enemy back rank, the Checker card becomes a Checker
            # Queen: it moves diagonally like a bishop, with captures handled
            # separately as jumps over an enemy piece.
            if start[1] == 0:
                return self._ray_move(start, end, diag, moving_agent)
            return abs(dx_signed) == 1 and dy_signed == -1
        if card_name == "Pawn":
            # When the king is on the enemy back rank (y == 0),
            # the Pawn card temporarily grants Queen movement.
            # Away from that rank, it keeps its normal Pawn movement.
            if start[1] == 0:
                return self._ray_move(start, end, queen_rays, moving_agent)

            # In the player's half of the board (rows 4 through 7),
            # the Pawn card may advance two squares straight forward.
            # Both the intermediate and destination squares must be empty.
            if moving_agent is None or moving_agent is self.player:
                if start[1] >= 4 and dx == 0 and dy_signed == -2:
                    intermediate = (start[0], start[1] - 1)
                    blocker = moving_agent or self.player
                    return (
                        self._occupied(intermediate, ignore=blocker) is None
                        and self._occupied(end, ignore=blocker) is None
                    )

            if dx == 0 and dy_signed == -1:
                return self._occupied(end, ignore=moving_agent or self.player) is None
            return dx == 1 and dy_signed == -1 and self._enemy_at(end) is not None
        if card_name == "King":
            return max(dx, dy) == 1
        if card_name == "Rook":
            return self._ray_move(start, end, ortho, moving_agent)
        if card_name == "Cannon":
            return self._cannon_allows_move(start, end, moving_agent)
        if card_name == "Bishop":
            return self._ray_move(start, end, diag, moving_agent)
        if card_name == "Stag":
            return self._ray_move(start, end, ((0, 1), (0, -1)), moving_agent) or max(dx, dy) == 1
        if card_name == "Ox":
            return self._ray_move(start, end, diag + ((0, 1), (0, -1)), moving_agent)
        if card_name == "Boar":
            return self._ray_move(start, end, diag + ((1, 0), (-1, 0)), moving_agent)
        if card_name == "Queen":
            return self._ray_move(start, end, queen_rays, moving_agent)
        if card_name == "Elephant":
            return (dx, dy) == (2, 2)
        if card_name == "Camel":
            return {dx, dy} == {1, 3}
        if card_name == "Knight":
            return (dx, dy) in knight_offsets
        if card_name == "Centaur":
            return (dx, dy) in knight_offsets or max(dx, dy) == 1
        if card_name == "Okapi":
            return (dx, dy) in {(1, 2), (2, 1), (2, 3), (3, 2)}
        if card_name == "Zebra":
            return (dx, dy) in {(2, 3), (3, 2)}
        if card_name == "Lancer":
            return (dx, dy) in {(1, 1), (1, -1), (-1, 1), (-1, -1),
                (1, 2), (-1, 2), (1, -2), (-1, -2)}
        if card_name == "Phoenix":
            return max(dx, dy) == 1 and (dx == 0 or dy == 0) or (dx, dy) == (2, 2)
        if card_name == "Kirin":
            return (dx, dy) == (1, 1) or (dx, dy) in {(0, 2), (2, 0)}
        if card_name == "Wizard":
            return (dx, dy) == (1, 1) or {dx, dy} == {1, 3}
        if card_name == "Dragon Horse":
            return self._ray_move(start, end, diag, moving_agent) or (
                max(dx, dy) == 1 and (dx == 0 or dy == 0)
            )
        if card_name == "Dragon King":
            return self._ray_move(start, end, ortho, moving_agent) or (dx, dy) == (1, 1)
        if card_name == "Princess":
            return self._ray_move(start, end, diag, moving_agent) or (dx, dy) in knight_offsets
        if card_name == "Empress":
            return self._ray_move(start, end, ortho, moving_agent) or (dx, dy) in knight_offsets
        if card_name == "Amazon":
            return self._ray_move(start, end, queen_rays, moving_agent) or (dx, dy) in knight_offsets
        return False

    def _en_passant_victim_for_move(self, start, end):
        """Pawn-card bypass capture: capture a horizontally adjacent enemy
        while landing one square diagonally forward behind that enemy.
        It is not restricted by enemy piece type or its previous move.
        """
        start, end = tuple(start), tuple(end)
        dx, dy = end[0] - start[0], end[1] - start[1]
        if abs(dx) != 1 or dy != -1 or self._occupied(end, ignore=self.player) is not None:
            return None
        adjacent = (start[0] + dx, start[1])
        victim = self._enemy_at(adjacent)
        return victim if victim is not None and victim.alive else None

    def _is_en_passant_move(self, start, end):
        return self._en_passant_victim_for_move(start, end) is not None

    def _best_lion_path(self, destination):
        paths = self._lion_paths_to(destination)
        if not paths:
            return None
        return max(
            paths,
            key=lambda path: sum(self._enemy_at(square) is not None for square in path),
        )

    def _checker_capture_paths(self):
        """Find complete Checker capture chains, including Checker Queen jumps.

        A regular Checker captures forward by jumping one diagonal square.
        When the player king starts on the enemy back rank (y == 0), the
        Checker card becomes a Checker Queen and may jump diagonally in any
        of the four directions. In either mode, each capture lands on the
        immediately adjacent empty square beyond the victim.
        """
        start = tuple(self.grid.positions[self.player])
        is_checker_queen = start[1] == 0
        enemies = {
            tuple(self.grid.positions[enemy]): enemy
            for enemy in self.living_enemies
        }
        directions = (
            ((-1, -1), (1, -1), (-1, 1), (1, 1))
            if is_checker_queen else ((-1, -1), (1, -1))
        )
        routes = []

        def search(position, remaining_enemies, landings, captured):
            found_jump = False
            for dx, dy in directions:
                middle = (position[0] + dx, position[1] + dy)
                landing = (position[0] + 2 * dx, position[1] + 2 * dy)
                if not self._inside(middle) or not self._inside(landing):
                    continue

                victim = remaining_enemies.get(middle)
                if victim is None or landing in remaining_enemies:
                    continue
                # Only enemies not yet captured remain as blockers. This
                # also lets a chain reuse a square vacated by an earlier
                # capture; the king's original square is vacant after jumping.

                found_jump = True
                next_enemies = dict(remaining_enemies)
                del next_enemies[middle]
                search(
                    landing,
                    next_enemies,
                    landings + [landing],
                    captured + [victim],
                )

            if not found_jump and captured:
                routes.append((landings, captured))

        search(start, enemies, [], [])
        return routes

    def _best_checker_path(self, destination):
        """Return the longest available capture chain ending on a square."""
        routes = [
            route
            for route in self._checker_capture_paths()
            if route[0] and route[0][-1] == tuple(destination)
        ]
        if not routes:
            return None
        return max(routes, key=lambda route: len(route[1]))

    @property
    def hades_card_choices(self):
        """Previously played Compound cards available for Hades to copy."""
        return list(dict.fromkeys(self.played_compound_cards))

    def legal_destinations(self, card_index=0, hades_choice=None):
        """Return board squares the king can enter with an unused card.

        ``hades_choice`` is the name of a previously played Compound card
        selected when the hand contains Hades' Underworld.
        """
        if not isinstance(card_index, int) or not 0 <= card_index < len(self.cards):
            return []
        card = self.cards[card_index]
        if card["used"]:
            return []
        start = tuple(self.grid.positions[self.player])
        effective_name = card["name"]
        if effective_name == "Hades' Underworld":
            if hades_choice not in self.hades_card_choices:
                return []
            effective_name = hades_choice
        if effective_name == "Checker":
            capture_routes = self._checker_capture_paths()
            if capture_routes:
                longest = max(len(captured) for _, captured in capture_routes)
                return [list(square) for square in sorted({
                    path[-1]
                    for path, captured in capture_routes
                    if path and len(captured) == longest
                })]

            if start[1] == 0:
                # Checker Queen's quiet moves are bishop-like diagonal slides.
                return [
                    [x, y]
                    for y in range(BOARD_SIZE)
                    for x in range(BOARD_SIZE)
                    if self._occupied((x, y), ignore=self.player) is None
                    and self._ray_move(start, (x, y),
                                       ((1, 1), (1, -1), (-1, 1), (-1, -1)),
                                       self.player)
                ]

            return [
                [start[0] + dx, start[1] - 1]
                for dx in (-1, 1)
                if self._inside((start[0] + dx, start[1] - 1))
                and self._occupied((start[0] + dx, start[1] - 1), ignore=self.player) is None
            ]

        destinations = []
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                end = (x, y)
                occupant = self._occupied(end, ignore=self.player)
                if occupant is not None and occupant is not self._enemy_at(end):
                    continue
                if (
                    self._card_allows_move(start, end, effective_name)
                    or (effective_name == "Pawn" and self._is_en_passant_move(start, end))
                ):
                    destinations.append([x, y])
        return destinations

    def play_card_move(self, destination, card_index=0, hades_choice=None):
        """Apply a valid player move, capture enemies, then move one enemy.

        For Hades' Underworld, pass ``hades_choice`` as the name of an
        eligible previously played Compound card.
        """
        if self.game_over:
            self.message = "The game is over. Reset to play again."
            return False
        if not isinstance(destination, (list, tuple)) or len(destination) != 2:
            self.message = "That destination is not a board square."
            return False
        if any(not isinstance(value, int) or not 0 <= value < BOARD_SIZE for value in destination):
            self.message = "That destination is outside the board."
            return False
        if not isinstance(card_index, int) or not 0 <= card_index < len(self.cards):
            self.message = "Select a card from your hand first."
            return False

        start = tuple(self.grid.positions[self.player])
        destination = tuple(destination)
        card = self.cards[card_index]
        if card["used"]:
            self.message = "That card has already been used this shuffle."
            return False
        card_name = card["name"]
        effective_name = card_name
        if card_name == "Hades' Underworld":
            if hades_choice not in self.hades_card_choices:
                self.message = "Choose a Compound card you have played before for Hades' Underworld."
                return False
            effective_name = hades_choice
        if destination not in [tuple(square) for square in self.legal_destinations(
            card_index, hades_choice=hades_choice
        )]:
            self.message = f"That move does not match the {effective_name} effect."
            return False

        lion_path = self._best_lion_path(destination) if effective_name == "Lion" else None
        checker_path = self._best_checker_path(destination) if effective_name == "Checker" else None
        en_passant_victim = (
            self._en_passant_victim_for_move(start, destination)
            if effective_name == "Pawn" else None
        )
        en_passant_capture = en_passant_victim is not None
        captured = []
        if checker_path:
            captured = checker_path[1]
        elif lion_path:
            for square in lion_path:
                enemy = self._enemy_at(square)
                if enemy is not None and enemy not in captured:
                    captured.append(enemy)
            if en_passant_capture and en_passant_victim not in captured:
                captured.append(en_passant_victim)
        else:
            direct_capture = self._enemy_at(destination)
            if direct_capture is not None:
                captured.append(direct_capture)
            elif en_passant_capture:
                captured.append(en_passant_victim)

        boss_captured = self.boss is not None and self.boss in captured
        for enemy in captured:
            self.grid.remove_agents([enemy])
            if enemy.is_boss:
                enemy.health -= 1
                enemy.alive = False
            else:
                enemy.alive = False

        # En passant is available only on the next player turn.
        self.en_passant_target = None
        self.en_passant_victim = None
        self.grid.move_to(self.player, destination)
        self.player.position = destination
        self.move_count += 1
        card["used"] = True
        if card.get("category") == "Compound" and card_name != "Hades' Underworld":
            if card_name not in self.played_compound_cards:
                self.played_compound_cards.append(card_name)
        self._record_frame(
            f"Player moved using {card_name}"
            + (f" (copied {effective_name})" if effective_name != card_name else "")
        )

        boss_respawned = False
        if boss_captured and self.boss.health > 0:
            self._respawn_boss()
            boss_respawned = True
            self.message = f"You struck the Card King! {self.boss.health} boss health remaining."
            self._record_frame("The Card King respawned")
        elif boss_captured:
            self.game_over = True
            self.outcome = "level_complete"
            self.message = "The Card King is defeated! You win the final level."
            return True

        if any(enemy.piece_type == "King" for enemy in captured):
            self.game_over = True
            self.outcome = "level_complete"
            self.message = f"You captured the enemy king! Level {self.level} cleared."
            return True

        if not self.living_enemies:
            self.game_over = True
            self.outcome = "level_complete"
            self.message = f"Level {self.level} cleared!"
            return True

        if self.remaining_card_count:
            self.cards_message = f"Moved with {card_name}" + (
                f" (copied {effective_name})." if effective_name != card_name else "."
            )
        else:
            self.cards = self._draw_hand()
            self.reshuffle_used = False
            self.shuffle_count += 1
            self.cards_message = f"Moved with {card_name}" + (
                f" (copied {effective_name})" if effective_name != card_name else ""
            ) + "; your five-card hand was refreshed."

        # A Card King respawn consumes its entire enemy turn. It cannot move
        # or spend a movement card until after the player has moved again.
        enemy_message = (
            "The Card King used its turn to respawn and cannot move this turn."
            if boss_respawned
            else self._take_enemy_turn()
        )
        if self.game_over:
            self.outcome = "enemy_win"
            self.message = enemy_message
        else:
            self.message = f"{self.cards_message} {enemy_message}"
        return True

    def _enemy_destinations(self, enemy):
        start = tuple(self.grid.positions[enemy])
        destinations = []
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                end = (x, y)
                if end == start:
                    continue
                occupant = self._occupied(end, ignore=enemy)
                if occupant is not None and occupant is not self.player:
                    continue
                if self._enemy_piece_allows(enemy, start, end):
                    destinations.append(end)
        return destinations

    def _respawn_boss(self):
        """Return the wounded boss at a random unoccupied board square."""
        free_squares = [
            (x, y)
            for y in range(BOARD_SIZE)
            for x in range(BOARD_SIZE)
            if self._occupied((x, y)) is None
        ]
        if not free_squares:
            free_squares = [tuple(self.grid.positions[self.player])]
        spawn = self.random.choice(free_squares)
        self.grid.add_agents([self.boss], positions=[spawn])
        self.boss.position = spawn
        self.boss.alive = True

    def _player_threat_count(self, target_position):
        """Count held cards that let the player capture a target square."""
        target_position = tuple(target_position)
        target_enemy = self._enemy_at(target_position)
        threat_count = 0
        for card_index, card in enumerate(self.cards):
            if card["used"]:
                continue
            if card["name"] == "Checker" and target_enemy is not None:
                routes = self._checker_capture_paths()
                if routes:
                    longest = max(len(captured) for _, captured in routes)
                    if any(
                        target_enemy in captured and len(captured) == longest
                        for _, captured in routes
                    ):
                        threat_count += 1
                continue
            if target_position in [
                tuple(square) for square in self.legal_destinations(card_index)
            ]:
                threat_count += 1
        return threat_count

    def _threat_counts_after_enemy_move(self, enemy, destination, enemy_king):
        """Count player capture cards after a hypothetical enemy move."""
        original_position = tuple(self.grid.positions[enemy])
        destination = tuple(destination)
        moved = destination != original_position
        if moved:
            self.grid.move_to(enemy, destination)
            enemy.position = destination
        try:
            enemy_threats = self._player_threat_count(tuple(self.grid.positions[enemy]))
            king_threats = 0
            if enemy_king is not None:
                king_threats = self._player_threat_count(
                    tuple(self.grid.positions[enemy_king])
                )
            return enemy_threats, king_threats
        finally:
            if moved:
                self.grid.move_to(enemy, original_position)
                enemy.position = original_position

    def _refresh_boss_hand_if_unusable(self, boss, max_attempts=100):
        """Redraw the Card King's hand when none of its unused cards can move.

        The played Compound-card history is preserved so Hades' Underworld
        can still copy cards used earlier in the level.
        """
        if not boss.is_boss or self._enemy_destinations(boss):
            return False

        for _ in range(max_attempts):
            boss.cards = self._draw_hand()
            if self._enemy_destinations(boss):
                return True

        # Avoid an infinite reroll if the board position itself has no moves.
        return False

    def _enemy_piece_allows(self, enemy, start, end):
        x1, y1 = start
        x2, y2 = end
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        piece = enemy.piece_type

        if enemy.is_boss:
            return any(
                not card["used"]
                and self._boss_card_allows_move(start, end, card["name"], enemy)
                for card in enemy.cards
            )

        if piece == "Pawn":
            forward = y2 - y1
            if dx == 0 and forward == 1 and self._occupied(end, ignore=enemy) is None:
                return True
            if dx == 0 and forward == 2 and y1 == 1:
                return (
                    self._occupied((x1, y1 + 1), ignore=enemy) is None
                    and self._occupied(end, ignore=enemy) is None
                )
            return dx == 1 and forward == 1 and end == tuple(self.grid.positions[self.player])
        if piece == "King":
            return max(dx, dy) == 1
        if piece == "Knight":
            return sorted((dx, dy)) == [1, 2]
        if piece == "Rook":
            return (dx == 0 or dy == 0) and self._path_is_clear(start, end, enemy)
        if piece == "Bishop":
            return dx == dy and self._path_is_clear(start, end, enemy)
        if piece == "Queen":
            straight_or_diagonal = dx == 0 or dy == 0 or dx == dy
            return straight_or_diagonal and self._path_is_clear(start, end, enemy)
        return False

    def _boss_card_allows_move(self, start, end, card_name, boss):
        """Apply a held movement card from the boss's perspective."""
        dx, dy = end[0] - start[0], end[1] - start[1]
        ax, ay = abs(dx), abs(dy)
        if card_name == "Pawn":
            return (dx == 0 and dy == 1 and self._occupied(end, ignore=boss) is None) or (
                ax == 1 and dy == 1 and end == tuple(self.grid.positions[self.player])
            )
        if card_name == "Checker":
            return ax == 1 and dy == 1
        if card_name == "Hades' Underworld":
            # Hades can copy only a Compound card the Card King has already
            # played during this level. Try each recorded card's movement.
            return any(
                self._boss_card_allows_move(start, end, previous_name, boss)
                for previous_name in boss.played_compound_cards
            )
        if card_name == "Zeus's Smite":
            return end == tuple(self.grid.positions[self.player])
        if card_name == "Cannon":
            return self._cannon_allows_move(start, end, moving_agent=boss)
        if card_name == "Poseidon's Trident":
            # This check can run after the boss has already been moved to
            # ``end``. Compare against the supplied original square instead
            # of reading the boss's now-updated grid position.
            return tuple(end) != tuple(start) and tuple(end) != tuple(
                self.grid.positions[self.player]
            )
        if card_name == "Lion":
            return 0 < max(ax, ay) <= 2
        # Other card patterns are direction-neutral. The moving agent is
        # passed through so sliding paths treat the boss as their origin.
        return self._card_allows_move(start, end, card_name, moving_agent=boss)

    def _spend_boss_card_for_move(self, boss, start, end):
        """Spend a matching card, tracking Compound use for Hades.

        Prefer a more specific card over Poseidon's Trident when both allow
        the same move. The Trident's broad movement should only be spent when
        no other unused card can account for the boss's move.
        """
        matching_cards = [
            card for card in boss.cards
            if not card["used"]
            and self._boss_card_allows_move(start, end, card["name"], boss)
        ]
        card = next(
            (candidate for candidate in matching_cards
             if candidate["name"] != "Poseidon's Trident"),
            matching_cards[0] if matching_cards else None,
        )
        if card is None:
            return None

        card["used"] = True
        card_name = card["name"]
        used_name = card_name
        if card_name == "Hades' Underworld":
            # If several previously played Compound cards permit this move,
            # copy the one with the greatest overall mobility from the boss's
            # current square. The AI has already selected the destination
            # using its normal tactical move scoring; this tie-break chooses
            # the strongest card to attribute/use for that move.
            start = tuple(start)
            eligible = []
            for history_index, previous_name in enumerate(boss.played_compound_cards):
                if not self._boss_card_allows_move(start, end, previous_name, boss):
                    continue
                mobility = 0
                for y in range(BOARD_SIZE):
                    for x in range(BOARD_SIZE):
                        candidate = (x, y)
                        if candidate == start:
                            continue
                        occupant = self._occupied(candidate, ignore=boss)
                        if occupant is not None and occupant is not self.player:
                            continue
                        if self._boss_card_allows_move(start, candidate, previous_name, boss):
                            mobility += 1
                eligible.append((mobility, -history_index, previous_name))
            copied_name = max(eligible)[2] if eligible else None
            used_name = f"Hades' Underworld (copied {copied_name})" if copied_name else card_name
        elif card.get("category") == "Compound":
            if card_name not in boss.played_compound_cards:
                boss.played_compound_cards.append(card_name)

        if all(held_card["used"] for held_card in boss.cards):
            # Keep the history across hands so Hades remains usable after
            # the Card King's deck refreshes.
            boss.cards = self._draw_hand()
        return used_name

    def _take_enemy_turn(self):
        """Move an available enemy piece, preferring moves toward the king."""
        if not self.living_enemies:
            return "No enemies remain."

        king_position = tuple(self.grid.positions[self.player])
        enemy_king = next(
            (enemy for enemy in self.living_enemies if enemy.piece_type in ("King", "Boss")),
            None,
        )
        current_king_threats = (
            self._player_threat_count(tuple(self.grid.positions[enemy_king]))
            if enemy_king is not None
            else 0
        )

        def distance(position):
            return max(abs(position[0] - king_position[0]), abs(position[1] - king_position[1]))

        options = []
        boss_reshuffled = False
        for offset in range(len(self.enemies)):
            index = (self.enemy_turn_index + offset) % len(self.enemies)
            enemy = self.enemies[index]
            if not enemy.alive:
                continue
            if enemy.is_boss:
                boss_reshuffled = (
                    self._refresh_boss_hand_if_unusable(enemy) or boss_reshuffled
                )
            start = tuple(self.grid.positions[enemy])
            starting_distance = distance(start)
            for destination in self._enemy_destinations(enemy):
                target_distance = distance(destination)
                captures_king = destination == king_position
                if captures_king:
                    threatened, king_threats_after = 0, current_king_threats
                else:
                    threatened, king_threats_after = self._threat_counts_after_enemy_move(
                        enemy, destination, enemy_king
                    )
                moves_closer = target_distance < starting_distance
                if current_king_threats and enemy_king is not None:
                    if king_threats_after == 0:
                        king_defense_priority = 3
                    elif king_threats_after < current_king_threats:
                        king_defense_priority = 2
                    elif enemy is enemy_king:
                        king_defense_priority = 1
                    else:
                        king_defense_priority = 0
                else:
                    king_defense_priority = 0
                # Prefer a king capture first. Otherwise prefer safety, then
                # protecting a threatened enemy king, then progress and
                # distance. Preserve round-robin fairness for ties.
                options.append((
                    captures_king,
                    king_defense_priority,
                    -king_threats_after,
                    not threatened,
                    moves_closer,
                    -target_distance,
                    -offset,
                    index,
                    enemy,
                    destination,
                    threatened,
                    king_threats_after,
                ))

        if not options:
            message = "Every enemy piece is blocked and has no legal move."
            if boss_reshuffled:
                message += " The Card King reshuffled its unusable hand."
            return message

        (
            _, _, _, _, moves_closer, _, _, index, enemy, destination,
            threatened, king_threats_after,
        ) = max(
            options, key=lambda option: option[:7]
        )
        self.enemy_turn_index = (index + 1) % len(self.enemies)

        if destination == king_position:
            # Record the exact movement card before ending the game. The boss
            # normally spends its card after moving, but a king capture exits
            # early, so account for that card here as well.
            movement_card = (
                self._spend_boss_card_for_move(enemy, tuple(self.grid.positions[enemy]), destination)
                if enemy.is_boss
                else None
            )
            self.game_over = True
            self.outcome = "enemy_win"
            self.loss_details = {
                "piece": enemy.piece_type,
                "movement_card": movement_card,
                "start": list(tuple(self.grid.positions[enemy])),
                "destination": list(destination),
            }
            if movement_card:
                message = (
                    f"The Card King captured your king using {movement_card}. "
                    "Game over."
                )
            else:
                message = (
                    f"The enemy {enemy.piece_type.lower()} captured your king. "
                    "Game over."
                )
            if boss_reshuffled:
                message += " The Card King reshuffled its unusable hand."
            return message

        start = tuple(self.grid.positions[enemy])
        original_y = int(self.grid.positions[enemy][1])
        self.grid.move_to(enemy, destination)
        enemy.position = destination
        boss_card_name = (
            self._spend_boss_card_for_move(enemy, start, destination)
            if enemy.is_boss
            else None
        )
        if enemy.piece_type == "Pawn" and destination[1] - original_y == 2:
            self.en_passant_target = (destination[0], original_y + 1)
            self.en_passant_victim = enemy
        self._record_frame(f"Enemy {enemy.piece_type.lower()} moved")
        if current_king_threats and enemy_king is not None:
            if king_threats_after == 0:
                message = f"The enemy {enemy.piece_type.lower()} protected its king from your cards."
                if boss_reshuffled:
                    message += " The Card King reshuffled its unusable hand."
                return message
            if king_threats_after < current_king_threats:
                message = f"The enemy {enemy.piece_type.lower()} blocked one of your threats to its king."
                if boss_reshuffled:
                    message += " The Card King reshuffled its unusable hand."
                return message
            if enemy is enemy_king:
                message = "The enemy king moved to escape your threat."
                if boss_reshuffled:
                    message += " The Card King reshuffled its unusable hand."
                return message
        if threatened:
            message = f"The enemy {enemy.piece_type.lower()} moved, but your hand can capture it."
        elif moves_closer:
            if boss_card_name:
                message = f"The Card King used {boss_card_name} and moved closer."
            else:
                message = f"The enemy {enemy.piece_type.lower()} moved closer while avoiding your cards."
        elif boss_card_name:
            message = f"The Card King used {boss_card_name} to move."
        else:
            message = f"The enemy {enemy.piece_type.lower()} moved to avoid your card threats."

        if boss_reshuffled:
            message += " The Card King reshuffled its unusable hand."
        return message
