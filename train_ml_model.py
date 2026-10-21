import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib

print("Loading synthetic data...")
df = pd.read_csv('synthetic_momo_transactions.csv')

# 1. Feature Engineering (Turning raw data into ML features)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['hour_of_day'] = df['timestamp'].dt.hour
df['is_night_transaction'] = (df['hour_of_day'] >= 22) | (df['hour_of_day'] <= 5)
df['is_high_value'] = df['amount'] > 1000

# 2. Define Target (0 = Normal, 1 = Fraud)
df['is_fraud'] = df['fraud_type'].apply(lambda x: 0 if x == 'NONE' else 1)

# 3. Select Features for the model
features = ['amount', 'hour_of_day', 'is_night_transaction', 'is_high_value']
X = df[features]
y = df['is_fraud']

# 4. Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("Training XGBoost Fraud Detection Model...")
# Initialize XGBoost (tuned for fraud detection which is imbalanced)
model = XGBClassifier(
    n_estimators=100, 
    max_depth=3, 
    learning_rate=0.1, 
    scale_pos_weight=len(y[y==0])/len(y[y==1]), # Handles imbalanced data
    use_label_encoder=False, 
    eval_metric='logloss'
)

model.fit(X_train, y_train)

# 5. Evaluate
y_pred = model.predict(X_test)
print(f"Model Accuracy: {accuracy_score(y_test, y_pred) * 100:.2f}%")
print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=['Normal', 'Fraud']))

# 6. Save the model
joblib.dump(model, 'fraud_ml_model.pkl')
print("✅ Model trained and saved as 'fraud_ml_model.pkl'")