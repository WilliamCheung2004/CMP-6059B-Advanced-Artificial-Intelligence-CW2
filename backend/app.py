from flask import Flask, request, jsonify
from flask_cors import CORS
from reasoningEngine import process_user_input, reset_all_states
from database import init_db

app = Flask(__name__)
CORS(app)

init_db()

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')

    try: 
        reply = process_user_input(user_message)
    except Exception as e:
        print(f"Error processing the message: {e}")
        reply = "Something went wrong, try again."

    tickets = []
    post_message = ""
    
    if isinstance(reply, tuple):
        if len(reply) == 4:
            reply_text = reply[0]
            ticket_data = reply[2]
            post_message = reply[3]
            if isinstance(ticket_data, list):
                tickets = ticket_data
            elif isinstance(ticket_data, dict):
                tickets = [ticket_data]
            reply = reply_text if reply_text else ""
        elif len(reply) == 3:
            reply_text = reply[0]
            ticket_data = reply[2]
            if isinstance(ticket_data, list):
                tickets = ticket_data
            elif isinstance(ticket_data, dict):
                tickets = [ticket_data]
            reply = reply_text if reply_text else ""
    
    return jsonify({
        'reply': reply,
        'postMessage': post_message,
        'options': [],
        'tickets': tickets,
        'context': {
            'title': 'TrainBot',
            'subtitle': ''
        }
    })

@app.route('/restart', methods=['POST'])
def restart_conversation():
    data = request.get_json()
    old_session_id = data.get('old_session_id')
    new_session_id = data.get('new_session_id')

    reset_all_states()

    return jsonify({
        'status': 'success',
        'message': 'Conversation restarted',
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)