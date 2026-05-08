import pandas as pd
import numpy as np
import joblib
import os

from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer


def train():
    df = pd.read_csv('IntentData.csv')

    texts = df['Text'].tolist()
    intents = df['Intent'].tolist()


    encoder = SentenceTransformer('all-MiniLM-L6-v2')

    X = encoder.encode(texts, normalize_embeddings=True)

    intent_map = {}

    for i, intent in enumerate(intents):
        if intent not in intent_map:
            intent_map[intent] = []
        intent_map[intent].append(X[i])

    intent_vectors = []
    intent_labels = []

    for intent, vecs in intent_map.items():
        centroid = np.mean(vecs, axis=0)
        intent_vectors.append(centroid)
        intent_labels.append(intent)

    intent_vectors = np.array(intent_vectors)


    os.makedirs("models", exist_ok=True)

    joblib.dump(encoder, "models/encoder.joblib")
    joblib.dump(intent_vectors, "models/intent_vectors.joblib")
    joblib.dump(intent_labels, "models/intent_labels.joblib")



def classify_intent(text, encoder=None, intent_vectors=None, intent_labels=None):

    if encoder is None:
        encoder = joblib.load("models/encoder.joblib")
        intent_vectors = joblib.load("models/intent_vectors.joblib")
        intent_labels = joblib.load("models/intent_labels.joblib")

    q = encoder.encode([text], normalize_embeddings=True)[0]

    scores = cosine_similarity([q], intent_vectors)[0]

    idx = np.argmax(scores)
    confidence = scores[idx]
    intent = intent_labels[idx]

    return intent, confidence

if __name__ == '__main__':

    if not os.path.exists('models/encoder.joblib'):
        print("Training model...")
        train()

    encoder = joblib.load("models/encoder.joblib")
    intent_vectors = joblib.load("models/intent_vectors.joblib")
    intent_labels = joblib.load("models/intent_labels.joblib")

    test_texts = [
        "I want to book a ticket from Norwich to London tomorrow",
        "Find me a train 24/10/2026",
        "I need to travel next Friday",
        "Is my train delayed right now?",
        "What platform does the train leave from?",
        "yo I need a ride to London",
        "can I go to cambridge tomorrow morning"
    ]

    for text in test_texts:
        intent, confidence = classify_intent(
            text,
            encoder,
            intent_vectors,
            intent_labels
        )

        print(f"Text: {text}")
        print(f"Intent: {intent} | Confidence: {confidence:.2f}\n")