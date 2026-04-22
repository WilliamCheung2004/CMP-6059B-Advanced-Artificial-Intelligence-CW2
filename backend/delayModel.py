#delayModel.py - trains a model to predict arrival delay at London Waterloo based on historical data

#some dependencies may need to be installed via pip:
#pip install openpyxl

import pandas as pd
import numpy as np
from sklearn.neighbors import KNeighborsRegressor
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_DATA_DIR = os.path.join(BASE_DIR, 'train-data')

#load all years of data
print("\nLoading data...\n")
dfs = []
data_files = [
    '2022_service_details.xlsx',
    '2023.xlsx',
    '2024.xlsx',
    '2025.xlsx'
]
for f in data_files:
    path = os.path.join(TRAIN_DATA_DIR, f)
    print(f"  Loading {f}...")
    df = pd.read_excel(path)
    dfs.append(df)

df = pd.concat(dfs, ignore_index=True)
print(f"\nTotal rows loaded: {len(df)}")

#convert times to minutes since midnight
def to_minutes(t):
    if pd.isnull(t): return np.nan
    if hasattr(t, 'hour'): return t.hour * 60 + t.minute
    return np.nan

for col in ['planned_arrival_time', 'actual_arrival_time',
            'planned_departure_time', 'actual_departure_time']:
    df[col + '_mins'] = df[col].apply(to_minutes)

df['arrival_delay'] = df['actual_arrival_time_mins'] - df['planned_arrival_time_mins']

#build training dataset
print("\nBuilding training dataset...")
records = []

for rid, group in df.groupby('rid'):
    group = group.reset_index(drop=True)

    #need a WAT (London Waterloo) row to use as the target
    wat_row = group[group['location'] == 'WAT']
    if wat_row.empty:
        continue

    wat_delay = wat_row['arrival_delay'].values[0]
    if pd.isnull(wat_delay):
        continue

    #remove extreme outliers e.g. overnight delays
    if abs(wat_delay) > 120:
        continue

    for _, row in group.iterrows():
        if row['location'] == 'WAT':
            continue
        if pd.isnull(row['arrival_delay']):
            continue

        records.append({
            'current_station':  row['location'],
            'current_delay':    row['arrival_delay'],
            'planned_dep_mins': row['planned_departure_time_mins'] if not pd.isnull(row['planned_departure_time_mins']) else 0,
            'day_of_week':      pd.Timestamp(row['date_of_service']).dayofweek,
            'wat_delay':        wat_delay
        })

train_df = pd.DataFrame(records)
print(f"Training samples: {len(train_df)}")

#encode station names as numbers
le = LabelEncoder()
train_df['station_encoded'] = le.fit_transform(train_df['current_station'])

#features and target
X = train_df[['station_encoded', 'current_delay', 'planned_dep_mins', 'day_of_week']]
y = train_df['wat_delay']

#train/validation/test split (70% train, 15% validation, 15% test)
X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.1765, random_state=42)
# 0.1765 of 85% ≈ 15% of total

print(f"\nTrain size: {len(X_train)}")
print(f"Validation size: {len(X_val)}")
print(f"Test size: {len(X_test)}")

#train and evaluate models on validation set
print("\n--- Model Comparison (Validation Set) ---")

models = {
    'kNN (k=5)':         KNeighborsRegressor(n_neighbors=5),
    'kNN (k=10)':        KNeighborsRegressor(n_neighbors=10),
    'Linear Regression': LinearRegression(),
    'MLP':               Pipeline([('scaler', StandardScaler()), ('mlp', MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=500, random_state=42))]),
}

results = {}
for name, model in models.items():
    print(f"  Training {name}...")
    model.fit(X_train, y_train)

    #evaluate on validation set to compare models
    val_preds = model.predict(X_val)
    val_mae   = mean_absolute_error(y_val, val_preds)
    val_rmse  = mean_squared_error(y_val, val_preds) ** 0.5
    results[name] = {'model': model, 'val_mae': val_mae, 'val_rmse': val_rmse}
    print(f"  {name:25s} | Val MAE: {val_mae:.2f} mins | Val RMSE: {val_rmse:.2f} mins")

#pick best model using validation MAE
best_name = min(results, key=lambda k: results[k]['val_mae'])
best_model = results[best_name]['model']
print(f"\nBest model: {best_name}")
print(f"  Val MAE:  {results[best_name]['val_mae']:.2f} mins")
print(f"  Val RMSE: {results[best_name]['val_rmse']:.2f} mins")

#final evaluation on test set - only done once with the best model
print("\n--- Final Evaluation (Test Set) ---")
test_preds = best_model.predict(X_test)
test_mae   = mean_absolute_error(y_test, test_preds)
test_rmse  = mean_squared_error(y_test, test_preds) ** 0.5
print(f"{best_name:25s} | Test MAE: {test_mae:.2f} mins | Test RMSE: {test_rmse:.2f} mins")

#save best model and encoder
models_dir = os.path.join(BASE_DIR, 'models')
os.makedirs(models_dir, exist_ok=True)

joblib.dump(best_model, os.path.join(models_dir, 'delay_model.joblib'))
joblib.dump(le, os.path.join(models_dir, 'station_encoder.joblib'))
print(f"\nSaved: models/delay_model.joblib")
print(f"Saved: models/station_encoder.joblib")

#sanity check using spec's exact scenario
print("\n--- Sanity Check (spec scenario) ---\n")
print("Train delayed 10 mins at Southampton, heading to London Waterloo\n")

def predict_wat_delay(current_station: str, current_delay_mins: int, planned_dep_mins: int = 570, day_of_week: int = 1):
    if current_station.upper() not in le.classes_:
        return None, f"Station '{current_station}' not recognised"
    station_enc = le.transform([current_station.upper()])[0]
    X_pred = pd.DataFrame([{
        'station_encoded':  station_enc,
        'current_delay':    current_delay_mins,
        'planned_dep_mins': planned_dep_mins,
        'day_of_week':      day_of_week
    }])
    return round(best_model.predict(X_pred)[0], 1), None

delay, err = predict_wat_delay('SOU', 10)
if err:
    print(f"Error: {err}")
else:
    print(f"Predicted delay at London Waterloo: {delay} minutes")
    
print("\n")