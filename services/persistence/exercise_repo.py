import sqlite3
import streamlit as st
from pathlib import Path

_Db_PPATH=(Path(__file__).parent.parent.parent/"data.db")

def _get_connection():
    conn=sqlite3.connect(str(_Db_PPATH),check_same_thread=False) # check_same_thread=False allows multiple threads to access the database
    conn.row_factory=sqlite3.Row # This allows us to access columns by name
    return conn

def init_db():
    conn=_get_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                Created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exercise(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                exercise_name TEXT NOT NULL,
                sets INTEGER NOT NULL DEFAULT 0,
                reps INTEGER NOT NULL DEFAULT 0,
                time INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                
            )            
        """)
        
def get_user(username):
    conn=_get_connection()
    
    return conn.execute("""
        SELECT * FROM users WHERE username = ?                   
    """,(username,)).fetchone()
    
def create_user(username):
    conn=_get_connection()
    with conn:
        conn.execute("""
            INSERT INTO users(username) values(?)                     
    """,(username,))
        
def get_or_create_user(username):
    user=get_user(username)
    if user is None:
        create_user(username)
        user = get_user(username)
    return user
        
def add_exercise(user_id,exercise_name,reps,sets,time):
    conn=_get_connection()
    
    with conn:
        existing=conn.execute("""
            SELECT * FROM exercise 
            WHERE user_id=? And exercise_name=? AND Date(created_at)=Date('now')            
        """,(user_id,exercise_name)).fetchone()
        
        if existing:
            conn.execute("""
                UPDATE exercise 
                SET reps=reps+?, sets=sets+?, time=time+?
                WHERE id=?
            """,(reps,sets,time,existing['id']))
        else:
            conn.execute("""
                INSERT INTO exercise (user_id,exercise_name,sets,reps,time)
                VALUES(?,?,?,?,?)
            """,(user_id,exercise_name,sets,reps,time))


def get_users_exercises(user_id):
    conn=_get_connection()
    
    return conn.execute("""
        SELECT * FROM exercise WHERE user_id=?
    """,(user_id,)).fetchall()


# kept for backward compatibility with the old name
get_user_exercise = get_users_exercises