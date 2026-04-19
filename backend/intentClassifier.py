from genericpath import exists
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib
import os 


def train():
    texts = []  
    intents = []    

    df = pd.read_csv('IntentData.csv')
    texts = df['Text'].tolist()
    intents = df['Intent'].tolist()

    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(texts)

    model = LogisticRegression(max_iter=1000)
    model.fit(X, intents)

    #save in /models folder
    joblib.dump(vectorizer, 'models/vectorizer.joblib')
    joblib.dump(model, 'models/intent_model.joblib')

def classify_intent(text, vectorizer=None, model=None):
    
    if vectorizer is None or model is None:
        vectorizer = joblib.load('models/vectorizer.joblib')
        model = joblib.load('models/intent_model.joblib')

    X = vectorizer.transform([text])
    predicted_intent = model.predict(X)[0]
    confidence = model.predict_proba(X).max()
    return predicted_intent, confidence


if __name__ == '__main__':
    #Make sure models exist if not train them
    if not os.path.exists('models/vectorizer.joblib') or not os.path.exists('models/intent_model.joblib'):
        print("Couldn't find models, training...")
        train()

    #Use models
    else:
        print("Models found, testing classification...")
        vectorizer = joblib.load('models/vectorizer.joblib')
        model = joblib.load('models/intent_model.joblib')
        # Test classification
        test_texts = [
            "I want to book a ticket from Norwich to London tomorrow",
            "Find me a ticket 24/10/2026",
            "I want to travel on Friday",
            "I want to travel next Friday",
            "I want to travel on the 5th",
            "I want to travel on 24th January",
            "I want to travel yesterday",
            "Can I get a ticket from Colchester to Norwich on the 25th March?",
        ]

        for text in test_texts:
            intent, confidence = classify_intent(text, vectorizer, model)
            print(f"Text: '{text}'")
            print(f"  Predicted Intent: {intent} (Confidence: {confidence:.2f})")
            print()
