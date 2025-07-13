import json
import random
import sys
from enum import IntEnum, auto
from dataclasses import dataclass
from typing import List, Tuple, Optional
from collections import deque

# === 基础常量 ===
FIELD_HEIGHT = 9
FIELD_WIDTH = 9
SIDE_COUNT = 2
TANKS_PER_SIDE = 2
MAX_TURN = 100

BASE_X = [FIELD_WIDTH // 2, FIELD_WIDTH // 2]
BASE_Y = [0, FIELD_HEIGHT - 1]

DX = [0, 1, 0, -1]
DY = [-1, 0, 1, 0]


# === 枚举定义 ===
class GameResult(IntEnum):
    NOT_FINISHED = -2
    DRAW = -1
    BLUE = 0
    RED = 1


class FieldItem(IntEnum):
    NONE = 0
    BRICK = 1
    STEEL = 2
    BASE = 4
    BLUE0 = 8
    BLUE1 = 16
    RED0 = 32
    RED1 = 64
    WATER = 128


class Action(IntEnum):
    INVALID = -2
    STAY = -1
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3
    UP_SHOOT = 4
    RIGHT_SHOOT = 5
    DOWN_SHOOT = 6
    LEFT_SHOOT = 7


TANK_ITEM_TYPES = [
    [FieldItem.BLUE0, FieldItem.BLUE1],
    [FieldItem.RED0, FieldItem.RED1]
]


# === 基础函数（原 C++ inline 函数） ===
def action_is_move(action: Action) -> bool:
    return Action.UP <= action <= Action.LEFT


def action_is_shoot(action: Action) -> bool:
    return Action.UP_SHOOT <= action <= Action.LEFT_SHOOT


def action_direction_is_opposite(a: Action, b: Action) -> bool:
    return a >= Action.UP and b >= Action.UP and (a + 2) % 4 == b % 4


def coord_valid(x: int, y: int) -> bool:
    return 0 <= x < FIELD_WIDTH and 0 <= y < FIELD_HEIGHT


def has_multiple_tank(item: int) -> bool:
    return item & (item - 1) != 0 and item != 0


def get_tank_side(item: FieldItem) -> int:
    return 0 if item in (FieldItem.BLUE0, FieldItem.BLUE1) else 1


def get_tank_id(item: FieldItem) -> int:
    return 0 if item in (FieldItem.BLUE0, FieldItem.RED0) else 1


def extract_direction_from_action(action: Action) -> int:
    if action >= Action.UP:
        return action % 4
    return -1


# === 数据类 ===
@dataclass(order=True, frozen=False)
class DisappearLog:
    x: int
    y: int
    item: FieldItem
    turn: int


# === 核心游戏逻辑类 ===
class TankField:
    def __init__(self, has_brick: List[int], has_water: List[int], has_steel: List[int], my_side: int):
        self.my_side = my_side
        self.current_turn = 1

        self.game_field = [[FieldItem.NONE for _ in range(FIELD_WIDTH)] for _ in range(FIELD_HEIGHT)]
        self.tank_alive = [[True, True], [True, True]]
        self.base_alive = [True, True]
        self.logs: List[DisappearLog] = []

        self.tank_x = [[FIELD_WIDTH // 2 - 2, FIELD_WIDTH // 2 + 2],
                       [FIELD_WIDTH // 2 + 2, FIELD_WIDTH // 2 - 2]]
        self.tank_y = [[0, 0],
                       [FIELD_HEIGHT - 1, FIELD_HEIGHT - 1]]

        self.next_action = [[Action.INVALID, Action.INVALID],
                            [Action.INVALID, Action.INVALID]]

        self.previous_actions = [[[Action.STAY for _ in range(TANKS_PER_SIDE)]
                                   for _ in range(SIDE_COUNT)] for _ in range(MAX_TURN + 1)]

        # 初始化地图
        for i in range(3):
            mask = 1
            for y in range(i * 3, (i + 1) * 3):
                for x in range(FIELD_WIDTH):
                    if has_brick[i] & mask:
                        self.game_field[y][x] = FieldItem.BRICK
                    elif has_water[i] & mask:
                        self.game_field[y][x] = FieldItem.WATER
                    elif has_steel[i] & mask:
                        self.game_field[y][x] = FieldItem.STEEL
                    mask <<= 1

        for side in range(SIDE_COUNT):
            for tank in range(TANKS_PER_SIDE):
                tx, ty = self.tank_x[side][tank], self.tank_y[side][tank]
                self.game_field[ty][tx] |= TANK_ITEM_TYPES[side][tank]
            self.game_field[BASE_Y[side]][BASE_X[side]] |= FieldItem.BASE

    def action_is_valid(self, side: int, tank: int, act: Action) -> bool:
        if act < Action.INVALID or act > Action.LEFT_SHOOT:
            return False
        if act == Action.INVALID:
            return False
        if act > Action.LEFT and self.previous_actions[self.current_turn - 1][side][tank] > Action.LEFT:
            return False  # 连续射击
        if act == Action.STAY or act > Action.LEFT:
            return True
        x = self.tank_x[side][tank] + DX[act]
        y = self.tank_y[side][tank] + DY[act]
        return coord_valid(x, y) and self.game_field[y][x] == FieldItem.NONE

    def all_actions_valid(self) -> bool:
        for side in range(SIDE_COUNT):
            for tank in range(TANKS_PER_SIDE):
                if self.tank_alive[side][tank] and not self.action_is_valid(side, tank, self.next_action[side][tank]):
                    return False
        return True

    def _destroy_tank(self, side: int, tank: int):
        self.tank_alive[side][tank] = False
        self.tank_x[side][tank] = self.tank_y[side][tank] = -1

    def _revert_tank(self, side: int, tank: int, log: DisappearLog):
        if self.tank_alive[side][tank]:
            y, x = self.tank_y[side][tank], self.tank_x[side][tank]
            self.game_field[y][x] = FieldItem(self.game_field[y][x] & ~TANK_ITEM_TYPES[side][tank])
        else:
            self.tank_alive[side][tank] = True

        self.tank_x[side][tank] = log.x
        self.tank_y[side][tank] = log.y
        self.game_field[log.y][log.x] |= TANK_ITEM_TYPES[side][tank]

    def do_action(self) -> bool:
        if not self.all_actions_valid():
            return False

        # 移动
        for side in range(SIDE_COUNT):
            for tank in range(TANKS_PER_SIDE):
                act = self.next_action[side][tank]
                self.previous_actions[self.current_turn][side][tank] = act

                if self.tank_alive[side][tank] and action_is_move(act):
                    x, y = self.tank_x[side][tank], self.tank_y[side][tank]
                    item = TANK_ITEM_TYPES[side][tank]

                    self.logs.append(DisappearLog(x, y, item, self.current_turn))

                    self.game_field[y][x] = FieldItem(self.game_field[y][x] & ~item)
                    x += DX[act]
                    y += DY[act]

                    self.tank_x[side][tank] = x
                    self.tank_y[side][tank] = y
                    self.game_field[y][x] |= item

        # 射击
        to_destroy = set()
        for side in range(SIDE_COUNT):
            for tank in range(TANKS_PER_SIDE):
                act = self.next_action[side][tank]
                if self.tank_alive[side][tank] and action_is_shoot(act):
                    dir = extract_direction_from_action(act)
                    x = self.tank_x[side][tank]
                    y = self.tank_y[side][tank]
                    has_multi = has_multiple_tank(self.game_field[y][x])

                    while True:
                        x += DX[dir]
                        y += DY[dir]
                        if not coord_valid(x, y):
                            break
                        item = self.game_field[y][x]
                        if item not in (FieldItem.NONE, FieldItem.WATER):
                            if item >= FieldItem.BLUE0 and not has_multi and not has_multiple_tank(item):
                                their_act = self.next_action[get_tank_side(item)][get_tank_id(item)]
                                if action_is_shoot(their_act) and action_direction_is_opposite(act, their_act):
                                    break

                            for mask in [1 << i for i in range(8)]:
                                if item & mask:
                                    to_destroy.add(DisappearLog(x, y, FieldItem(mask), self.current_turn))
                            break

        # 执行摧毁
        for log in sorted(to_destroy):
            item = log.item
            if item == FieldItem.BASE:
                side = GameResult.BLUE if log.x == BASE_X[0] else GameResult.RED
                self.base_alive[side] = False
            elif item in (FieldItem.BLUE0, FieldItem.BLUE1, FieldItem.RED0, FieldItem.RED1):
                self._destroy_tank(get_tank_side(item), get_tank_id(item))
            elif item == FieldItem.STEEL:
                continue
            self.game_field[log.y][log.x] = FieldItem(self.game_field[log.y][log.x] & ~item)
            self.logs.append(log)

        # 清除 next_action
        self.next_action = [[Action.INVALID, Action.INVALID], [Action.INVALID, Action.INVALID]]
        self.current_turn += 1
        return True

    def revert(self) -> bool:
        if self.current_turn == 1:
            return False
        self.current_turn -= 1
        while self.logs and self.logs[-1].turn == self.current_turn:
            log = self.logs.pop()
            item = log.item
            if item == FieldItem.BASE:
                side = 0 if log.x == BASE_X[0] else 1
                self.base_alive[side] = True
                self.game_field[log.y][log.x] = FieldItem.BASE
            elif item == FieldItem.BRICK:
                self.game_field[log.y][log.x] = FieldItem.BRICK
            elif item in (FieldItem.BLUE0, FieldItem.BLUE1, FieldItem.RED0, FieldItem.RED1):
                self._revert_tank(get_tank_side(item), get_tank_id(item), log)
        return True

    def get_game_result(self) -> GameResult:
        fail = [False, False]
        for side in range(SIDE_COUNT):
            if not (self.tank_alive[side][0] or self.tank_alive[side][1]) or not self.base_alive[side]:
                fail[side] = True
        if fail[0] == fail[1]:
            return GameResult.DRAW if fail[0] or self.current_turn > MAX_TURN else GameResult.NOT_FINISHED
        return GameResult.RED if fail[0] else GameResult.BLUE

    def debug_print(self):
        symbol = {
            FieldItem.NONE: '.',
            FieldItem.BRICK: '#',
            FieldItem.STEEL: '%',
            FieldItem.BASE: '*',
            FieldItem.BLUE0: 'b',
            FieldItem.BLUE1: 'B',
            FieldItem.RED0: 'r',
            FieldItem.RED1: 'R',
            FieldItem.WATER: 'W'
        }
        print("=" * 30)
        for row in self.game_field:
            print("".join(symbol.get(cell, '@') for cell in row))
        print("-" * 30)
        for side in range(SIDE_COUNT):
            tanks = ', '.join(
                f"坦克{tid} {'存活' if self.tank_alive[side][tid] else '已炸'}"
                for tid in range(TANKS_PER_SIDE)
            )
            print(f"{'蓝' if side == 0 else '红'}：基地{'存活' if self.base_alive[side] else '已炸'}，{tanks}")
        result = self.get_game_result()
        if result == GameResult.NOT_FINISHED:
            print(f"当前回合：{self.current_turn}，游戏尚未结束")
        elif result == GameResult.DRAW:
            print("游戏平局")
        else:
            print(f"{'蓝' if result == GameResult.BLUE else '红'}方胜利")
        print("=" * 30)


# === 地图生成类 ===
class TankJudge:
    def __init__(self):
        self.field_binary = [0, 0, 0]
        self.water_binary = [0, 0, 0]
        self.steel_binary = [0, 0, 0]

        self.tank_x = [
            [FIELD_WIDTH // 2 - 2, FIELD_WIDTH // 2 + 2],
            [FIELD_WIDTH // 2 + 2, FIELD_WIDTH // 2 - 2]
        ]
        self.tank_y = [
            [0, 0],
            [FIELD_HEIGHT - 1, FIELD_HEIGHT - 1]
        ]

    def ensure_connected(self, has_water, has_steel) -> bool:
        from collections import deque

        visited = [[False for _ in range(FIELD_WIDTH)] for _ in range(FIELD_HEIGHT)]
        total = sum(
            1 for y in range(FIELD_HEIGHT)
            for x in range(FIELD_WIDTH)
            if not has_water[y][x] and not has_steel[y][x]
        )

        q = deque()
        q.append((BASE_X[0], BASE_Y[0]))
        visited[BASE_Y[0]][BASE_X[0]] = True
        count = 1

        while q:
            x, y = q.popleft()
            for i in range(4):
                nx, ny = x + DX[i], y + DY[i]
                if coord_valid(nx, ny) and not visited[ny][nx] and not has_water[ny][nx] and not has_steel[ny][nx]:
                    visited[ny][nx] = True
                    q.append((nx, ny))
                    count += 1
        return count == total

    def initialize_field(self):
        field_height, field_width = FIELD_HEIGHT, FIELD_WIDTH
        portion_h = (field_height + 1) // 2

        while True:
            has_brick = [[False] * field_width for _ in range(field_height)]
            has_water = [[False] * field_width for _ in range(field_height)]
            has_steel = [[False] * field_width for _ in range(field_height)]

            for y in range(portion_h):
                for x in range(field_width):
                    if random.randint(0, 2) == 2:
                        has_brick[y][x] = True
                    elif random.randint(0, 26) > 22:
                        has_water[y][x] = True
                    elif random.randint(0, 22) > 18:
                        has_steel[y][x] = True

            bx, by = BASE_X[0], BASE_Y[0]
            for dx in [-1, 0, 1]:
                for dy in [0, 1]:
                    x, y = bx + dx, by + dy
                    if coord_valid(x, y):
                        has_brick[y][x] = (dx == 0 and dy == 1)
                        has_water[y][x] = False
                        has_steel[y][x] = False
            for dx in [-2, 0, 2]:
                if coord_valid(bx + dx, by):
                    has_brick[by][bx + dx] = False
                    has_water[by][bx + dx] = False
                    has_steel[by][bx + dx] = False

            # 对称填充
            for y in range(portion_h):
                for x in range(field_width):
                    y2 = field_height - 1 - y
                    x2 = field_width - 1 - x
                    has_brick[y2][x2] = has_brick[y][x]
                    has_water[y2][x2] = has_water[y][x]
                    has_steel[y2][x2] = has_steel[y][x]

            for y in range(2, field_height - 2):
                has_brick[y][field_width // 2] = True
                has_water[y][field_width // 2] = False
                has_steel[y][field_width // 2] = False

            for x in range(field_width):
                has_brick[field_height // 2][x] = True
                has_water[field_height // 2][x] = False
                has_steel[field_height // 2][x] = False

            for side in range(SIDE_COUNT):
                for tank in range(TANKS_PER_SIDE):
                    x, y = self.tank_x[side][tank], self.tank_y[side][tank]
                    has_brick[y][x] = False
                    has_water[y][x] = False
                    has_steel[y][x] = False
                x, y = BASE_X[side], BASE_Y[side]
                has_brick[y][x] = False
                has_water[y][x] = False
                has_steel[y][x] = False

            has_brick[field_height // 2][field_width // 2] = False
            has_water[field_height // 2][field_width // 2] = False
            has_steel[field_height // 2][field_width // 2] = True

            for tank in range(TANKS_PER_SIDE):
                x = self.tank_x[0][tank]
                has_brick[field_height // 2][x] = False
                has_water[field_height // 2][x] = False
                has_steel[field_height // 2][x] = True

            if self.ensure_connected(has_water, has_steel):
                break

        def compress(matrix):
            res = [0, 0, 0]
            for i in range(3):
                mask = 1
                for y in range(i * 3, (i + 1) * 3):
                    for x in range(field_width):
                        if matrix[y][x]:
                            res[i] |= mask
                        mask <<= 1
            return res

        self.field_binary = compress(has_brick)
        self.water_binary = compress(has_water)
        self.steel_binary = compress(has_steel)


# === 通信接口类 (Refactored) ===
class TankBotInterface:
    def __init__(self):
        # Game state properties
        self.game_id = None
        self.is_terminated = False
        self.winner = None # 'top', 'bottom', 'draw', or None

        # Player configuration
        self.top_player_type = 'human'
        self.bottom_player_type = 'bot'
        self.top_executor = None
        self.bottom_executor = None

        # Turn management
        self.pending_moves = {} # e.g., {'top': [Action, Action], 'bottom': [Action, Action]}

        # Initialize game field
        judge = TankJudge()
        judge.initialize_field()
        
        # Store the compressed map data
        self.brick_binary = judge.field_binary
        self.water_binary = judge.water_binary
        self.steel_binary = judge.steel_binary

        # Side 0 (Blue) is the 'top' player, Side 1 (Red) is the 'bottom' player
        self.field = TankField(self.brick_binary, self.water_binary, self.steel_binary, 0)

    def terminate(self):
        """Marks the game as terminated and cleans up resources."""
        self.is_terminated = True
        if self.top_executor: self.top_executor.cleanup()
        if self.bottom_executor: self.bottom_executor.cleanup()

    def configure_players(self, top_player_type, bottom_player_type, top_executor, bottom_executor):
        """Sets up the players for the game."""
        self.top_player_type = top_player_type
        self.bottom_player_type = bottom_player_type
        self.top_executor = top_executor
        self.bottom_executor = bottom_executor

    def start_new_turn(self):
        """Prepares the game for a new turn by clearing pending moves."""
        self.pending_moves = {}

    def collect_move(self, player_side: str, move_data: dict):
        """Collects an action from a player for the current turn."""
        # The bot returns {"response": [act0, act1]}
        # The human player will send actions in the same format
        actions = move_data.get("response", [-2, -2]) # [-2 is INVALID]
        self.pending_moves[player_side] = [Action(actions[0]), Action(actions[1])]

    def are_all_moves_collected(self) -> bool:
        """Checks if moves from both players have been received."""
        return 'top' in self.pending_moves and 'bottom' in self.pending_moves

    def process_turn(self):
        """Processes the collected moves for one turn."""
        if not self.are_all_moves_collected():
            return

        # Map 'top'/'bottom' to side 0/1 and set actions
        top_actions = self.pending_moves['top']
        bottom_actions = self.pending_moves['bottom']
        
        self.field.next_action[0][0] = top_actions[0]
        self.field.next_action[0][1] = top_actions[1]
        self.field.next_action[1][0] = bottom_actions[0]
        self.field.next_action[1][1] = bottom_actions[1]

        # Execute the turn
        self.field.do_action()

    def check_winner(self) -> Optional[str]:
        """Checks the game result and updates the winner property."""
        result = self.field.get_game_result()
        if result == GameResult.NOT_FINISHED:
            self.winner = None
        elif result == GameResult.DRAW:
            self.winner = 'draw'
        elif result == GameResult.BLUE: # Blue is 'top' player
            self.winner = 'top'
        elif result == GameResult.RED: # Red is 'bottom' player
            self.winner = 'bottom'
        return self.winner

    def get_state(self) -> dict:
        """Serializes the current game state for the frontend."""
        tanks = []
        for side_idx, side_name in enumerate(['top', 'bottom']):
            for tank_idx in range(TANKS_PER_SIDE):
                tanks.append({
                    'side': side_name,
                    'id': tank_idx,
                    'x': self.field.tank_x[side_idx][tank_idx],
                    'y': self.field.tank_y[side_idx][tank_idx],
                    'alive': self.field.tank_alive[side_idx][tank_idx]
                })
        
        return {
            # Add the compressed map data for initial drawing, same as for bots
            'brick_binary': self.brick_binary,
            'water_binary': self.water_binary,
            'steel_binary': self.steel_binary,

            # Keep the existing state info
            'field': self.field.game_field,
            'tanks': tanks,
            'bases': {
                'top': {'alive': self.field.base_alive[0]},
                'bottom': {'alive': self.field.base_alive[1]}
            },
            'turn': self.field.current_turn,
            'max_turn': MAX_TURN
        }

    def get_bot_input(self, player_side: str) -> str:
        """Generates the JSON input string for an AI bot."""
        side_idx = 0 if player_side == 'top' else 1
        
        # For the first turn, the bot needs the full map info.
        if self.field.current_turn == 1:
            return json.dumps({
                "requests": [{
                    "brickfield": self.brick_binary,
                    "waterfield": self.water_binary,
                    "steelfield": self.steel_binary,
                    "mySide": side_idx
                }],
                "responses": []
            })
        else:
            # For subsequent turns, provide the opponent's last action.
            opponent_side_idx = 1 - side_idx
            opponent_actions = self.field.previous_actions[self.field.current_turn - 1][opponent_side_idx]
            
            return json.dumps({
                "requests": [[int(act) for act in opponent_actions]],
                "responses": [] # Responses would be for a turn-based game, not needed here
            })

    # The following methods are from the old protocol and are no longer used directly by the server.
    # They are kept for reference or potential single-player testing.
    def read_input(self):
        pass
    def _process_request_or_response(self, value, is_opponent: bool):
        pass
    def submit_action(self, act0: Action, act1: Action, debug: str = "", data: str = "", global_data: str = "", exit_after=True):
        pass
    def send_to_client(self, first_round: bool, mySide: int,max_turn=100):
        pass