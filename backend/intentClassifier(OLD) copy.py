import pandas as pd
import numpy as np
import joblib
import os

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def train():
    df = pd.read_csv('IntentData.csv')

    texts = df['Text'].tolist()
    intents = df['Intent'].tolist()

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 3),
        lowercase=True
    )

    X = vectorizer.fit_transform(texts)

    joblib.dump(vectorizer, 'models/vectorizer.joblib')
    joblib.dump(X, 'models/X.joblib')
    joblib.dump(intents, 'models/intents.joblib')


def classify_intent(text, vectorizer=None, X=None, intents=None):

    if vectorizer is None or X is None or intents is None:
        vectorizer = joblib.load('models/vectorizer.joblib')
        X = joblib.load('models/X.joblib')
        intents = joblib.load('models/intents.joblib')

    q = vectorizer.transform([text])

    scores = cosine_similarity(q, X)[0]

    idx = np.argmax(scores)
    confidence = scores[idx]
    intent = intents[idx]

    return intent, confidence


if __name__ == '__main__':

    if not os.path.exists('models/vectorizer.joblib'):
        print("Training model...")
        os.makedirs("models", exist_ok=True)
        train()

    vectorizer = joblib.load('models/vectorizer.joblib')
    X = joblib.load('models/X.joblib')
    intents = joblib.load('models/intents.joblib')

    test_texts = [
        "I want to book a ticket from Norwich to London tomorrow",
        "Find me a ticket 24/10/2026",
        "I want to travel on Friday",
        "I want to travel next Friday",
        "I want to travel on the 5th",
        "Can I get a train to Cambridge tomorrow?",
        "Is my train delayed right now?",
        "What platform does the train leave from?"
    ]

    for text in test_texts:
        intent, confidence = classify_intent(text, vectorizer, X, intents)
        print(f"Text: {text}")
        print(f"Intent: {intent} | Confidence: {confidence:.2f}\n")