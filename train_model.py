import pandas as pd
import joblib

from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
import pandas as pd

# load original SMS spam dataset
df1 = pd.read_csv("spam.csv", encoding="latin-1")

df1 = df1[['v1','v2']]
df1.columns = ["label","text"]

# load multilingual dataset
df2 = pd.read_csv("multilingual_fraud_dataset.csv")

# merge both datasets
df = pd.concat([df1, df2])

# save final dataset
df.to_csv("dataset.csv", index=False)

print("Dataset merged successfully")

X = df["text"]
y = df["label"]

pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3,5),
        max_features=10000
    )),
    ("clf", LogisticRegression(max_iter=1000))
])

pipeline.fit(X,y)

joblib.dump(pipeline,"model.pkl")

print("Model trained and saved")