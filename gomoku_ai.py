# game.py
import time

class GomokuGame:
    def __init__(self):
        self.board = [[0] * 15 for _ in range(15)]
        self.current_player = 1  # 1 = player, 2 = AI
        self.winner = 0

    def is_valid(self, x, y):
        return 0 <= x < 15 and 0 <= y < 15 and self.board[x][y] == 0

    def place_piece(self, x, y, player):
        if self.is_valid(x, y) and self.winner == 0 and self.current_player == player:
            self.board[x][y] = player
            if self.check_win(x, y, player):
                self.winner = player
            self.current_player = 3 - player
            return True
        return False

    def ai_move(self):
        # 1. 首手必下中心
        if all(self.board[y][x] == 0 for y in range(15) for x in range(15)):
            center = (7, 7)
            self.place_piece(center[0], center[1], 2)
            return center

        # 2. 模式-分数映射（可以根据需要微调）
        # 自己的模式（2 表示 AI）
        my_patterns = {
            '0222220': 100000,   # 活五
            '022220':   10000,   # 活四
            '202222':   8000,    # 冲四
            '02220':    1000,    # 活三
            '20222':    800,     # 冲三
            '0220':     200,     # 活二
            '2022':     100,     # 冲二
        }
        # 对手的模式（1 表示玩家）
        opp_patterns = {
            '011110': 90000,     # 对手活五（必须堵）
            '01110':  9000,      # 对手活四
            '10111':  8000,      # 对手冲四
            '0110':   900,       # 对手活三
            '1011':   800,       # 对手冲三
            '010':    50,        # 对手活二
        }

        directions = [(1,0),(0,1),(1,1),(1,-1)]
        def score_at(x, y, patterns, player):
            """在 (x,y) 位置，针对 player（1/2）按 patterns 打分。"""
            total = 0
            for dx, dy in directions:
                # 构建长度 7 的窗口：从 -3 到 +3
                line = ''
                for d in range(-3, 4):
                    nx, ny = x + d*dx, y + d*dy
                    if 0 <= nx < 15 and 0 <= ny < 15:
                        v = self.board[ny][nx]
                        if v == player:
                            line += str(player)
                        elif v == 0:
                            line += '0'
                        else:
                            line += '3'  # 对手的子
                    else:
                        line += '3'      # 边界当对手
                # 对每种模式打分
                for ptn, val in patterns.items():
                    if ptn in line:
                        total += val
            return total

        best_score = -1
        best_move = None

        # 3. 扫描每个空位，计算综合得分
        for y in range(15):
            for x in range(15):
                if self.board[y][x] != 0:
                    continue
                # 本方进攻分 + 对手威胁分 * 权重
                my_score  = score_at(x, y, my_patterns, 2)
                opp_score = score_at(x, y, opp_patterns, 1)
                score = my_score + opp_score * 1.1

                if score > best_score:
                    best_score = score
                    best_move = (x, y)

        # 4. 落子并返回
        if best_move:
            self.place_piece(best_move[0], best_move[1], 2)
            return best_move
        return None


    def check_win(self, x, y, player):
        dirs = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dx, dy in dirs:
            count = 1
            for d in [-1, 1]:
                nx, ny = x, y
                while True:
                    nx += dx * d
                    ny += dy * d
                    if 0 <= nx < 15 and 0 <= ny < 15 and self.board[nx][ny] == player:
                        count += 1
                    else:
                        break
            if count >= 5:
                return True
        return False
