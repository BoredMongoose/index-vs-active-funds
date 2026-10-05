# Download daily NAVs for every large-cap direct-growth fund (plus the UTI Nifty 50 index fund) from api.mfapi.in
import json
import re
import os
import urllib.request

def get(url):
    return json.load(urllib.request.urlopen(url, timeout=60))

os.makedirs("data", exist_ok=True)
all_funds = get("https://api.mfapi.in/mf")

# Keep large-cap funds, direct plan, growth option; leave out mid-cap mixes, closed-end series and dividend options
funds = []
for f in all_funds:
    name = f["schemeName"]
    if (re.search(r"large\s*-?\s*cap|bluechip", name, re.I) and re.search(r"direct", name, re.I)
            and re.search(r"growth", name, re.I)
            and not re.search(r"mid|series|bonus|idcw|dividend|us |emerging|flexi|index|etf|fof|segregated", name, re.I)):
        funds.append(f["schemeCode"])
funds.append(120716)   # UTI Nifty 50 Index Fund - Direct - Growth, the benchmark

for code in funds:
    data = get(f"https://api.mfapi.in/mf/{code}")
    if data.get("data"):
        json.dump(data, open(f"data/{code}.json", "w"))
print("Saved", len(os.listdir("data")), "funds to data/")
