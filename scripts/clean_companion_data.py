import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
file_path = os.path.join(BASE_DIR, "data", "companion.csv")

df = pd.read_csv(file_path)

# Clean columns
df["Plant_A"] = df["Plant_A"].str.lower().str.strip()
df["Plant_B"] = df["Plant_B"].str.lower().str.strip()
df["Relationship"] = df["Relationship"].str.lower().str.strip()
df["Reason"] = df["Reason"].str.strip()

# Remove weird citations like [cite: 1]
df["Reason"] = df["Reason"].str.split("[").str[0]

# Drop duplicates
df = df.drop_duplicates()

print(df.head())


import json

result = {}

for _, row in df.iterrows():
    a = row["Plant_A"]
    b = row["Plant_B"]
    rel = row["Relationship"]
    reason = row["Reason"]

    # Ensure both plants exist
    for plant in [a, b]:
        if plant not in result:
            result[plant] = {
                "companions": [],
                "avoid": []
            }

    entry_ab = {"plant": b, "reason": reason}
    entry_ba = {"plant": a, "reason": reason}

    if rel == "companion":
        result[a]["companions"].append(entry_ab)
        result[b]["companions"].append(entry_ba)
    else:
        result[a]["avoid"].append(entry_ab)
        result[b]["avoid"].append(entry_ba)

def deduplicate(entries):
    seen = set()
    unique = []
    for item in entries:
        key = (item["plant"], item["reason"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique

for plant in result:
    result[plant]["companions"] = deduplicate(result[plant]["companions"])
    result[plant]["avoid"] = deduplicate(result[plant]["avoid"])

with open("data/companion_plants.json", "w") as f:
    json.dump(result, f, indent=2)