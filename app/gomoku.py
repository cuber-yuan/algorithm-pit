from flask import Blueprint, request
from . import socketio
from .gomoku_judge import GomokuJudge
from uuid import uuid4
from flask_socketio import emit, join_room
import sys
import json
import io
from unittest.mock import patch
import contextlib
import subprocess
import tempfile
import os
from .code_executor import CodeExecutor

gomoku_bp = Blueprint('gomoku', __name__)

sessions = {}

def register_gomoku_events(socketio):
    @socketio.on('connect', namespace='/gomoku')
    def handle_connect():
        user_id = str(uuid4())
        sessions[user_id] = GomokuJudge()
        # 初始化 executor
        # sessions[user_id].executor = CodeExecutor()
        join_room(request.sid)
        emit('init', {
            'user_id': user_id,
            'board': sessions[user_id].board
        }, room=request.sid)
        print(f'new gomoku user connected: {user_id}')
        

    @socketio.on('player_move', namespace='/gomoku')
    def handle_player_move(data):
        user_id = data['user_id']
        x, y = data['x'], data['y']
        game = sessions.get(user_id)
        sid = request.sid

        if not game:
            emit('error', {'message': 'Invalid user_id'})
            return

        # 新增：如果已經有勝者，不允許再落子
        if hasattr(game, 'winner') and game.winner:
            emit('error', {'message': 'Game over'})
            return

        if game.current_player != 1:
            emit('error', {'message': 'Not your turn'})
            return

        game.apply_move(x, y)

        # 判斷勝負
        winner = game.check_win(x, y)
        if winner != 0:
            game.winner = winner  # 記錄勝者

        response = {
            'board': game.board,
            'move': {'x': x, 'y': y, 'player': 1}
        }
        if winner != 0:
            response['winner'] = winner

        emit('update', response)

        if winner != 0:
            return  # 有勝者就不再讓AI落子

        
        input_str = game.send_action_to_ai()
        
        print("input_str IS :", input_str)
        
        output = game.executor.run(input_str)
        

        if output:
            try:
                move_data = json.loads(output)
                ai_x = move_data['x']
                ai_y = move_data['y']
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                print(f"Raw output: {repr(output)}")
                ai_x, ai_y = 0, 0
        else:
            print("No output from bot!")
            ai_x, ai_y = 0, 0

        print("===DEBUG===", output)
        print(f'AI move: {ai_x}, {ai_y}')
        game.apply_move(ai_x, ai_y)

        # 新增：判断AI落子后的胜负
        ai_winner = game.check_win(ai_x, ai_y)
        ai_response = {
            'board': game.board,
            'ai_move': {'x': ai_x, 'y': ai_y, 'player': 2}
        }
        if ai_winner != 0:
            game.winner = ai_winner
            ai_response['winner'] = ai_winner

        emit('update', ai_response, room=sid)


    @socketio.on('new_game', namespace='/gomoku')
    def new_game(data):
        user_id = data['user_id']
        game = sessions.get(user_id)
        if not game:
            emit('error', {'message': 'Invalid user_id'})
            return

        black_bot_id = data.get('black_bot')
        white_bot_id = data.get('white_bot')
        
        
        
        import pymysql
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        conn = pymysql.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        
        
        
        # if black_bot_id:
        #     cursor.execute("SELECT bot_code FROM bots WHERE id = %s", (black_bot_id,))
        #     result = cursor.fetchone()
        #     if result:
        #         black_bot_code = result[0]
        
        if white_bot_id:
            cursor.execute("SELECT source_code FROM bots WHERE id = %s", (white_bot_id,))
            result = cursor.fetchone()
            if result:
                game.white_bot_code = result[0]
                game.executor = CodeExecutor(
                    code=sessions[user_id].white_bot_code)
        conn.close()
        
        # 将bot代码传递给游戏实例
        #game.new_game(black_bot_code=black_bot_code, white_bot_code=white_bot_code)
        game.new_game()
        response = {
            'board': game.board,
        }
        emit('update', response)

    @socketio.on('disconnect', namespace='/gomoku')
    def handle_disconnect():
        for user_id, game in list(sessions.items()):
            if game.sid == request.sid:
                del sessions[user_id]
                print(f'User {user_id} disconnected and session cleaned up')
                break