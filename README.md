# CMP-6059B-Advanced-Artificial-Intelligence-CW2
Chatbot for Train Tickets

## -------- Instruction for how to Setup and Run --------
How to run in terminal:

1. Download Ollama LLM, model mistral:7b from this link:
    https://ollama.com/library/mistral:7b

2. Run the mistral:7b Ollama model in the background to enable LLM functionality.

3. Install dependencies (Requires Python 3.9.6 or higher):
    pip install -r requirements.txt

4. Change directory to the backend folder:
    cd backend

5. Load the spaCy English language model (in terminal):
    python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('loaded')"

6. Then run the app.py file to run the backend.

7. Make a new terminal window and change directory to the frontend folder:
    cd my-react-app

8. Install any dependencies:
    npm install

9. Run the frontend:
    npm run dev

10. Open the local host website from the link provided (e.g. http://localhost:5173)