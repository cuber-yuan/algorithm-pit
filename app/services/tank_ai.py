import sys
import json
import random
import math
from enum import IntEnum, IntFlag
from collections import deque

# ------------------- 常量定义 -------------------

FIELD_HEIGHT = 9
FIELD_WIDTH = 9
SIDE_COUNT = 2
TANK_PER_SIDE = 2

# 基地的坐标
BASE_X = [FIELD_WIDTH // 2, FIELD_WIDTH // 2]
BASE_Y = [0, FIELD_HEIGHT - 1]

# 方向向量 (Up, Right, Down, Left)
DX = [0, 1, 0, -1]
DY = [-1, 0, 1, 0]

MAX_TURN = 100
INF = 100000
LARGE = 10000
BOMB = 1000

# ------------------- 枚举定义 -------------------

class GameResult(IntEnum):
    NOT_FINISHED = -2
    DRAW = -1
    BLUE = 0
    RED = 1

class FieldItem(IntFlag):
    NONE = 0
    BRICK = 1
    STEEL = 2
    BASE = 4
    BLUE0 = 8
    BLUE1 = 16
    RED0 = 32
    RED1 = 64
    WATER = 128
    
    @staticmethod
    def get_tank_side(item):
        if item in (FieldItem.BLUE0, FieldItem.BLUE1):
            return 0  # Blue
        return 1  # Red

    @staticmethod
    def get_tank_id(item):
        if item in (FieldItem.BLUE0, FieldItem.RED0):
            return 0
        return 1

TANK_ITEM_TYPES = [
    [FieldItem.BLUE0, FieldItem.BLUE1],
    [FieldItem.RED0, FieldItem.RED1]
]

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

    @staticmethod
    def is_move(act):
        return Action.UP <= act <= Action.LEFT

    @staticmethod
    def is_shoot(act):
        return Action.UP_SHOOT <= act <= Action.LEFT_SHOOT

    @staticmethod
    def direction_is_opposite(a, b):
        return a >= Action.UP and b >= Action.UP and (a + 2) % 4 == b % 4
    
    @staticmethod
    def extract_direction(act):
        if act >= Action.UP:
            return act % 4
        return -1

class SpecialCase(IntEnum):
    NORMAL = 0
    TBT = 1
    TBT2 = 2
    AVOID_O = 3
    OVERLAP = 4
    LOOP = 5
    TURTLE = 6
    KILL = 7
    DEFENSE = 8

# ------------------- 工具类和函数 -------------------

def coord_valid(x, y):
    return 0 <= x < FIELD_WIDTH and 0 <= y < FIELD_HEIGHT

def has_multiple_tank(item):
    # 如果item是2的幂或0，则item & (item - 1) == 0
    return (item & (item - 1)) != 0

class DisappearLog:
    def __init__(self, item, turn, x, y):
        self.item = item
        self.turn = turn
        self.x = x
        self.y = y

    def __lt__(self, other):
        if self.x != other.x:
            return self.x < other.x
        if self.y != other.y:
            return self.y < other.y
        return self.item < other.item
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y and self.item == other.item

    def __hash__(self):
        return hash((self.x, self.y, self.item))

# ------------------- 主逻辑类 -------------------

class TankField:
    def __init__(self, has_brick, has_water, has_steel, my_side):
        self.my_side = my_side
        self.game_field = [[FieldItem.NONE for _ in range(FIELD_WIDTH)] for _ in range(FIELD_HEIGHT)]

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
        
        self.tank_alive = [[True, True], [True, True]]
        self.base_alive = [True, True]
        self.tank_x = [
            [FIELD_WIDTH // 2 - 2, FIELD_WIDTH // 2 + 2],
            [FIELD_WIDTH // 2 + 2, FIELD_WIDTH // 2 - 2]
        ]
        self.tank_y = [
            [0, 0],
            [FIELD_HEIGHT - 1, FIELD_HEIGHT - 1]
        ]

        for side in range(SIDE_COUNT):
            for tank in range(TANK_PER_SIDE):
                self.game_field[self.tank_y[side][tank]][self.tank_x[side][tank]] = TANK_ITEM_TYPES[side][tank]
            self.game_field[BASE_Y[side]][BASE_X[side]] = FieldItem.BASE

        self.current_turn = 1
        self.logs = []  # 用作栈
        
        # 历史记录
        self.previous_actions = [[([Action.STAY] * TANK_PER_SIDE) for _ in range(SIDE_COUNT)] for _ in range(MAX_TURN + 1)]
        self.history_x = [[([-1] * TANK_PER_SIDE) for _ in range(SIDE_COUNT)] for _ in range(MAX_TURN + 1)]
        self.history_y = [[([-1] * TANK_PER_SIDE) for _ in range(SIDE_COUNT)] for _ in range(MAX_TURN + 1)]

        self.next_action = [[Action.INVALID, Action.INVALID], [Action.INVALID, Action.INVALID]]

        # AI 状态
        self.search_a0 = -2
        self.search_a1 = -2
        self.tank2steel = False
        self.attack_id = -1
        self.under_attack = [[[0] * FIELD_WIDTH for _ in range(FIELD_HEIGHT)] for _ in range(SIDE_COUNT)]

    def action_is_valid(self, side, tank, act, enable_back=True):
        if act == Action.INVALID:
            return False
        if act > Action.LEFT and self.previous_actions[self.current_turn - 1][side][tank] > Action.LEFT:
            return False
        if act == Action.STAY or act > Action.LEFT:
            return True
        if not self.tank_alive[side][tank] and act != Action.STAY:
            return False
        
        if not enable_back:
            if act == Action.UP and side == 0: return False
            if act == Action.DOWN and side == 1: return False
            
        x = self.tank_x[side][tank] + DX[act]
        y = self.tank_y[side][tank] + DY[act]
        return coord_valid(x, y) and self.game_field[y][x] == FieldItem.NONE

    def all_actions_valid(self):
        for side in range(SIDE_COUNT):
            for tank in range(TANK_PER_SIDE):
                if not self.action_is_valid(side, tank, self.next_action[side][tank]):
                    return False
        return True

    def _destroy_tank(self, side, tank):
        self.tank_alive[side][tank] = False
        self.tank_x[side][tank] = -1
        self.tank_y[side][tank] = -1

    def _revert_tank(self, side, tank, log):
        curr_x, curr_y = self.tank_x[side][tank], self.tank_y[side][tank]
        if self.tank_alive[side][tank]:
            self.game_field[curr_y][curr_x] &= ~TANK_ITEM_TYPES[side][tank]
        else:
            self.tank_alive[side][tank] = True
        self.tank_x[side][tank] = log.x
        self.tank_y[side][tank] = log.y
        self.game_field[log.y][log.x] |= TANK_ITEM_TYPES[side][tank]

    def do_action(self):
        if not self.all_actions_valid():
            return False

        # 1. 移动
        for side in range(SIDE_COUNT):
            for tank in range(TANK_PER_SIDE):
                act = self.next_action[side][tank]
                self.previous_actions[self.current_turn][side][tank] = act
                if self.tank_alive[side][tank] and Action.is_move(act):
                    x, y = self.tank_x[side][tank], self.tank_y[side][tank]
                    
                    log = DisappearLog(TANK_ITEM_TYPES[side][tank], self.current_turn, x, y)
                    self.logs.append(log)

                    self.tank_x[side][tank] += DX[act]
                    self.tank_y[side][tank] += DY[act]

                    self.game_field[self.tank_y[side][tank]][self.tank_x[side][tank]] |= log.item
                    self.game_field[y][x] &= ~log.item
        
        # 2. 射击
        items_to_be_destroyed = set()
        for side in range(SIDE_COUNT):
            for tank in range(TANK_PER_SIDE):
                act = self.next_action[side][tank]
                if self.tank_alive[side][tank] and Action.is_shoot(act):
                    direction = Action.extract_direction(act)
                    x, y = self.tank_x[side][tank], self.tank_y[side][tank]
                    has_multiple_tank_with_me = has_multiple_tank(self.game_field[y][x])
                    
                    shot_x, shot_y = x, y
                    while True:
                        shot_x += DX[direction]
                        shot_y += DY[direction]
                        if not coord_valid(shot_x, shot_y):
                            break
                        
                        items = self.game_field[shot_y][shot_x]
                        if items != FieldItem.NONE and items != FieldItem.WATER:
                            if items >= FieldItem.BLUE0 and not has_multiple_tank_with_me and not has_multiple_tank(items):
                                their_side = FieldItem.get_tank_side(items)
                                their_id = FieldItem.get_tank_id(items)
                                their_action = self.next_action[their_side][their_id]
                                if Action.is_shoot(their_action) and Action.direction_is_opposite(act, their_action):
                                    break
                            
                            mask = FieldItem.BRICK
                            while mask <= FieldItem.RED1:
                                if items & mask:
                                    log = DisappearLog(mask, self.current_turn, shot_x, shot_y)
                                    items_to_be_destroyed.add(log)
                                mask <<= 1
                            break

        for log in items_to_be_destroyed:
            if log.item == FieldItem.BASE:
                side = 0 if log.x == BASE_X[0] and log.y == BASE_Y[0] else 1
                self.base_alive[side] = False
            elif log.item == FieldItem.BLUE0: self._destroy_tank(0, 0)
            elif log.item == FieldItem.BLUE1: self._destroy_tank(0, 1)
            elif log.item == FieldItem.RED0:  self._destroy_tank(1, 0)
            elif log.item == FieldItem.RED1:  self._destroy_tank(1, 1)
            elif log.item == FieldItem.STEEL: continue
            
            self.game_field[log.y][log.x] &= ~log.item
            self.logs.append(log)

        for s in range(SIDE_COUNT):
            for t in range(TANK_PER_SIDE):
                self.history_x[self.current_turn][s][t] = self.tank_x[s][t]
                self.history_y[self.current_turn][s][t] = self.tank_y[s][t]

        self.current_turn += 1
        return True

    def revert(self):
        if self.current_turn == 1:
            return False
        
        self.current_turn -= 1
        while self.logs:
            log = self.logs[-1]
            if log.turn == self.current_turn:
                self.logs.pop()
                if log.item == FieldItem.BASE:
                    side = 0 if log.x == BASE_X[0] and log.y == BASE_Y[0] else 1
                    self.base_alive[side] = True
                    self.game_field[log.y][log.x] = FieldItem.BASE
                elif log.item == FieldItem.BRICK:
                    self.game_field[log.y][log.x] = FieldItem.BRICK
                elif log.item == FieldItem.BLUE0: self._revert_tank(0, 0, log)
                elif log.item == FieldItem.BLUE1: self._revert_tank(0, 1, log)
                elif log.item == FieldItem.RED0:  self._revert_tank(1, 0, log)
                elif log.item == FieldItem.RED1:  self._revert_tank(1, 1, log)
            else:
                break
        
        for side in range(SIDE_COUNT):
            for tank in range(TANK_PER_SIDE):
                self.next_action[side][tank] = self.previous_actions[self.current_turn][side][tank]
        return True

    def set_action(self, who, action0, action1):
        self.next_action[who][0] = Action(action0)
        self.next_action[who][1] = Action(action1)

    def get_game_result(self):
        fail = [False, False]
        for side in range(SIDE_COUNT):
            if (not self.tank_alive[side][0] and not self.tank_alive[side][1]) or not self.base_alive[side]:
                fail[side] = True
        
        if fail[0] == fail[1]:
            return GameResult.DRAW if fail[0] or self.current_turn > MAX_TURN else GameResult.NOT_FINISHED
        if fail[0]: return GameResult.RED
        return GameResult.BLUE

    def debug_print(self):
        # This function will not print in the online environment
        if "BOTZONE_ONLINE" in sys.argv:
            return
            
        legend = (
            "图例:\n"
            ". - 空\t# - 砖\t% - 钢\t* - 基地\t@ - 多个坦克\n"
            "b - 蓝0\tB - 蓝1\tr - 红0\tR - 红1\tW - 水\n"
        )
        print("=" * 30)
        print(legend)
        print("-" * 30)
        for y in range(FIELD_HEIGHT):
            row_str = ""
            for x in range(FIELD_WIDTH):
                item = self.game_field[y][x]
                if item == FieldItem.NONE:    row_str += '.'
                elif item == FieldItem.BRICK: row_str += '#'
                elif item == FieldItem.STEEL: row_str += '%'
                elif item == FieldItem.BASE:  row_str += '*'
                elif item == FieldItem.BLUE0: row_str += 'b'
                elif item == FieldItem.BLUE1: row_str += 'B'
                elif item == FieldItem.RED0:  row_str += 'r'
                elif item == FieldItem.RED1:  row_str += 'R'
                elif item == FieldItem.WATER: row_str += 'W'
                else:                         row_str += '@'
            print(row_str)
        print("-" * 30)
        
        side_map = ["蓝", "红"]
        alive_map = ["已炸", "存活"]
        for side in range(SIDE_COUNT):
            status = f"{side_map[side]}：基地{alive_map[self.base_alive[side]]}"
            for tank in range(TANK_PER_SIDE):
                status += f", 坦克{tank}{alive_map[self.tank_alive[side][tank]]}"
            print(status)
        
        result = self.get_game_result()
        result_str = ""
        if result == GameResult.NOT_FINISHED: result_str = "游戏尚未结束"
        elif result == GameResult.DRAW:       result_str = "游戏平局"
        else:                                 result_str = f"{side_map[result]}方胜利"
        
        print(f"当前回合：{self.current_turn}，{result_str}")
        print("=" * 30)

    # ------------------- AI/策略函数 -------------------

    def tank_count(self, side):
        return self.tank_alive[side][0] + self.tank_alive[side][1]

    def is_steel(self, side, tank, x, y, mode):
        item = self.game_field[y][x]
        if item == FieldItem.STEEL: return True
        if mode:
            if side == 0 and item in (FieldItem.RED0, FieldItem.RED1): return True
            if side == 1 and item in (FieldItem.BLUE0, FieldItem.BLUE1): return True
        
        if side == 0:
            if tank == 0 and item == FieldItem.BLUE1: return True
            if tank == 1 and item == FieldItem.BLUE0: return True
        else:
            if tank == 0 and item == FieldItem.RED1: return True
            if tank == 1 and item == FieldItem.RED0: return True
        return False

    def step_to_win(self, side, tank, flag=False):
        if not self.base_alive[1 - side]: return 0
        if not self.tank_alive[side][tank]: return BOMB

        val = [[BOMB] * FIELD_WIDTH for _ in range(FIELD_HEIGHT)]
        op_base_y, op_base_x = BASE_Y[1 - side], BASE_X[1 - side]
        val[op_base_y][op_base_x] = 0
        
        q = deque()

        for k in range(4):
            cury, curx = op_base_y, op_base_x
            while True:
                prey, prex = cury, curx
                cury += DY[k]
                curx += DX[k]
                if not coord_valid(curx, cury): break
                q.append((curx, cury))

                if self.is_steel(side, tank, curx, cury, flag):
                    val[cury][curx] = LARGE
                    break
                else:
                    if self.game_field[prey][prex] == FieldItem.BRICK:
                        val[cury][curx] = val[prey][prex] + 2
                    elif self.game_field[prey][prex] == FieldItem.BASE:
                        val[cury][curx] = val[prey][prex] + 1
                    else:
                        val[cury][curx] = val[prey][prex]
        
        for i in range(FIELD_HEIGHT):
            for j in range(FIELD_WIDTH):
                if self.game_field[i][j] == FieldItem.WATER:
                    val[i][j] = LARGE

        while q:
            curx, cury = q.popleft()
            for k in range(4):
                nx, ny = curx + DX[k], cury + DY[k]
                if not coord_valid(nx, ny): continue
                if self.is_steel(side, tank, nx, ny, flag): continue
                if self.game_field[ny][nx] == FieldItem.WATER: continue
                if self.game_field[ny][nx] == FieldItem.BASE: continue
                
                new_val = val[cury][curx] + (2 if self.game_field[cury][curx] == FieldItem.BRICK else 1)
                if new_val < val[ny][nx]:
                    val[ny][nx] = new_val
                    q.append((nx, ny))
        
        fix = 0
        if self.tank_y[side][tank] == op_base_y or \
           (self.tank_x[side][tank] == op_base_x and abs(self.tank_y[side][tank] - op_base_y) < 4):
            if self.previous_actions[self.current_turn - 1][side][tank] > Action.LEFT:
                fix = 1
        
        res = val[self.tank_y[side][tank]][self.tank_x[side][tank]] + fix
        return res

    def evaluate(self, side):
        gr = self.get_game_result()
        if gr == side: return INF
        if gr == 1 - side: return -INF
        if gr == GameResult.DRAW: return 0

        flag = self.tank2steel
        my_v = [
            -self.step_to_win(self.my_side, 0, flag and (self.attack_id == 0)),
            -self.step_to_win(self.my_side, 1, flag and (self.attack_id == 1))
        ]
        op_v = [
            -self.step_to_win(1 - self.my_side, 0),
            -self.step_to_win(1 - self.my_side, 1)
        ]
        
        my_v.sort(reverse=True)
        op_v.sort(reverse=True)

        res = my_v[0] * 2 + my_v[1] - op_v[0] * 2 - op_v[1]
        if self.tank_x[side][0] == self.tank_x[side][1] and self.tank_y[side][0] == self.tank_y[side][1]:
            res -= BOMB
        return res

    def shortest_moves(self, tank, act, flag=False):
        if not self.action_is_valid(self.my_side, tank, Action(act), True):
            # This should not happen if called correctly
            print("===== WARNING: invalid move in shortest_moves! =====", file=sys.stderr)
            return INF

        if tank == 0:
            self.set_action(self.my_side, act, -1)
        else:
            self.set_action(self.my_side, -1, act)
        self.set_action(1 - self.my_side, -1, -1)
        self.do_action()
        
        re = self.step_to_win(self.my_side, tank, flag)
        self.revert()
        return re

    def calc_attack_range(self):
        self.under_attack = [[[0] * FIELD_WIDTH for _ in range(FIELD_HEIGHT)] for _ in range(SIDE_COUNT)]
        for s in range(SIDE_COUNT):
            for t in range(TANK_PER_SIDE):
                if self.tank_alive[s][t] and self.previous_actions[self.current_turn - 1][s][t] <= Action.LEFT:
                    for k in range(4):
                        curx, cury = self.tank_x[s][t], self.tank_y[s][t]
                        while True:
                            curx += DX[k]
                            cury += DY[k]
                            if not coord_valid(curx, cury): break
                            
                            self.under_attack[1 - s][cury][curx] |= (1 << ((k + 2) % 4))
                            
                            if self.game_field[cury][curx] & (FieldItem.STEEL | FieldItem.BRICK | FieldItem.BASE):
                                break
                            
                            if self.game_field[cury][curx] & (FieldItem.BLUE0 | FieldItem.BLUE1 | FieldItem.RED0 | FieldItem.RED1):
                                # Complex logic to check if tank can be bypassed, simplified here
                                break


    def pre_processing(self):
        self.tank2steel = False
        self.attack_id = -1
        for t in range(2):
            rival = self.find_rival(t)
            step_rival = self.step_to_win(1 - self.my_side, rival)
            step_me = self.step_to_win(self.my_side, t, True)
            if step_me < step_rival + 2 and abs(self.tank_y[self.my_side][t] - BASE_Y[1 - self.my_side]) < 4:
                self.tank2steel = True
                self.attack_id = t
        self.calc_attack_range()

    def find_rival(self, tank):
        if not self.tank_alive[1 - self.my_side][0]: return 1
        if not self.tank_alive[1 - self.my_side][1]: return 0

        # Heuristics based on starting position and distance
        if abs(self.tank_x[self.my_side][tank] - self.tank_x[1 - self.my_side][1 - tank]) <= 1:
            return 1 - tank
        
        a = abs(self.tank_x[self.my_side][tank] - self.tank_x[1 - self.my_side][1 - tank]) + \
            abs(self.tank_y[self.my_side][tank] - self.tank_y[1 - self.my_side][1 - tank])
        b = abs(self.tank_x[self.my_side][tank] - self.tank_x[1 - self.my_side][tank]) + \
            abs(self.tank_y[self.my_side][tank] - self.tank_y[1 - self.my_side][tank])
        
        return 1 - tank if a <= b else tank

    def is_tbt(self, tank): # Tank-Brick-Tank
        my_forward = 1 if self.my_side == 0 else -1
        op_tank_mask = (FieldItem.RED0 | FieldItem.RED1) if self.my_side == 0 else (FieldItem.BLUE0 | FieldItem.BLUE1)
        curx, cury = self.tank_x[self.my_side][tank], self.tank_y[self.my_side][tank]
        
        cnt_brick = 0
        flag = False
        while True:
            cury += my_forward
            if not coord_valid(curx, cury): break

            if self.game_field[cury][curx] == FieldItem.BRICK:
                cnt_brick += 1
                if cnt_brick > 1: break
            elif self.game_field[cury][curx] == FieldItem.WATER:
                continue
            elif self.game_field[cury][curx] == FieldItem.STEEL:
                return False
            elif self.game_field[cury][curx] & op_tank_mask:
                if cnt_brick == 1:
                    flag = True
                break
        return flag

    def is_loop(self, tank):
        if self.current_turn <= 10: return False
        
        rival = self.find_rival(tank)
        
        def is_tank_move(side):
            if self.history_x[self.current_turn - 3][side][0] != self.history_x[self.current_turn - 1][side][0]: return True
            if self.history_y[self.current_turn - 3][side][0] != self.history_y[self.current_turn - 1][side][0]: return True
            if self.history_x[self.current_turn - 3][side][1] != self.history_x[self.current_turn - 1][side][1]: return True
            if self.history_y[self.current_turn - 3][side][1] != self.history_y[self.current_turn - 1][side][1]: return True
            return False

        if self.previous_actions[self.current_turn - 3][1 - self.my_side][rival] == self.previous_actions[self.current_turn - 1][1 - self.my_side][rival] and \
           not is_tank_move(self.my_side) and not is_tank_move(1 - self.my_side):
            if self.tank_alive[self.my_side][tank] and abs(self.tank_y[self.my_side][tank] - BASE_Y[1 - self.my_side]) <= 5:
                return True
        
        return False
    
    def is_kill(self, tank):
        # A simplified check, the original is too slow for Python
        # This checks if there is a shooting action that leads to a win
        for act in range(Action.UP_SHOOT, Action.LEFT_SHOOT + 1):
             if self.action_is_valid(self.my_side, tank, Action(act)):
                self.set_action(self.my_side, act if tank == 0 else -1, act if tank == 1 else -1)
                self.set_action(1 - self.my_side, -1, -1)
                self.do_action()
                if not self.base_alive[1 - self.my_side]:
                    self.revert()
                    return True
                self.revert()
        return False

    def fuck_kill(self, tank):
        # Corresponds to is_kill
        for act in range(Action.UP_SHOOT, Action.LEFT_SHOOT + 1):
             if self.action_is_valid(self.my_side, tank, Action(act)):
                self.set_action(self.my_side, act if tank == 0 else -1, act if tank == 1 else -1)
                self.set_action(1 - self.my_side, -1, -1)
                self.do_action()
                if not self.base_alive[1 - self.my_side]:
                    self.revert()
                    return act
                self.revert()
        return Action.STAY


    def look_ahead(self, dep, enable_mask, alpha, beta):
        who = (self.my_side + dep) % 2

        if dep % 2 == 0:
            gr = self.get_game_result()
            if gr == who: return INF
            if gr == 1 - who: return -INF
            if gr == GameResult.DRAW: return 0

        if dep == 2: # Reduced depth for performance
            return self.evaluate(self.my_side)

        re = -INF - 1
        
        act_order = list(range(-1, 8))
        if dep == 0:
            random.shuffle(act_order)

        for act0 in act_order:
            if not self.action_is_valid(who, 0, Action(act0), True): continue
            if dep == 1 and not ((1 << (act0 + 1)) & enable_mask[0]): continue
            
            for act1 in act_order:
                if not self.action_is_valid(who, 1, Action(act1), True): continue
                if dep == 1 and not ((1 << (act1 + 1)) & enable_mask[1]): continue
                
                self.set_action(who, act0, act1)
                
                child = 0
                if dep % 2 == 1:
                    if not self.all_actions_valid(): continue
                    self.do_action()
                    child = -self.look_ahead(dep + 1, enable_mask, -beta, -alpha)
                    if self.tank_x[self.my_side][0] == self.tank_x[self.my_side][1] and self.tank_y[self.my_side][0] == self.tank_y[self.my_side][1]:
                        child -= BOMB # Penalize overlap
                    self.revert()
                else: # dep % 2 == 0
                    child = -self.look_ahead(dep + 1, enable_mask, -beta, -alpha)
                
                if child > re:
                    re = child
                    if dep == 0:
                        self.search_a0 = act0
                        self.search_a1 = act1
                
                if re > alpha: alpha = re
                if re >= beta: return re # Pruning
        return re

    def fuck_loop(self, tank):
        mask0 = 1 << (self.previous_actions[self.current_turn - 2][1 - self.my_side][0] + 1)
        mask1 = 1 << (self.previous_actions[self.current_turn - 2][1 - self.my_side][1] + 1)
        
        self.look_ahead(0, (mask0, mask1), -INF, INF)
        return self.search_a0 if tank == 0 else self.search_a1

    def fuck_tbt(self, tank):
        go_front = Action.DOWN if self.my_side == 0 else Action.UP
        if self.action_is_valid(self.my_side, tank, go_front):
            return go_front
        return Action.STAY

    def is_defense(self, tank):
        if self.current_turn <= 5: return False
        if abs(self.tank_y[self.my_side][tank] - BASE_Y[self.my_side]) >= 4: return False

        rival = self.find_rival(tank)
        if self.step_to_win(self.my_side, tank) > self.step_to_win(1 - self.my_side, rival) + 1:
            return True
        return False

    def fuck_defense(self, tank):
        # Simplified defense logic
        rival = self.find_rival(tank)
        op_x, op_y = self.tank_x[1-self.my_side][rival], self.tank_y[1-self.my_side][rival]
        my_x, my_y = self.tank_x[self.my_side][tank], self.tank_y[self.my_side][tank]

        # Try to block the opponent's path to our base
        # Move to be between opponent and our base
        if abs(my_x - BASE_X[self.my_side]) > abs(op_x - BASE_X[self.my_side]):
            move_act = Action.RIGHT if my_x < BASE_X[self.my_side] else Action.LEFT
            if self.action_is_valid(self.my_side, tank, move_act):
                return move_act
        
        # Shoot if there's a brick in the way
        shoot_act = Action.DOWN_SHOOT if self.my_side == 0 else Action.UP_SHOOT
        if self.action_is_valid(self.my_side, tank, shoot_act):
            return shoot_act

        return Action.STAY


    def detect_case(self, tank):
        if not self.tank_alive[self.my_side][tank]: return SpecialCase.NORMAL
        if self.is_kill(tank): return SpecialCase.KILL
        if self.is_defense(tank): return SpecialCase.DEFENSE
        if self.is_loop(tank): return SpecialCase.LOOP
        if self.is_tbt(tank): return SpecialCase.TBT
        return SpecialCase.NORMAL
    
    def is_action_ok(self, t, a):
        x, y = self.tank_x[self.my_side][t], self.tank_y[self.my_side][t]
        if Action.is_move(Action(a)):
            x += DX[a]
            y += DY[a]
        
        if self.under_attack[self.my_side][y][x]:
            if Action.is_shoot(Action(a)):
                shoot_dir = a - 4
                # If shooting back, it's ok (simplified)
                if (self.under_attack[self.my_side][y][x] & (1 << shoot_dir)) != 0:
                    return True
            return False # Avoid moving into attack range
        return True

    def select_better(self, tank, moves):
        if not moves: return Action.STAY
        random.shuffle(moves)

        # In early turns, avoid shooting own bricks near base
        if self.current_turn <= 2:
            for move in moves:
                if Action.is_shoot(Action(move)):
                    if self.tank_x[self.my_side][tank] < 4 and Action(move) == Action.RIGHT_SHOOT: continue
                    if self.tank_x[self.my_side][tank] > 4 and Action(move) == Action.LEFT_SHOOT: continue
                return move
        
        return random.choice(moves)

    def normal_rush(self, t):
        if not self.tank_alive[self.my_side][t]: return -1
        
        acts = []
        flag = self.tank2steel and (self.attack_id == t)
        
        for a in range(-1, 8):
            if not self.action_is_valid(self.my_side, t, Action(a), True): continue
            move_cnt = self.shortest_moves(t, a, flag)
            acts.append((move_cnt, a))
        
        acts.sort()

        best_value = INF
        vec = []
        for move_cnt, a in acts:
            if self.is_action_ok(t, a):
                if move_cnt <= best_value:
                    best_value = move_cnt
                    vec.append(a)
                else:
                    break
        
        if not vec: # Fallback if all safe moves are worse
            for move_cnt, a in acts:
                if move_cnt <= best_value:
                    best_value = move_cnt
                    vec.append(a)
                else:
                    break

        return self.select_better(t, vec)

    def rush(self):
        act = [-1, -1]
        for t in range(TANK_PER_SIDE):
            the_case = self.detect_case(t)
            if the_case == SpecialCase.KILL:    act[t] = self.fuck_kill(t)
            elif the_case == SpecialCase.DEFENSE: act[t] = self.fuck_defense(t)
            elif the_case == SpecialCase.LOOP:    act[t] = self.fuck_loop(t)
            elif the_case == SpecialCase.TBT:     act[t] = self.fuck_tbt(t)
            else:                               act[t] = self.normal_rush(t)
        
        # Fallback for invalid actions
        for t in range(TANK_PER_SIDE):
            if not self.action_is_valid(self.my_side, t, Action(act[t])):
                act[t] = -1
        
        return tuple(act)

    def legend_algorithm(self):
        # A simplified version of the original complex decision logic
        return self.rush()


# ------------------- 平台交互 -------------------
field = None

def process_request_or_response(value, is_opponent):
    global field
    if isinstance(value, list):
        if not is_opponent:
            field.set_action(field.my_side, value[0], value[1])
        else:
            field.set_action(1 - field.my_side, value[0], value[1])
            field.do_action()
    else:
        # First turn, initializing the field
        has_brick = value["brickfield"]
        has_water = value["waterfield"]
        has_steel = value["steelfield"]
        my_side = value["mySide"]
        field = TankField(has_brick, has_water, has_steel, my_side)

def read_input(in_stream):
    # Botzone sends a single line of JSON
    line = ""
    while not line:
        line = in_stream.readline()
    
    input_json = json.loads(line)

    if "requests" in input_json and "responses" in input_json:
        requests = input_json["requests"]
        responses = input_json["responses"]
        for i, req in enumerate(requests):
            process_request_or_response(req, True)
            if i < len(responses):
                process_request_or_response(responses[i], False)
    else:
        process_request_or_response(input_json, True)

def submit_and_exit(tank0, tank1, debug=""):
    output = {
        "response": [tank0, tank1],
        "debug": debug
    }
    print(json.dumps(output))
    # sys.exit(0)


if __name__ == "__main__":
    random.seed()
    
    # Add a flag to indicate online environment to suppress prints
    # if len(sys.argv) > 1 and sys.argv[1] == 'online':
    #     sys.argv.append("BOTZONE_ONLINE")

    # while True:
    read_input(sys.stdin)
    # field.debug_print()
    field.pre_processing()

    a0, a1 = field.legend_algorithm()
    
    submit_and_exit(a0, a1, "")
        