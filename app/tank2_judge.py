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


@dataclass(order=True, frozen=False)
class DisappearLog:
    x: int
    y: int
    item: FieldItem
    turn: int


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
                side = BLUE if log.x == BASE_X[0] else RED
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

# === 通信接口类 ===
class TankBotInterface:
    def __init__(self):
        self.field: Optional[TankField] = None
        self.reader = json
        self.my_side = 0
        self.data = ''
        self.global_data = ''

        # by cuber
        self.judge = TankJudge()
        self.judge.initialize_field()

    def read_input(self):
        raw = ""
        while True:
            try:
                line = input()
                if not line.strip():
                    continue
                raw += line.strip()
                if line.strip().endswith('}') or line.strip().endswith(']'):
                    break
            except EOFError:
                break

        input_json = json.loads(raw)

        if isinstance(input_json, dict):
            if 'requests' in input_json and 'responses' in input_json:
                requests = input_json['requests']
                responses = input_json['responses']
                for i in range(len(requests)):
                    self._process_request_or_response(requests[i], is_opponent=True)
                    if i < len(responses):
                        self._process_request_or_response(responses[i], is_opponent=False)
                self.data = input_json.get('data', '')
                self.global_data = input_json.get('globaldata', '')
            else:
                self._process_request_or_response(input_json, is_opponent=True)

    def _process_request_or_response(self, value, is_opponent: bool):
        if isinstance(value, list):
            # 动作数组
            side = 1 - self.my_side if is_opponent else self.my_side
            for tank in range(TANKS_PER_SIDE):
                self.field.next_action[side][tank] = Action(value[tank])
            if is_opponent:
                self.field.do_action()
        elif isinstance(value, dict):
            # 初始化字段
            brick = value["brickfield"]
            water = value["waterfield"]
            steel = value["steelfield"]
            self.my_side = value["mySide"]
            self.field = TankField(brick, water, steel, self.my_side)

    def submit_action(self, act0: Action, act1: Action, debug: str = "", data: str = "", global_data: str = "", exit_after=True):
        result = {
            "response": [act0, act1]
        }
        if debug:
            result["debug"] = debug
        if data:
            result["data"] = data
        if global_data:
            result["globaldata"] = global_data
        print(json.dumps(result))
        if exit_after:
            sys.exit(0)
        else:
            self.field.next_action[self.my_side][0] = act0
            self.field.next_action[self.my_side][1] = act1
            print(">>>BOTZONE_REQUEST_KEEP_RUNNING<<<")


    def send_to_client(self, first_round: bool, mySide: int,max_turn=100):
        if first_round:
            # 发送地图初始化数据
            output = {
                "request": [{
                
                    "brickfield": self.judge.field_binary,
                    "waterfield": self.judge.water_binary,
                    "steelfield": self.judge.steel_binary,
                    "mySide": mySide,
                    
                
                }],
                
            }
            print(json.dumps(output))
        else:
            # 发送中间回合动作请求，可以按需求扩展
            output = {
                "command": "request",
                "data": self.data,
                "globaldata": self.global_data
                # 这里可加更多运行时信息
            }
            print(json.dumps(output))