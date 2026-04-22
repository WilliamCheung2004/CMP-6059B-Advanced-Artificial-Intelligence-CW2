#delayPrediction.py - loads the trained delay prediction model and provides a function to predict arrival delay at London Waterloo based on current journey info

import joblib
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

#load saved model and encoder
model   = joblib.load(os.path.join(BASE_DIR, 'models', 'delay_model.joblib'))
encoder = joblib.load(os.path.join(BASE_DIR, 'models', 'station_encoder.joblib'))

def predict_arrival_delay(current_station: str, current_delay_mins: int, planned_dep_mins: int = 570, day_of_week: int = 1) -> dict:
    """
    Predicts the delay at London Waterloo given current journey info.

    Args:
        current_station:   3-letter station code e.g. 'SOU' for Southampton
        current_delay_mins: how many minutes late the train currently is
        planned_dep_mins:  planned departure in mins since midnight (default 570 = 9:30am)
        day_of_week:       0=Monday ... 6=Sunday

    Returns:
        dict with 'predicted_delay' in minutes and 'message' for the chatbot
    """
    #check station is known
    if current_station.upper() not in encoder.classes_:
        return {
            'predicted_delay': None,
            'message': f"Sorry, I don't recognise the station code '{current_station}'."
        }

    station_enc = encoder.transform([current_station.upper()])[0]

    X = pd.DataFrame([{
        'station_encoded':  station_enc,
        'current_delay':    current_delay_mins,
        'planned_dep_mins': planned_dep_mins,
        'day_of_week':      day_of_week
    }])

    predicted_delay = round(model.predict(X)[0], 1)

    #build a friendly chatbot message
    if predicted_delay <= 0:
        message = f"Good news! Despite the current delay, your train is predicted to arrive at London Waterloo on time or even slightly early."
    elif predicted_delay < 5:
        message = f"Your train is predicted to arrive at London Waterloo approximately {predicted_delay} minutes late."
    elif predicted_delay < 15:
        message = f"Your train is predicted to arrive at London Waterloo around {predicted_delay} minutes late. You may be entitled to Delay Repay compensation."
    else:
        message = f"Your train is predicted to arrive at London Waterloo around {predicted_delay} minutes late. You are likely entitled to Delay Repay compensation — visit the South Western Railway website to claim."

    return {
        'predicted_delay': predicted_delay,
        'message': message
    }


if __name__ == '__main__':
    #test with spec's exact scenario:
    # - train delayed 10 mins at Southampton, heading to London Waterloo
    print("\nTest 1: 10 min delay at Southampton (SOU)")
    result = predict_arrival_delay('SOU', 10)
    print(f"  Predicted delay at WAT: {result['predicted_delay']} mins")
    print(f"  Message: {result['message']}")
    print()

    print("Test 2: 30 min delay at Bournemouth (BMH)")
    result = predict_arrival_delay('BMH', 30)
    print(f"  Predicted delay at WAT: {result['predicted_delay']} mins")
    print(f"  Message: {result['message']}")
    print()

    print("Test 3: No delay at Winchester (WIN)")
    result = predict_arrival_delay('WIN', 0)
    print(f"  Predicted delay at WAT: {result['predicted_delay']} mins")
    print(f"  Message: {result['message']}")
    
    print("\n")