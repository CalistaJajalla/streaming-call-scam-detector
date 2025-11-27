import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import train_test_split
import joblib

def generate_synthetic_data(n_samples=5000, random_seed=42):
    np.random.seed(random_seed)
    call_duration = np.random.exponential(scale=60, size=n_samples)
    num_digits = np.random.choice([7,10,11,12], size=n_samples, p=[0.2, 0.5, 0.2, 0.1])
    hour_of_day = np.random.randint(0, 24, size=n_samples)
    freq_calls = np.random.poisson(2, size=n_samples)

    # Labeling logic (probabilistic)
    prob_scam = (
        (call_duration < 40).astype(float) * 0.4 +
        ((hour_of_day < 6) | (hour_of_day > 22)).astype(float) * 0.3 +
        (freq_calls > 3).astype(float) * 0.3 +
        (num_digits == 11).astype(float) * 0.1
    )
    prob_scam = np.clip(prob_scam, 0, 0.95)
    labels = (np.random.rand(n_samples) < prob_scam).astype(int)

    return pd.DataFrame({
        "call_duration": call_duration,
        "num_digits": num_digits,
        "hour_of_day": hour_of_day,
        "freq_calls": freq_calls,
        "label": labels,
    })

def train_and_save_model(df, filename="knn_model.joblib"):
    X = df[["call_duration", "num_digits", "hour_of_day", "freq_calls"]]
    y = df["label"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=5))
    pipeline.fit(X_train, y_train)
    accuracy = pipeline.score(X_test, y_test)
    print(f"Test accuracy: {accuracy:.4f}")
    joblib.dump(pipeline, filename)
    print(f"Model saved to {filename}")

if __name__ == "__main__":
    data = generate_synthetic_data()
    train_and_save_model(data)
