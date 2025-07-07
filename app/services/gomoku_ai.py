import json
import sys
import math
import random
import time

# --- Constants ---
EMPTY = 0
PLAYER_HUMAN = 1
PLAYER_AI = 2

# Transposition Table Flags
EXACT = 0
LOWER_BOUND = 1
UPPER_BOUND = 2

# --- Evaluation Scores ---
# These scores are critical and need careful tuning.
# Higher scores for AI patterns, negative for Human patterns (opponent's turn perspective)
# Prioritize blocking opponent's patterns heavily
SCORE_WIN = 100000000
WIN_ADJUSTMENT = 1000 # Adjust win score to prioritize faster wins

# AI Offensive Patterns
SCORE_AI_FIVE = SCORE_WIN
SCORE_AI_LIVE_FOUR = 200000 # Unstoppable threat
SCORE_AI_DEAD_FOUR = 25000  # Can become live four
SCORE_AI_LIVE_THREE = 6000  # Strong threat, can become live four
SCORE_AI_DEAD_THREE = 1500
SCORE_AI_LIVE_TWO = 600
SCORE_AI_DEAD_TWO = 150

# Human Defensive (Blocking) Patterns - These scores are absolute values
# AI values these highly because they prevent the opponent from winning or creating strong threats.
SCORE_HUMAN_FIVE = SCORE_WIN # Opponent wins, should be avoided (negative score for AI)
SCORE_HUMAN_LIVE_FOUR = 400000 # Highest priority: block opponent's live four
SCORE_HUMAN_DEAD_FOUR = 20000
SCORE_HUMAN_LIVE_THREE = 50000 # Critical: block opponent's live three
SCORE_HUMAN_DEAD_THREE = 1200
SCORE_HUMAN_LIVE_TWO = 500

class GomokuAI:
    def __init__(self, board_size=15, time_limit=4.5, move_history=None):
        self.board_size = board_size
        self.time_limit = time_limit
        self.board = [[EMPTY] * self.board_size for _ in range(self.board_size)]
        
        # --- Zobrist Hashing and Transposition Table ---
        # Using 2**64 - 1 for a large random range
        self.zobrist_table = [[[random.randint(1, 2**64 - 1) for _ in range(3)] 
                               for _ in range(board_size)] for _ in range(board_size)]
        self.current_hash = 0
        self.transposition_table = {}

        self.start_time = 0
        self.timed_out = False
        
        self.patterns = self._initialize_patterns()

        if move_history:
            self._restore_from_history(move_history)
            # Initialize current_hash based on restored history
            self.current_hash = self._calculate_initial_hash()

    def _calculate_initial_hash(self):
        h = 0
        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] != EMPTY:
                    h ^= self.zobrist_table[r][c][self.board[r][c]]
        return h

    def _initialize_patterns(self):
        # Patterns are represented as strings.
        # 0: EMPTY, 1: PLAYER_HUMAN, 2: PLAYER_AI, 3: OUT_OF_BOUNDS (or blocked by opponent)
        # Scores are from AI's perspective (positive for AI advantage, negative for Human advantage)
        return {
            # AI Patterns (offensive)
            '22222': SCORE_AI_FIVE,
            '022220': SCORE_AI_LIVE_FOUR, # Open ended four
            '122220': SCORE_AI_DEAD_FOUR, '022221': SCORE_AI_DEAD_FOUR, # One end blocked
            '20222': SCORE_AI_DEAD_FOUR, '22022': SCORE_AI_DEAD_FOUR, '22202': SCORE_AI_DEAD_FOUR, # Broken fours
            
            '02220': SCORE_AI_LIVE_THREE, # Open ended three
            '12220': SCORE_AI_DEAD_THREE, '02221': SCORE_AI_DEAD_THREE, # One end blocked
            '020220': SCORE_AI_LIVE_THREE, '022020': SCORE_AI_LIVE_THREE, # Broken live three
            '122020': SCORE_AI_DEAD_THREE, '020221': SCORE_AI_DEAD_THREE, # Broken dead three
            
            '002200': SCORE_AI_LIVE_TWO,
            '102200': SCORE_AI_DEAD_TWO, '002201': SCORE_AI_DEAD_TWO,
            '102020': SCORE_AI_DEAD_TWO, # Broken dead two

            # Human Patterns (defensive for AI, hence negative scores)
            '11111': -SCORE_HUMAN_FIVE,
            '011110': -SCORE_HUMAN_LIVE_FOUR, # Opponent's open ended four - critical to block
            '211110': -SCORE_HUMAN_DEAD_FOUR, '011112': -SCORE_HUMAN_DEAD_FOUR,
            '10111': -SCORE_HUMAN_DEAD_FOUR, '11011': -SCORE_HUMAN_DEAD_FOUR, '11101': -SCORE_HUMAN_DEAD_FOUR,

            '01110': -SCORE_HUMAN_LIVE_THREE, # Opponent's open ended three - critical to block
            '21110': -SCORE_HUMAN_DEAD_THREE, '01112': -SCORE_HUMAN_DEAD_THREE,
            '010110': -SCORE_HUMAN_LIVE_THREE, '011010': -SCORE_HUMAN_LIVE_THREE,
            '211010': -SCORE_HUMAN_DEAD_THREE, '010112': -SCORE_HUMAN_DEAD_THREE,

            '001100': -SCORE_HUMAN_LIVE_TWO,
            '201100': -SCORE_HUMAN_LIVE_TWO/2, '001102': -SCORE_HUMAN_LIVE_TWO/2,
            '201010': -SCORE_HUMAN_LIVE_TWO/2,
        }

    def _restore_from_history(self, move_history):
        for i, move in enumerate(move_history):
            # Player alternates, human is first
            player = PLAYER_HUMAN if i % 2 == 0 else PLAYER_AI
            self.make_move(move['x'], move['y'], player)

    def _update_hash(self, x, y, player):
        # XOR the piece's hash into the current board hash
        self.current_hash ^= self.zobrist_table[y][x][player]

    def make_move(self, x, y, player):
        if self.board[y][x] == EMPTY:
            self.board[y][x] = player
            self._update_hash(x, y, player)
            return True
        return False

    def undo_move(self, x, y):
        player = self.board[y][x]
        if player != EMPTY:
            # XOR out the piece to revert the hash
            self._update_hash(x, y, player) 
            self.board[y][x] = EMPTY
            return True
        return False

    def check_win(self):
        # Check rows, columns, and diagonals for a win
        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] != EMPTY:
                    player = self.board[r][c]
                    # Check horizontal
                    if c <= self.board_size - 5 and all(self.board[r][c+i] == player for i in range(5)): return player
                    # Check vertical
                    if r <= self.board_size - 5 and all(self.board[r+i][c] == player for i in range(5)): return player
                    # Check diagonal (down-right)
                    if r <= self.board_size - 5 and c <= self.board_size - 5 and all(self.board[r+i][c+i] == player for i in range(5)): return player
                    # Check diagonal (up-right)
                    if r >= 4 and c <= self.board_size - 5 and all(self.board[r-i][c+i] == player for i in range(5)): return player
        return EMPTY

    def _get_line_segment(self, r, c, dr, dc, length=9): # Line length for pattern matching
        line_segment = ""
        for i in range(-length // 2, length // 2 + 1):
            nr, nc = r + i * dr, c + i * dc
            if 0 <= nr < self.board_size and 0 <= nc < self.board_size:
                line_segment += str(self.board[nr][nc])
            else:
                line_segment += '3' # Represents out of bounds or blocked
        return line_segment

    def _evaluate_line_score(self, line_str, is_ai_turn):
        score = 0

        # Count all predefined patterns
        for pattern, value in self.patterns.items():
            if pattern in line_str:
                score += value

        # --- Enhanced Threat Detection ---

        # Double live three (threatening win in two ways)
        if line_str.count('02220') + line_str.count('020220') + line_str.count('022020') >= 2:
            score += SCORE_AI_LIVE_FOUR // 2

        # Jump three patterns (can become four)
        jump_threes = ['20220', '22020', '20022', '22002']
        for pat in jump_threes:
            if pat in line_str:
                score += SCORE_AI_DEAD_FOUR // 2

        # Combination of live three and dead four
        if ('02220' in line_str or '022221' in line_str) and ('20222' in line_str or '22022' in line_str):
            score += SCORE_AI_LIVE_FOUR

        # Opponent double live three (high danger)
        if line_str.count('01110') >= 2:
            score -= SCORE_HUMAN_LIVE_FOUR // 2

        # Opponent immediate win threat (live four)
        if line_str.count('011110') >= 1:
            score -= SCORE_HUMAN_LIVE_FOUR * 2

        # AI dead four + live three synergy
        if ('022221' in line_str or '122220' in line_str) and ('02220' in line_str):
            score += SCORE_AI_LIVE_FOUR // 2

        return score

    def evaluate_board(self, current_player):
        score = 0
        # Iterate over all cells to find patterns
        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] != EMPTY:
                    # Check horizontal, vertical, and two diagonals
                    # We only need to check from one "direction" to avoid double counting.
                    # For example, checking left-to-right (dr=0, dc=1) is enough for horizontal.
                    # The pattern matching will extract segments around each piece.
                    
                    # Horizontal
                    line_h = self._get_line_segment(r, c, 0, 1)
                    score += self._evaluate_line_score(line_h, current_player == PLAYER_AI)

                    # Vertical
                    line_v = self._get_line_segment(r, c, 1, 0)
                    score += self._evaluate_line_score(line_v, current_player == PLAYER_AI)

                    # Diagonal (down-right)
                    line_dr = self._get_line_segment(r, c, 1, 1)
                    score += self._evaluate_line_score(line_dr, current_player == PLAYER_AI)

                    # Diagonal (up-right)
                    line_ur = self._get_line_segment(r, c, -1, 1)
                    score += self._evaluate_line_score(line_ur, current_player == PLAYER_AI)
        return score

    def _get_sorted_moves(self):
        candidates = set()
        # Search radius around existing pieces for candidate moves
        search_radius = 2 # Consider moves within 2 squares of an existing piece
        
        # If board is empty, suggest center move
        is_board_empty = True
        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] != EMPTY:
                    is_board_empty = False
                    break
            if not is_board_empty:
                break
        
        if is_board_empty:
            return [(self.board_size // 2, self.board_size // 2)]

        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] != EMPTY:
                    for dr in range(-search_radius, search_radius + 1):
                        for dc in range(-search_radius, search_radius + 1):
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < self.board_size and 0 <= nc < self.board_size and self.board[nr][nc] == EMPTY:
                                candidates.add((nc, nr))
        
        if not candidates:
            return []

        # Heuristic sorting: Evaluate each candidate move with a shallow lookahead
        # Give higher scores to moves that create strong patterns for AI or block strong patterns for Human.
        move_scores = {}
        for x, y in candidates:
            score = 0
            # Temporarily make the move for AI and evaluate
            self.make_move(x, y, PLAYER_AI)
            # Evaluate the board from AI's perspective after making the move
            score_ai_move = self.evaluate_board(PLAYER_AI) # Positive is good for AI
            self.undo_move(x, y) # Undo the move

            # Temporarily make the move for Human and evaluate (for blocking)
            self.make_move(x, y, PLAYER_HUMAN)
            # Evaluate the board from Human's perspective (negative for AI)
            score_human_move = self.evaluate_board(PLAYER_HUMAN) # More negative is bad for AI, so we want to block these
            self.undo_move(x, y)

            # A good move for AI either greatly increases AI's score or greatly decreases Human's score.
            # Using current_player to evaluate makes sense. In _get_sorted_moves, we are
            # trying to find the best move for the AI, so we evaluate if AI takes the spot
            # and if Human takes the spot.
            
            # Prioritize moves that create offensive patterns for AI or block defensive patterns for Human.
            # The pattern scores already have signs, so we add them.
            # A move is good if it creates AI threats or blocks human threats.
            # When we check for Human's move, we expect the score to become very negative if it's a threat.
            # So, we want to maximize our score_ai_move AND maximize the negative score_human_move (which is equivalent to minimizing opponent's score)
            move_scores[(x,y)] = score_ai_move - score_human_move # This simple diff might need tuning

        # Sort moves by their heuristic score in descending order
        sorted_moves = sorted(list(candidates), key=lambda m: move_scores[m], reverse=True)
        return sorted_moves

    def minimax(self, depth, alpha, beta, maximizing_player):
        # Time check
        if self.timed_out or time.time() - self.start_time > self.time_limit:
            self.timed_out = True
            return 0 # Return a neutral score if timed out to avoid bad decisions

        # Transposition Table Lookup
        alpha_orig = alpha
        tt_entry = self.transposition_table.get(self.current_hash)
        if tt_entry and tt_entry['depth'] >= depth:
            if tt_entry['flag'] == EXACT:
                return tt_entry['score']
            elif tt_entry['flag'] == LOWER_BOUND:
                alpha = max(alpha, tt_entry['score'])
            elif tt_entry['flag'] == UPPER_BOUND:
                beta = min(beta, tt_entry['score'])
            if alpha >= beta: # Pruning based on stored bounds
                return tt_entry['score']

        # Terminal node check
        winner = self.check_win()
        if winner != EMPTY:
            return (SCORE_WIN - (20 - depth) * WIN_ADJUSTMENT) if winner == PLAYER_AI else -(SCORE_WIN - (20 - depth) * WIN_ADJUSTMENT)
        
        if depth == 0:
            # Evaluate board at leaf node
            # The 'maximizing_player' here refers to whose turn it is
            return self.evaluate_board(PLAYER_AI if maximizing_player else PLAYER_HUMAN)

        moves = self._get_sorted_moves()
        if not moves: # No moves possible, e.g., full board (draw, though rare in Gomoku)
            return 0

        best_score = -math.inf if maximizing_player else math.inf
        best_move_for_tt = None # Store the best move for TT

        for x, y in moves:
            current_player_to_move = PLAYER_AI if maximizing_player else PLAYER_HUMAN
            self.make_move(x, y, current_player_to_move)

            if maximizing_player:
                score = self.minimax(depth - 1, alpha, beta, False) # Next turn is opponent's (minimizing)
                if score > best_score:
                    best_score = score
                    best_move_for_tt = (x,y)
                alpha = max(alpha, best_score)
            else: # Minimizing player
                score = self.minimax(depth - 1, alpha, beta, True) # Next turn is AI's (maximizing)
                if score < best_score:
                    best_score = score
                    best_move_for_tt = (x,y)
                beta = min(beta, best_score)
            
            self.undo_move(x, y) # Undo the move
            
            if self.timed_out:
                return 0 # Propagate timeout

            if alpha >= beta: # Alpha-beta cut-off
                break
        
        # Store result in Transposition Table
        flag = EXACT
        if maximizing_player:
            if best_score <= alpha_orig: # A higher value was found, so it's a lower bound
                flag = LOWER_BOUND
            elif best_score >= beta: # Beta cut-off, means it's an upper bound
                flag = UPPER_BOUND
        else: # Minimizing player
            if best_score <= alpha_orig: # Alpha cut-off, means it's a lower bound
                flag = LOWER_BOUND
            elif best_score >= beta: # A lower value was found, so it's an upper bound
                flag = UPPER_BOUND

        self.transposition_table[self.current_hash] = {
            'score': best_score, 'depth': depth, 'flag': flag, 'best_move': best_move_for_tt
        }
        
        return best_score

    def find_best_move(self):
        self.start_time = time.time()
        self.timed_out = False
        self.transposition_table.clear() # Clear table for each new move decision

        overall_best_move = None
        
        # Iterative Deepening Loop
        # Start with a shallow depth and increase, allowing for best move even if timed out later.
        # A typical max depth for Gomoku AI in 4.5s could be 4-6, depending on pruning efficiency.
        # Starting with 1 or 2 is usually good.
        for depth in range(1, 10): # Max depth could be adjusted, but time will limit it.
            # Perform minimax search for AI (maximizing player)
            score = self.minimax(depth, -math.inf, math.inf, True)
            
            if self.timed_out:
                # If timed out, use the best move found in the previous, completed depth.
                # If no move was found yet, fallback to sorted moves.
                break 

            tt_entry = self.transposition_table.get(self.current_hash)
            if tt_entry and tt_entry.get('best_move'):
                overall_best_move = tt_entry['best_move']
            
            # If a winning move is found, stop searching deeper.
            # Consider a win as SCORE_WIN - WIN_ADJUSTMENT to prioritize earlier wins.
            if tt_entry and tt_entry['score'] >= SCORE_WIN - WIN_ADJUSTMENT:
                break
        
        # Fallback if no specific best move was determined by iterative deepening
        # (e.g., initial state is empty and timeout occurs immediately before a search finishes)
        if overall_best_move is None:
            moves = self._get_sorted_moves()
            if moves:
                return moves[0] # Return the heuristically best move
            
        return overall_best_move

def main():
    try:
        input_data = json.loads(input().strip())
        move_history = input_data.get('move_history', [])
        
        game = GomokuAI(move_history=move_history, time_limit=4.5)
        
        best_move = game.find_best_move()
        
        if best_move:
            result = {"x": best_move[0], "y": best_move[1]}
            print(json.dumps(result))
        else:
            # This case should ideally not be hit if _get_sorted_moves handles empty/full boards.
            # If no valid move found at all (e.g., board full), return an error.
            print(json.dumps({"error": "No valid move found or board is full."}))
            
    except Exception as e:
        # Catch any unexpected errors and return them in JSON format
        print(json.dumps({"error": str(e), "type": type(e).__name__, "message": "An unexpected error occurred during AI computation."}))

if __name__ == '__main__':
    main()