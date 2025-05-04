import pandas as pd
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

# Load dataset
df = pd.read_csv("diseases.csv")

# Prepare data: Combine diagnosis and symptoms as features
df['features'] = df['Kasallik nomi'] + " " + df['Belgilar']
X = df['features']
y = df['Tavsiya etilgan dorilar'].str.split(',').explode().str.strip()

# Create a binary classification dataset
data = []
labels = []
for idx, row in df.iterrows():
    diagnosis = row['features']
    recommended_meds = [med.strip() for med in row['Tavsiya etilgan dorilar'].split(',')]
    all_meds = set(df['Tavsiya etilgan dorilar'].str.split(',').explode().str.strip())
    for med in all_meds:
        data.append(diagnosis + " " + med)
        labels.append(1 if med in recommended_meds else 0)

# Vectorize and train
pipeline = Pipeline([
    ('tfidf', TfidfVectorizer()),
    ('clf', RandomForestClassifier(n_estimators=100, random_state=42))
])
X_train, X_test, y_train, y_test = train_test_split(data, labels, test_size=0.2, random_state=42)
pipeline.fit(X_train, y_train)

# Save the model
with open('medication_model.pkl', 'wb') as f:
    pickle.dump(pipeline, f)

# Print accuracy on test set
print(f"Model accuracy: {pipeline.score(X_test, y_test) * 100:.2f}%")