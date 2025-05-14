# game.py
import math
import random
import time # For potential time limits in IDDFS

# Constants for players
EMPTY = 0
PLAYER_HUMAN = 1
PLAYER_AI = 2

# Scores for evaluation - ensure win/loss scores are dominant
SCORE_WIN = 100000000  # AI wins
SCORE_LOSS = -100000000 # Human wins (AI loses)
SCORE_LIVE_FOUR = 50000
SCORE_BLOCK_LIVE_FOUR = 100000 # Blocking opponent's live four is more critical
SCORE_LIVE_THREE = 5000
SCORE_BLOCK_LIVE_THREE = 10000
SCORE_LIVE_TWO = 500
SCORE_BLOCK_LIVE_TWO = 1000
SCORE_DEAD_FOUR = 1000 # AI's Dead Four (e.g. X X X X O)
SCORE_BLOCK_DEAD_FOUR = 2000
# ... other scores for dead threes, twos, etc.

class GomokuGame:
    def __init__(self, board_size=15, search_depth=3): # search_depth is max for IDDFS
        self.board_size = board_size
        self.search_depth = search_depth # Max depth for Iterative Deepening
        self.current_player = PLAYER_HUMAN
        self.winner = EMPTY
        self.board = [[EMPTY] * self.board_size for _ in range(self.board_size)]

        # Zobrist Hashing and Transposition Table
        self.zobrist_table = [[[random.randint(1, 2**64 - 1) for _ in range(3)]  # 0: empty, 1: P1, 2: P2
                               for _ in range(self.board_size)]
                              for _ in range(self.board_size)]
        self.current_hash = 0
        self.transposition_table = {} # {hash: {'depth', 'score', 'flag', 'best_move'}}
                                      # flag: 'EXACT', 'LOWERBOUND', 'UPPERBOUND'
        self._initialize_hash()

        # Killer Moves: store 2 killer moves per ply
        # Max practical depth for killers might be around 10-15 plies
        self.killer_moves = [[(None, None), (None, None)] for _ in range(search_depth + 5)] # Max depth + buffer
        self.is_player_turn = True  # Initialize to True, as the player starts the game

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

    def new_game(self):
        self.board = [[EMPTY] * self.board_size for _ in range(self.board_size)]
        self.current_player = PLAYER_HUMAN
        self.winner = EMPTY
        self._initialize_hash()
        self.transposition_table.clear()
        self.killer_moves = [[(None, None), (None, None)] for _ in range(self.search_depth + 5)]
        self.is_player_turn = True  # Reset to True for a new game

    def is_valid(self, x, y):
        return 0 <= x < self.board_size and 0 <= y < self.board_size and self.board[x][y] == EMPTY

    def place_piece(self, x, y, player_to_place=None):
        if player_to_place is None:
            player_to_place = self.current_player

        if self.is_valid(x, y) and self.winner == EMPTY:
            old_piece = self.board[x][y] # Should be EMPTY
            self.board[x][y] = player_to_place
            self._update_hash(x, y, old_piece, player_to_place)

            if self.check_win(x, y, player_to_place):
                self.winner = player_to_place
            
            # Only switch current_player if the move was made by the actual current_player
            if player_to_place == self.current_player:
                 self.current_player = PLAYER_AI if self.current_player == PLAYER_HUMAN else PLAYER_HUMAN
            return True
        return False

    def check_win(self, x, y, player):
        if self.board[x][y] != player:
            return False
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for dx, dy in directions:
            count = 1
            for i in range(1, 5):
                nx, ny = x + i * dx, y + i * dy
                if 0 <= nx < self.board_size and 0 <= ny < self.board_size and self.board[nx][ny] == player:
                    count += 1
                else:
                    break
            for i in range(1, 5):
                nx, ny = x - i * dx, y - i * dy
                if 0 <= nx < self.board_size and 0 <= ny < self.board_size and self.board[nx][ny] == player:
                    count += 1
                else:
                    break
            if count >= 5:
                return True
        return False

    def get_candidate_moves(self, last_player_made_move=None):
        if all(self.board[r][c] == EMPTY for r in range(self.board_size) for c in range(self.board_size)):
            return [(self.board_size // 2, self.board_size // 2)]

        candidates = set()
        # Radius for considering moves around existing pieces
        # Larger radius might find better moves but increases branching factor
        radius = 1 # Check 1 cell away
        # radius = 2 # Check up to 2 cells away for more aggressive search (slower)

        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] != EMPTY:
                    for dr in range(-radius, radius + 1):
                        for dc in range(-radius, radius + 1):
                            if dr == 0 and dc == 0:
                                continue
                            nr, nc = r + dr, c + dc
                            if self.is_valid(nr, nc):
                                candidates.add((nr, nc))
        
        if not candidates: # No candidates near pieces, e.g., board almost full
            return [(r, c) for r in range(self.board_size) for c in range(self.board_size) if self.is_valid(r,c)]
        
        # Simple heuristic pre-sort: check for immediate threats/opportunities
        # This could be more sophisticated, e.g. checking for fours, threes
        # For now, just a basic list, more advanced ordering happens within minimax/IDDFS
        return list(candidates)


    def evaluate_line(self, line, player_perspective):
        """Evaluates a single line of 5 cells for a given player perspective."""
        ai_player = PLAYER_AI
        human_player = PLAYER_HUMAN
        
        score = 0
        
        # AI's patterns
        ai_pieces = line.count(ai_player)
        empty_pieces_ai = line.count(EMPTY)
        if ai_pieces == 5: score += SCORE_WIN // 10 # Part of a win
        elif ai_pieces == 4 and empty_pieces_ai == 1: score += SCORE_LIVE_FOUR
        elif ai_pieces == 3 and empty_pieces_ai == 2: score += SCORE_LIVE_THREE
        elif ai_pieces == 2 and empty_pieces_ai == 3: score += SCORE_LIVE_TWO
        elif ai_pieces == 4 and empty_pieces_ai == 0 and line.count(human_player) == 1: # Effectively a dead four if blocked by human
             pass # Or a small score
        elif ai_pieces == 3 and empty_pieces_ai == 1 : score += SCORE_LIVE_THREE / 2 # Potential for dead four or strong three
        
        # Human's patterns (from AI's perspective, these are threats to block)
        human_pieces = line.count(human_player)
        empty_pieces_human = line.count(EMPTY)
        if human_pieces == 5: score -= SCORE_LOSS // 10 # Part of a loss
        elif human_pieces == 4 and empty_pieces_human == 1: score -= SCORE_BLOCK_LIVE_FOUR
        elif human_pieces == 3 and empty_pieces_human == 2: score -= SCORE_BLOCK_LIVE_THREE
        elif human_pieces == 2 and empty_pieces_human == 3: score -= SCORE_BLOCK_LIVE_TWO
        elif human_pieces == 3 and empty_pieces_human == 1: score -= SCORE_BLOCK_LIVE_THREE / 2

        return score if player_perspective == ai_player else -score


    def evaluate_board(self):
        ai_player = PLAYER_AI
        total_score = 0

        for r in range(self.board_size):
            for c in range(self.board_size):
                # Horizontal
                if c <= self.board_size - 5:
                    line = [self.board[r][c+i] for i in range(5)]
                    total_score += self.evaluate_line(line, ai_player)
                # Vertical
                if r <= self.board_size - 5:
                    line = [self.board[r+i][c] for i in range(5)]
                    total_score += self.evaluate_line(line, ai_player)
                # Diagonal \
                if r <= self.board_size - 5 and c <= self.board_size - 5:
                    line = [self.board[r+i][c+i] for i in range(5)]
                    total_score += self.evaluate_line(line, ai_player)
                # Diagonal /
                if r <= self.board_size - 5 and c >= 4:
                    line = [self.board[r+i][c-i] for i in range(5)]
                    total_score += self.evaluate_line(line, ai_player)
        
        # Slight positional bonus (can be tuned)
        # for r_idx in range(self.board_size):
        #     for c_idx in range(self.board_size):
        #         if self.board[r_idx][c_idx] == PLAYER_AI:
        #             total_score += (7 - abs(r_idx - 7)) + (7 - abs(c_idx - 7)) # Max bonus at center (7,7 for 15x15)
        #         elif self.board[r_idx][c_idx] == PLAYER_HUMAN:
        #             total_score -= (7 - abs(r_idx - 7)) + (7 - abs(c_idx - 7))
        return total_score

    def _add_killer_move(self, move, ply):
        if ply < len(self.killer_moves):
            if move != self.killer_moves[ply][0]:
                self.killer_moves[ply][1] = self.killer_moves[ply][0]
                self.killer_moves[ply][0] = move
    
    def _order_moves(self, candidate_moves, ply, tt_move):
        # Simple ordering: TT move, then Killer moves, then others
        ordered = []
        if tt_move and tt_move in candidate_moves:
            ordered.append(tt_move)
        
        if ply < len(self.killer_moves):
            for killer in self.killer_moves[ply]:
                if killer and killer != tt_move and killer in candidate_moves:
                    ordered.append(killer)
        
        for move in candidate_moves:
            if move not in ordered:
                ordered.append(move)
        return ordered

    def minimax(self, depth, alpha, beta, is_maximizing_player, ply_from_root, last_move_coord=None):
        # `ply_from_root` is the number of moves made from the root of this search iteration
        original_alpha = alpha
        
        # 1. Transposition Table Lookup
        tt_entry = self.transposition_table.get(self.current_hash)
        tt_move = None
        if tt_entry and tt_entry['depth'] >= depth:
            if tt_entry['flag'] == 'EXACT':
                return tt_entry['score'], tt_entry.get('best_move')
            elif tt_entry['flag'] == 'LOWERBOUND': # Stored score is a lower bound (alpha)
                alpha = max(alpha, tt_entry['score'])
            elif tt_entry['flag'] == 'UPPERBOUND': # Stored score is an upper bound (beta)
                beta = min(beta, tt_entry['score'])
            
            if alpha >= beta: # Cutoff based on TT entry
                return tt_entry['score'], tt_entry.get('best_move')
            tt_move = tt_entry.get('best_move')


        # 2. Base Cases: Win/Loss/Draw or Max Depth Reached
        if last_move_coord:
            x, y = last_move_coord
            # The player who made `last_move_coord` is self.board[x][y]
            current_mover_val = self.board[x][y] 
            if self.check_win(x, y, current_mover_val):
                score = SCORE_WIN - ply_from_root if current_mover_val == PLAYER_AI else SCORE_LOSS + ply_from_root
                return score, None # No best move from a terminal state

        if depth == 0:
            return self.evaluate_board(), None

        candidate_moves = self.get_candidate_moves(last_player_made_move= (PLAYER_AI if is_maximizing_player else PLAYER_HUMAN))
        if not candidate_moves: # No moves left (draw)
            return 0, None
        
        # Order moves: TT move, killer moves, then others
        candidate_moves = self._order_moves(candidate_moves, ply_from_root, tt_move)

        best_move_for_this_node = None

        if is_maximizing_player: # AI's turn (Player 2)
            max_eval = -math.inf
            for r, c in candidate_moves:
                old_val = self.board[r][c] # Should be EMPTY
                self.board[r][c] = PLAYER_AI
                self._update_hash(r, c, old_val, PLAYER_AI)
                
                eval_score, _ = self.minimax(depth - 1, alpha, beta, False, ply_from_root + 1, (r,c))
                
                self.board[r][c] = old_val # Undo move
                self._update_hash(r, c, PLAYER_AI, old_val)
                
                if eval_score > max_eval:
                    max_eval = eval_score
                    best_move_for_this_node = (r,c)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    self._add_killer_move((r,c), ply_from_root) # This move caused a cutoff
                    break # Beta cut-off
            eval_to_return = max_eval
        else: # Player's turn (Player 1)
            min_eval = math.inf
            for r, c in candidate_moves:
                old_val = self.board[r][c] # Should be EMPTY
                self.board[r][c] = PLAYER_HUMAN
                self._update_hash(r, c, old_val, PLAYER_HUMAN)

                eval_score, _ = self.minimax(depth - 1, alpha, beta, True, ply_from_root + 1, (r,c))

                self.board[r][c] = old_val # Undo move
                self._update_hash(r, c, PLAYER_HUMAN, old_val)

                if eval_score < min_eval:
                    min_eval = eval_score
                    best_move_for_this_node = (r,c)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    self._add_killer_move((r,c), ply_from_root) # This move caused a cutoff
                    break # Alpha cut-off
            eval_to_return = min_eval

        # 3. Store result in Transposition Table
        flag_to_store = 'EXACT'
        if eval_to_return <= original_alpha: # Failed low, score is an upper bound for this node
            flag_to_store = 'UPPERBOUND'
        elif eval_to_return >= beta: # Failed high (for maximizer) or beta was updated (for minimizer), score is a lower bound
             flag_to_store = 'LOWERBOUND'
        
        self.transposition_table[self.current_hash] = {
            'depth': depth, 
            'score': eval_to_return, 
            'flag': flag_to_store,
            'best_move': best_move_for_this_node
        }
        return eval_to_return, best_move_for_this_node


    def ai_move(self):
        if self.winner != EMPTY:
            return None

        # --- Immediate win/block logic (depth 1 lookahead) ---
        candidate_moves = self.get_candidate_moves(last_player_made_move=PLAYER_HUMAN) # Human just moved
        if not candidate_moves: return None # No moves left

        # 1. Check for AI immediate win
        for r_idx, c_idx in candidate_moves:
            self.board[r_idx][c_idx] = PLAYER_AI
            # No hash update needed for this shallow check, it's temporary
            if self.check_win(r_idx, c_idx, PLAYER_AI):
                self.board[r_idx][c_idx] = EMPTY # Undo test
                print(f"AI found immediate win at ({r_idx},{c_idx})")
                self.place_piece(r_idx, c_idx, PLAYER_AI) # Make the actual move
                return (r_idx, c_idx)
            self.board[r_idx][c_idx] = EMPTY # Undo test

        # 2. Check for Player immediate win and block it
        best_block_move = None
        # Need to simulate player placing at each spot, then check if AI can block that spot
        for r_idx, c_idx in candidate_moves: # Iterate over where player *could* play
            self.board[r_idx][c_idx] = PLAYER_HUMAN # Simulate player move
            can_player_win = self.check_win(r_idx, c_idx, PLAYER_HUMAN)
            self.board[r_idx][c_idx] = EMPTY # Undo test player move

            if can_player_win:
                print(f"AI blocking player's win at ({r_idx},{c_idx})")
                self.place_piece(r_idx, c_idx, PLAYER_AI) # AI plays at that spot to block
                return (r_idx, c_idx)
        # --- End of immediate win/block logic ---

        # --- Iterative Deepening ---
        overall_best_move = None
        # If board is empty, place center (already handled by get_candidate_moves for first call)
        if all(self.board[r][c] == EMPTY for r in range(self.board_size) for c in range(self.board_size)):
            center_move = (self.board_size // 2, self.board_size // 2)
            print(f"AI (first move) plays center: {center_move}")
            self.place_piece(center_move[0], center_move[1], PLAYER_AI)
            return center_move

        start_time = time.time()
        # `search_depth` is the max depth for IDDFS
        for current_depth_limit in range(1, self.search_depth + 1):
            current_iter_best_score, current_iter_best_move = self.minimax(
                depth=current_depth_limit,
                alpha=-math.inf,
                beta=math.inf,
                is_maximizing_player=True, # AI's turn to decide
                ply_from_root=0,
                last_move_coord=None # No last move for the root of the search
            )
            
            if current_iter_best_move: # If a move was found at this depth
                overall_best_move = current_iter_best_move
                print(f"IDDFS Depth {current_depth_limit}: Best Move {overall_best_move}, Score {current_iter_best_score:.2f}")
            else: # No move found (e.g., only losing lines, or error)
                print(f"IDDFS Depth {current_depth_limit}: No best move found. Using previous or fallback.")
                if not overall_best_move and candidate_moves: # Fallback if no move ever found
                    overall_best_move = random.choice(candidate_moves)
                break # Stop deepening if no sensible move found

            # Optional: Time limit per iteration or total time
            # if time.time() - start_time > MAX_THINK_TIME_PER_MOVE:
            #     print("AI move time limit reached.")
            #     break
        
        end_time = time.time()
        print(f"AI search took {end_time - start_time:.3f} seconds.")

        if overall_best_move:
            print(f"AI final decision: plays at {overall_best_move}")
            self.place_piece(overall_best_move[0], overall_best_move[1], PLAYER_AI)
            return overall_best_move
        else: # Fallback if IDDFS somehow fails to find a move
             if candidate_moves:
                fallback_move = random.choice(candidate_moves)
                print(f"AI fallback: plays random candidate {fallback_move}")
                self.place_piece(fallback_move[0], fallback_move[1], PLAYER_AI)
                return fallback_move
             else: # Truly no moves left, should be a draw or game over
                print("AI: No moves left and no fallback.")
                return None


# Example Usage (for testing within this file):
if __name__ == '__main__':
    game = GomokuGame(board_size=15, search_depth=3) # Max IDDFS depth of 3 (1,2,3)

    # Scenario 1: AI plays first
    # game.current_player = PLAYER_AI # Let AI start
    # ai_best_move = game.ai_move()
    # if ai_best_move: print(f"AI moved to {ai_best_move}")

    # game.place_piece(7,6, PLAYER_HUMAN) # Human responds

    # ai_best_move = game.ai_move()
    # if ai_best_move: print(f"AI moved to {ai_best_move}")


    # Scenario 2: Human plays first
    game.place_piece(7, 7, PLAYER_HUMAN) # Player 1
    print("Human (P1) moved to (7,7)")
    for r in game.board: print(" ".join(map(str,r)))
    print("-" * 20)

    ai_best_move = game.ai_move() # AI (P2) responds
    if ai_best_move:
        print(f"AI (P2) moved to {ai_best_move}")
    else:
        print("AI could not move or game over.")
    for r in game.board: print(" ".join(map(str,r)))
    print("-" * 20)

    game.place_piece(7, 6, PLAYER_HUMAN) # Player 1
    print("Human (P1) moved to (7,6)")
    for r in game.board: print(" ".join(map(str,r)))
    print("-" * 20)
    
    ai_best_move = game.ai_move() # AI (P2) responds
    if ai_best_move:
        print(f"AI (P2) moved to {ai_best_move}")
    else:
        print("AI could not move or game over.")

    # Print board
    print("\nFinal Board State:")
    for row in game.board:
        # Replace numbers with symbols for readability
        print(" ".join(['.' if x==0 else 'X' if x==1 else 'O' for x in row]))

    if game.winner != EMPTY:
        print(f"Game Over! Winner is: Player {game.winner}")