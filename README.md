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

5. Download the spaCy English language model:
    python -m spacy download en_core_web_sm

6. Verify it loaded correctly (optional):
    python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('loaded')"

7. Run delayModel.py then run intent.py to create the necessary models to run TrainBot

8. Then run the app.py file to run the backend.
    - if the terminal returns an error saying "No such file or directory: 'stations.csv'", just redo the change directory to the backend (cd backend) and run app.py again

9. Make a new terminal window and change directory to the frontend folder:
    cd my-react-app

10. Install any dependencies:
    npm install

11. Run the frontend:
    npm run dev

12. Open the local host website from the link provided (e.g. http://localhost:5173)