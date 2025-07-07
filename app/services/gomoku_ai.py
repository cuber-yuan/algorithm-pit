import json
import sys
import math
import random
import time

# Constants for players
EMPTY = 0
PLAYER_HUMAN = 1
PLAYER_AI = 2

# Scores for evaluation
SCORE_WIN = 100000000
SCORE_LOSS = -SCORE_WIN
# A win found at a shallower depth is better
WIN_ADJUSTMENT = 1000 

# Scores for AI player's patterns
SCORE_LIVE_FOUR = 100000
SCORE_DEAD_FOUR = 15000
SCORE_LIVE_THREE = 5000
SCORE_DEAD_THREE = 1000
SCORE_LIVE_TWO = 500
SCORE_DEAD_TWO = 100

# Scores for blocking opponent's patterns (Human)
SCORE_BLOCK_LIVE_FOUR = 80000
SCORE_BLOCK_DEAD_FOUR = 20000
SCORE_BLOCK_LIVE_THREE = 40000
SCORE_BLOCK_DEAD_THREE = 8000
SCORE_BLOCK_LIVE_TWO = 800

class GomokuAI:
    def __init__(self, board_size=15, time_limit=4.5, move_history=None):
        self.board_size = board_size
        self.time_limit = time_limit
        self.board = [[EMPTY] * self.board_size for _ in range(self.board_size)]
        self.total_score = 0
        self.start_time = 0
        self.timed_out = False

        self.patterns = self._initialize_patterns()

        if move_history:
            self._restore_from_history(move_history)

    def _initialize_patterns(self):
        """Initializes a dictionary of threat patterns and their scores."""
        p = {
            # AI Patterns (Player 2)
            "22222": SCORE_WIN,
            "022220": SCORE_LIVE_FOUR,
            "122220": SCORE_DEAD_FOUR, "022221": SCORE_DEAD_FOUR,
            "22202": SCORE_DEAD_FOUR, "20222": SCORE_DEAD_FOUR, "22022": SCORE_DEAD_FOUR,
            "02220": SCORE_LIVE_THREE,
            "122200": SCORE_DEAD_THREE, "002221": SCORE_DEAD_THREE,
            "122020": SCORE_DEAD_THREE, "020221": SCORE_DEAD_THREE,
            "02200": SCORE_LIVE_TWO,
            "122000": SCORE_DEAD_TWO, "000221": SCORE_DEAD_TWO,
            
            # Human Patterns (Player 1) - scores are negative for AI
            "11111": SCORE_LOSS,
            "011110": -SCORE_BLOCK_LIVE_FOUR,
            "211110": -SCORE_BLOCK_DEAD_FOUR, "011112": -SCORE_BLOCK_DEAD_FOUR,
            "11101": -SCORE_BLOCK_DEAD_FOUR, "10111": -SCORE_BLOCK_DEAD_FOUR, "11011": -SCORE_BLOCK_DEAD_FOUR,
            "01110": -SCORE_BLOCK_LIVE_THREE,
            "211100": -SCORE_BLOCK_DEAD_THREE, "001112": -SCORE_BLOCK_DEAD_THREE,
            "211010": -SCORE_BLOCK_DEAD_THREE, "010112": -SCORE_BLOCK_DEAD_THREE,
            "01100": -SCORE_BLOCK_LIVE_TWO,
            "211000": -SCORE_BLOCK_LIVE_TWO / 2, "000112": -SCORE_BLOCK_LIVE_TWO / 2
        }
        return p

    def _restore_from_history(self, move_history):
        """Efficiently restores board state and incrementally calculates the total score."""
        for i, move in enumerate(move_history):
            player = PLAYER_HUMAN if i % 2 == 0 else PLAYER_AI
            # The incremental update is embedded in make_move, so this is efficient
            self.make_move(move['x'], move['y'], player)

    def make_move(self, x, y, player):
        """Places a piece and incrementally updates the board score."""
        if self.board[y][x] == EMPTY:
            self._update_score(x, y, player)
            self.board[y][x] = player
            return True
        return False

    def undo_move(self, x, y):
        """Removes a piece and incrementally reverts the board score."""
        player = self.board[y][x]
        if player != EMPTY:
            self.board[y][x] = EMPTY
            self._update_score(x, y, player) # Re-calculates score changes
            return True
        return False
        
    def _update_score(self, x, y, player):
        """Calculates the change in score by analyzing lines through (x, y)."""
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dx, dy in directions:
            old_line = self._get_line(x, y, dx, dy)
            self.total_score -= self._evaluate_line(old_line)
            
            self.board[y][x] = player
            new_line = self._get_line(x, y, dx, dy)
            self.total_score += self._evaluate_line(new_line)
            
            self.board[y][x] = EMPTY

    def _get_line(self, x, y, dx, dy):
        """Gets a string representation of a line of 9 cells through (x,y)."""
        line = ""
        for i in range(-4, 5):
            nx, ny = x + i * dx, y + i * dy
            if 0 <= nx < self.board_size and 0 <= ny < self.board_size:
                line += str(self.board[ny][nx])
            else:
                line += '3' # Border/wall
        return line

    def _evaluate_line(self, line):
        score = 0
        for pattern, value in self.patterns.items():
            if pattern in line:
                score += value
        return score
        
    def check_win_at(self, x, y, player):
        self.board[y][x] = player
        for dx, dy in [(1,0), (0,1), (1,1), (1,-1)]:
            count = 0
            for i in range(-4, 5):
                nx, ny = x + i*dx, y + i*dy
                if 0 <= nx < self.board_size and 0 <= ny < self.board_size and self.board[ny][nx] == player:
                    count += 1
                    if count >= 5:
                        self.board[y][x] = EMPTY
                        return True
                else:
                    count = 0
        self.board[y][x] = EMPTY
        return False

    def get_candidate_moves(self):
        if all(self.board[r][c] == EMPTY for r in range(self.board_size) for c in range(self.board_size)):
            return [(self.board_size // 2, self.board_size // 2)]
        candidates = set()
        radius = 2
        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] != EMPTY:
                    for dr in range(-radius, radius + 1):
                        for dc in range(-radius, radius + 1):
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < self.board_size and 0 <= nc < self.board_size and self.board[nr][nc] == EMPTY:
                                candidates.add((nc, nr))
        return list(candidates)

    def minimax(self, depth, alpha, beta, is_maximizing_player):
        if time.time() - self.start_time > self.time_limit:
            self.timed_out = True
            return 0 # Bail out

        # Terminal state check
        if depth == 0:
            return self.total_score if is_maximizing_player else -self.total_score

        player = PLAYER_AI if is_maximizing_player else PLAYER_HUMAN
        moves = self.get_candidate_moves()

        if not moves:
            return 0
        
        # Move ordering could be improved here by checking promising moves first

        if is_maximizing_player:
            max_eval = -math.inf
            for x, y in moves:
                if self.check_win_at(x,y,player):
                    return SCORE_WIN - (20 - depth) # Prioritize faster wins
                
                self.make_move(x, y, player)
                eval_score = self.minimax(depth - 1, alpha, beta, False)
                self.undo_move(x, y)
                
                if self.timed_out: return 0
                
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = math.inf
            for x, y in moves:
                if self.check_win_at(x,y,player):
                    return SCORE_LOSS + (20 - depth) # Postpone losses
                
                self.make_move(x, y, player)
                eval_score = self.minimax(depth - 1, alpha, beta, True)
                self.undo_move(x, y)

                if self.timed_out: return 0
                
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            return min_eval

    def find_best_move(self):
        """
        Finds the best move using Iterative Deepening and a time limit.
        """
        self.start_time = time.time()
        self.timed_out = False
        
        candidates = self.get_candidate_moves()
        if not candidates:
            return None

        # Check for immediate win or loss to respond instantly
        for x, y in candidates:
            if self.check_win_at(x, y, PLAYER_AI):
                return (x, y)
        for x, y in candidates:
            if self.check_win_at(x, y, PLAYER_HUMAN):
                return (x, y)

        overall_best_move = candidates[0]
        
        # Iterative Deepening Loop
        for depth in range(1, 20): # Max depth, will be stopped by time
            best_move_this_iteration = None
            best_score = -math.inf
            
            for x, y in candidates:
                self.make_move(x, y, PLAYER_AI)
                score = self.minimax(depth, -math.inf, math.inf, False)
                self.undo_move(x, y)

                if self.timed_out:
                    break 

                if score > best_score:
                    best_score = score
                    best_move_this_iteration = (x, y)
            
            if self.timed_out:
                break # Exit the depth loop if the search for this depth timed out

            if best_move_this_iteration:
                overall_best_move = best_move_this_iteration
                # Move ordering: best move from this depth goes first in the next
                candidates.remove(overall_best_move)
                candidates.insert(0, overall_best_move)
            
            # If a win is found, no need to search deeper
            if best_score >= SCORE_WIN - (20 - depth + 1):
                break

        return overall_best_move


def main():
    try:
        input_data = json.loads(input().strip())
        move_history = input_data.get('move_history', [])
        
        # Initialize AI. The time limit ensures a timely response.
        game = GomokuAI(move_history=move_history, time_limit=4.5)
        
        best_move = game.find_best_move()
        
        if best_move:
            result = {"x": best_move[0], "y": best_move[1]}
            print(json.dumps(result))
        else:
            print(json.dumps({"error": "No valid move found"}))
            
    except Exception as e:
        print(json.dumps({"error": str(e), "type": type(e).__name__}))

if __name__ == '__main__':
    main()