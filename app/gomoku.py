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

gomoku_bp = Blueprint('gomoku', __name__)

sessions = {}

def register_gomoku_events(socketio):
    @socketio.on('connect', namespace='/gomoku')
    def handle_connect():
        user_id = str(uuid4())
        sessions[user_id] = GomokuJudge()
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

        

        game.apply_move(x, y)  
        
        response = {
            'board': game.board,
            'move': {'x': x, 'y': y, 'player': 1}
        }
        if game.check_win(x, y) != 0:
            response['winner'] = game.check_win(x, y)

        emit('update', response)
        

        
        input_str = game.send_action_to_ai()
        
        print("input_str IS :", input_str)

        try:
            # 调用 gomoku_ai.py，传递 input_str 给 stdin
            # 写入临时文件
            with tempfile.NamedTemporaryFile('w', delete=False, suffix='.py') as tmpfile:
                tmpfile.write(game.white_bot_code)
                tmpfile_path = tmpfile.name

            # 用 subprocess 运行临时文件
            result = subprocess.run(
                ['python', tmpfile_path],
                input=input_str.encode('utf-8'),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10
            )
            # 删除临时文件
            os.unlink(tmpfile_path)
            output = result.stdout.decode('utf-8').strip()
            print("===AI STDOUT===", output)
            if result.stderr:
                print("===AI STDERR===", result.stderr.decode('utf-8'))
        except Exception as e:
            print(f"Subprocess error: {e}")
            output = ''

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
        emit('update', {
            'board': game.board,
            'ai_move': {'x': ai_x, 'y': ai_y, 'player': 2}
        }, room=sid)


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