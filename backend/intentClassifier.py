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
        train()

    #Use models
    else:
        vectorizer = joblib.load('models/vectorizer.joblib')
        model = joblib.load('models/intent_model.joblib')
