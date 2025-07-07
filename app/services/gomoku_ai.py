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
SCORE_LOSS = -100000000
SCORE_LIVE_FOUR = 50000
SCORE_BLOCK_LIVE_FOUR = 100000
SCORE_LIVE_THREE = 5000
SCORE_BLOCK_LIVE_THREE = 10000
SCORE_LIVE_TWO = 500
SCORE_BLOCK_LIVE_TWO = 1000
SCORE_DEAD_FOUR = 1000
SCORE_BLOCK_DEAD_FOUR = 2000

class GomokuGame:
    def __init__(self, board_size=15, search_depth=3):
        self.board_size = board_size
        self.search_depth = search_depth
        self.current_player = PLAYER_HUMAN
        self.winner = EMPTY
        self.board = [[EMPTY] * self.board_size for _ in range(self.board_size)]

        # Zobrist Hashing and Transposition Table
        self.zobrist_table = [[[random.randint(1, 2**64 - 1) for _ in range(3)]
                               for _ in range(self.board_size)]
                              for _ in range(self.board_size)]
        self.current_hash = 0
        self.transposition_table = {}
        self.killer_moves = [[(None, None), (None, None)] for _ in range(search_depth + 5)]
        self._initialize_hash()

    def _initialize_hash(self):
        self.current_hash = 0
        for r in range(self.board_size):
            for c in range(self.board_size):
                piece = self.board[r][c]
                if piece != EMPTY:
                    self.current_hash ^= self.zobrist_table[r][c][piece]

    def _update_hash(self, r, c, old_piece, new_piece):
        if old_piece != EMPTY:
            self.current_hash ^= self.zobrist_table[r][c][old_piece]
        if new_piece != EMPTY:
            self.current_hash ^= self.zobrist_table[r][c][new_piece]

    def is_valid(self, x, y):
        return 0 <= x < self.board_size and 0 <= y < self.board_size and self.board[y][x] == EMPTY

    def place_piece(self, x, y, player):
        """Place piece at (x, y) - x=column, y=row"""
        if self.is_valid(x, y):
            old_piece = self.board[y][x]
            self.board[y][x] = player
            self._update_hash(y, x, old_piece, player)
            return True
        return False

    def check_win(self, x, y, player):
        """Check if player wins by placing at (x, y)"""
        if self.board[y][x] != player:
            return False
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for dx, dy in directions:
            count = 1
            # Check positive direction
            for i in range(1, 5):
                nx, ny = x + i * dx, y + i * dy
                if 0 <= nx < self.board_size and 0 <= ny < self.board_size and self.board[ny][nx] == player:
                    count += 1
                else:
                    break
            # Check negative direction
            for i in range(1, 5):
                nx, ny = x - i * dx, y - i * dy
                if 0 <= nx < self.board_size and 0 <= ny < self.board_size and self.board[ny][nx] == player:
                    count += 1
                else:
                    break
            if count >= 5:
                return True
        return False

    def get_candidate_moves(self):
        """Get candidate moves around existing pieces"""
        if all(self.board[r][c] == EMPTY for r in range(self.board_size) for c in range(self.board_size)):
            return [(self.board_size // 2, self.board_size // 2)]

        candidates = set()
        radius = 2  # Search radius around existing pieces

        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] != EMPTY:
                    for dr in range(-radius, radius + 1):
                        for dc in range(-radius, radius + 1):
                            if dr == 0 and dc == 0:
                                continue
                            nr, nc = r + dr, c + dc
                            if 0 <= nc < self.board_size and 0 <= nr < self.board_size and self.board[nr][nc] == EMPTY:
                                candidates.add((nc, nr))  # (x, y) format

        return list(candidates) if candidates else []

    def evaluate_board(self):
        """Evaluate current board position"""
        total_score = 0
        
        # Check all possible lines of 5
        for r in range(self.board_size):
            for c in range(self.board_size):
                # Horizontal
                if c <= self.board_size - 5:
                    line = [self.board[r][c+i] for i in range(5)]
                    total_score += self.evaluate_line(line)
                # Vertical
                if r <= self.board_size - 5:
                    line = [self.board[r+i][c] for i in range(5)]
                    total_score += self.evaluate_line(line)
                # Diagonal \
                if r <= self.board_size - 5 and c <= self.board_size - 5:
                    line = [self.board[r+i][c+i] for i in range(5)]
                    total_score += self.evaluate_line(line)
                # Diagonal /
                if r <= self.board_size - 5 and c >= 4:
                    line = [self.board[r+i][c-i] for i in range(5)]
                    total_score += self.evaluate_line(line)
        
        return total_score

    def evaluate_line(self, line):
        """Evaluate a line of 5 positions"""
        ai_count = line.count(PLAYER_AI)
        human_count = line.count(PLAYER_HUMAN)
        empty_count = line.count(EMPTY)
        
        score = 0
        
        # If line contains both players, it's useless
        if ai_count > 0 and human_count > 0:
            return 0
            
        # AI patterns
        if ai_count == 4 and empty_count == 1:
            score += SCORE_LIVE_FOUR
        elif ai_count == 3 and empty_count == 2:
            score += SCORE_LIVE_THREE
        elif ai_count == 2 and empty_count == 3:
            score += SCORE_LIVE_TWO
            
        # Human patterns (threats to block)
        if human_count == 4 and empty_count == 1:
            score -= SCORE_BLOCK_LIVE_FOUR
        elif human_count == 3 and empty_count == 2:
            score -= SCORE_BLOCK_LIVE_THREE
        elif human_count == 2 and empty_count == 3:
            score -= SCORE_BLOCK_LIVE_TWO
            
        return score

    def minimax(self, depth, alpha, beta, is_maximizing, last_move=None):
        """Minimax with alpha-beta pruning"""
        # Check for terminal states
        if last_move:
            x, y = last_move
            player = self.board[y][x]
            if self.check_win(x, y, player):
                return SCORE_WIN if player == PLAYER_AI else SCORE_LOSS
                
        if depth == 0:
            return self.evaluate_board()

        candidates = self.get_candidate_moves()
        if not candidates:
            return 0

        if is_maximizing:  # AI turn
            max_eval = -math.inf
            for x, y in candidates:
                self.board[y][x] = PLAYER_AI
                eval_score = self.minimax(depth - 1, alpha, beta, False, (x, y))
                self.board[y][x] = EMPTY
                
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            return max_eval
        else:  # Human turn
            min_eval = math.inf
            for x, y in candidates:
                self.board[y][x] = PLAYER_HUMAN
                eval_score = self.minimax(depth - 1, alpha, beta, True, (x, y))
                self.board[y][x] = EMPTY
                
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            return min_eval

    def find_best_move(self):
        """Find the best move for AI"""
        candidates = self.get_candidate_moves()
        if not candidates:
            return None

        # Check for immediate win
        for x, y in candidates:
            self.board[y][x] = PLAYER_AI
            if self.check_win(x, y, PLAYER_AI):
                self.board[y][x] = EMPTY
                return (x, y)
            self.board[y][x] = EMPTY

        # Check for immediate threat to block
        for x, y in candidates:
            self.board[y][x] = PLAYER_HUMAN
            if self.check_win(x, y, PLAYER_HUMAN):
                self.board[y][x] = EMPTY
                return (x, y)
            self.board[y][x] = EMPTY

        # Use minimax to find best move
        best_move = None
        best_score = -math.inf

        for x, y in candidates:
            self.board[y][x] = PLAYER_AI
            score = self.minimax(self.search_depth - 1, -math.inf, math.inf, False, (x, y))
            self.board[y][x] = EMPTY
            
            if score > best_score:
                best_score = score
                best_move = (x, y)

        return best_move

    def restore_from_history(self, move_history):
        """Restore board state from move history"""
        self.board = [[EMPTY] * self.board_size for _ in range(self.board_size)]
        
        for i, move in enumerate(move_history):
            x, y = move['x'], move['y']
            player = PLAYER_HUMAN if i % 2 == 0 else PLAYER_AI  # Assume human plays first
            self.place_piece(x, y, player)

def main():
    """Main function to process one move"""
    try:
        # Read JSON input
        input_data = json.loads(input().strip())
        
        # Create game instance
        game = GomokuGame()
        
        # Restore game state from history
        move_history = input_data.get('move_history', [])
        game.restore_from_history(move_history)
        
        # Find best move for AI
        best_move = game.find_best_move()
        
        if best_move:
            x, y = best_move
            # Output JSON result
            result = {"x": x, "y": y}
            print(json.dumps(result))
        else:
            # No valid move found
            print(json.dumps({"error": "No valid move"}))
            
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == '__main__':
    main()