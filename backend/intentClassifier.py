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


if __name__ == '__main__':
    #Make sure models exist if not train them
    if not os.path.exists('models/vectorizer.joblib') or not os.path.exists('models/intent_model.joblib'):
        train()

    #Use models
    else:
        vectorizer = joblib.load('models/vectorizer.joblib')
        model = joblib.load('models/intent_model.joblib')

        X_test = vectorizer.transform([" book ."])
        predicted_intent = model.predict(X_test)[0]
        probability = model.predict_proba(X_test).max()
        best_guess = model.predict(X_test)[0]

        if probability < 0.5:
            print(f"Do you want to {predicted_intent}?")
        print(f"Predicted Intent: {predicted_intent} (Confidence: {probability:.2f})")

