from flask import Flask, request, jsonify
from flask_cors import CORS
from reasoningEngine import process_user_input
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

    return jsonify({
        'reply': reply,
        'options': [],
        'tickets': [],
        'context': {
            'title': 'TrainBot',
            'subtitle': ''
        }
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)