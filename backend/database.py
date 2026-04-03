import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'chatbot.db')

def get_db_connection():
    """Returns a connection to the SQLite database"""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initialises the database with necessary tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    #create conversations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_input TEXT NOT NULL,
            bot_response TEXT NOT NULL,
            intent TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    #journey table to store user journeys
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journeys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            travel_date TEXT NOT NULL,
            return_date TEXT,
            ticket_type TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    
def save_message(session_id: str, user_input: str, bot_response: str, intent: str = None): 
    """Saves a conversation message to the database"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO conversations (session_id, user_input, bot_response, intent)
        VALUES (?, ?, ?, ?)
    ''', (session_id, user_input, bot_response, intent))
                   
    conn.commit()
    conn.close()
    
def save_journey(session_id: str, origin: str, destination: str, 
                 travel_date: str, return_date: str = None, ticket_type: str = None):
    """Saves a user journey to the database"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO journeys (session_id, origin, destination, travel_date, return_date, ticket_type)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (session_id, origin, destination, travel_date, return_date, ticket_type))
                   
    conn.commit()
    conn.close()
    
def get_conversation_history(session_id: str) -> list:
    """Retrieves conversation history for a given session ID"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_input, bot_response, intent, timestamp
        FROM conversations
        WHERE session_id = ?
        ORDER BY timestamp ASC
    ''', (session_id,))
    
    history = cursor.fetchall()
    conn.close()
    
    return history

if __name__ == '__main__':
    init_db()
    print("\nDatabase initialised!\n")
    
    save_message('session123', 'What is the cheapest ticket to Norwich?', 'The cheapest ticket to Norwich is...', 'ticket_query')
    save_message('session123', 'Can I get a railcard discount?', 'Yes, you can get a railcard discount if you have a valid railcard.', 'railcard_query')
    save_message('session123', 'My train is delayed, what are my options?', 'If your train is delayed, you can claim compensation or rebook on a later train.', 'delay_query')
    save_journey('session123', 'Cambridge', 'Norwich', '2024-07-01', '2024-07-02', 'return')
    
    conv_history = get_conversation_history('session123')
    
    print("Conversation history for session123:\n")
    for msg in conv_history:
        print(f"User: {msg[0]}\nBot: {msg[1]}\nIntent: {msg[2]}\nTimestamp: {msg[3]}\n")