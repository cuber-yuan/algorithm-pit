import json

BOARD_SIZE = 15

class GomokuJudge:
    def __init__(self):
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.current_player = 1  # 1: 黑, 2: 白
        self.move_history = []

    def is_valid_move(self, x, y):
        return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE and self.board[y][x] == 0

    def apply_move(self, x, y):
        if not self.is_valid_move(x, y):
            return False
        self.board[y][x] = self.current_player
        self.move_history.append((self.current_player, x, y))
        self.current_player = 3 - self.current_player  # 1<->2
        return True

    def check_win(self, x, y):
        player = self.board[y][x]
        directions = [(1,0), (0,1), (1,1), (1,-1)]
        for dx, dy in directions:
            count = 1
            for d in [1, -1]:
                nx, ny = x, y
                while True:
                    nx += dx * d
                    ny += dy * d
                    if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and self.board[ny][nx] == player:
                        count += 1
                    else:
                        break
            if count >= 5:
                return player
        return 0

    def to_json(self):
        return json.dumps({
            "board": self.board,
            "current_player": self.current_player,
            "move_history": self.move_history
        })

    def send_action_to_ai(self, player, last_move):
        # last_move: (player, x, y)
        data = {
            "board": self.board,
            "your_side": player,
            "last_move": last_move
        }
        print(json.dumps(data))
        return json.dumps(data)

    def receive_action_from_ai(self):
        # 读取AI的落子
        raw = input()
        move = json.loads(raw)
        x, y = move["x"], move["y"]
        return x, y

if __name__ == "__main__":
    judge = GomokuJudge()
    winner = 0
    while True:
        # 发送当前状态给当前玩家AI
        last_move = judge.move_history[-1] if judge.move_history else None
        judge.send_action_to_ai(judge.current_player, last_move)
        # 接收AI的落子
        x, y = judge.receive_action_from_ai()
        if not judge.apply_move(x, y):
            print(json.dumps({"error": "Invalid move"}))
            break
        winner = judge.check_win(x, y)
        if winner:
            print(json.dumps({"winner": winner}))
            break
        if len(judge.move_history) == BOARD_SIZE * BOARD_SIZE:
            print(json.dumps({"winner": 0}))  # 平局
            break