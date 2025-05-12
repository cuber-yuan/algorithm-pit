# game.py

class GomokuGame:
    def __init__(self):
        self.board = [[0] * 15 for _ in range(15)]
        self.current_player = 1  # 1 = player, 2 = AI
        self.winner = 0

    def is_valid(self, x, y):
        return 0 <= x < 15 and 0 <= y < 15 and self.board[x][y] == 0

    def new_game(self):
        self.board = [[0] * 15 for _ in range(15)]
        self.current_player = 1  # 1 = player, 2 = AI
        self.winner = 0
        
    def place_piece(self, x, y, player):
        if self.is_valid(x, y) and self.winner == 0 and self.current_player == player:
            self.board[x][y] = player
            if self.check_win(x, y, player):
                self.winner = player
            self.current_player = 3 - player
            return True
        return False

    def ai_move(self):
        def score(x, y, player):
            count = 0
            directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
            for dx, dy in directions:
                line = 1
                for d in range(1, 5):
                    nx, ny = x + dx * d, y + dy * d
                    if nx < 0 or ny < 0 or nx >= 15 or ny >= 15:
                        break
                    if self.board[nx][ny] == player:
                        line += 1
                    else:
                        break
                for d in range(1, 5):
                    nx, ny = x - dx * d, y - dy * d
                    if nx < 0 or ny < 0 or nx >= 15 or ny >= 15:
                        break
                    if self.board[nx][ny] == player:
                        line += 1
                    else:
                        break
                count = max(count, line)
            center_bonus = 15 - abs(x - 15 / 2) - abs(y - 15 / 2)
            return count * 10 + center_bonus

        best = {'score': -1, 'x': 0, 'y': 0}

        for i in range(15):
            for j in range(15):
                if self.board[i][j] != 0:
                    continue

                # 模拟 AI 胜利
                self.board[i][j] = 2
                if self.check_win(i, j, 2):
                    self.winner = 2
                    print("AI wins!")
                    gameOver = True
                    self.current_player = 1
                    return [i,j]
                self.board[i][j] = 0

                # 模拟玩家胜利并阻止
                self.board[i][j] = 1
                if self.check_win(i, j, 1):
                    self.board[i][j] = 2
                    self.current_player = 1
                    return[i,j]
                self.board[i][j] = 0

                # 综合评分
                s = score(i, j, 2)
                if s > best['score']:
                    best = {'score': s, 'x': i, 'y': j}

        self.board[best['x']][best['y']] = 2
        if self.check_win(best['x'], best['y'], 2):
            print("AI wins!")
            self.winner = 2
            gameOver = True
        self.current_player = 1
        return [best['x'],best['y']]
        


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
