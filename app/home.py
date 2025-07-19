from flask import Blueprint, request
from . import socketio
from judges.gomoku_judge import GomokuJudge
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
import uuid
import pymysql
from dotenv import load_dotenv
import datetime

load_dotenv()

home_bp = Blueprint('home', __name__)

sessions = {} 

def _get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )




def register_home_events(socketio):
    @socketio.on('connect', namespace='/')
    def handle_connect():
        user_id = str(uuid4())
        print(f'new home user connected: {user_id}')

        # Query matches table and send to user
        try:
            conn = _get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM matches ORDER BY created_at DESC LIMIT 20")
                matches = cursor.fetchall()
                # Convert datetime fields to string
                for match in matches:
                    for k, v in match.items():
                        if isinstance(v, datetime.datetime):
                            match[k] = v.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print("Failed to fetch matches:", e)
            matches = []
        finally:
            if conn:
                conn.close()
        # print(matches)
        emit('latest_matches', {"matches": matches})


