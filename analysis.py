# Do active large-cap funds in India beat a cheap Nifty 50 index fund?
# Data: daily NAVs (direct plans, growth option) from api.mfapi.in, saved in data/ by fetch_data.py
import json
import glob
import pandas as pd
import matplotlib.pyplot as plt

INDEX_CODE = 120716          # UTI Nifty 50 Index Fund - Direct - Growth (our "market" benchmark)
START = "2013-01-02"         # direct plans started in January 2013

# ---- 1. Load every fund into one table of daily NAVs ----
navs = {}
names = {}
for path in glob.glob("data/*.json"):
    raw = json.load(open(path))
    code = int(raw["meta"]["scheme_code"])
    df = pd.DataFrame(raw["data"])
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    navs[code] = df.set_index("date")["nav"].sort_index()
    names[code] = raw["meta"]["scheme_name"].replace("UTI - Large", "UTI Large").split(" - ")[0].split("-Direct")[0].strip()

# ---- 2. Data-integrity checks ----
checks = []
last_day = max(s.index.max() for s in navs.values())
for code, s in navs.items():
    checks.append({
        "fund": names[code],
        "first_date": s.index.min().date(),
        "last_date": s.index.max().date(),
        "missing_navs": int(s.isna().sum()),
        "zero_or_negative": int((s <= 0).sum()),
        "duplicate_dates": int(s.index.duplicated().sum()),
        "daily_moves_over_15pct": int((s.pct_change().abs() > 0.15).sum()),
        "still_running": s.index.max() >= last_day - pd.Timedelta(days=10),
    })
checks = pd.DataFrame(checks).sort_values("first_date")
checks.to_csv("output/data_checks.csv", index=False)
print("Funds loaded:", len(checks))
print("Missing NAVs:", checks["missing_navs"].sum(), "| zero/negative:", checks["zero_or_negative"].sum(),
      "| duplicate dates:", checks["duplicate_dates"].sum(), "| daily moves over 15%:", checks["daily_moves_over_15pct"].sum())

# Fix found by the checks: one Axis NAV of 0.0 on a Sunday (2013-04-07) is a data-entry error, so drop NAVs of 0
for code in navs:
    navs[code] = navs[code][navs[code] > 0]

# ---- 3. Keep funds with the full history (2013 to today) so everyone is compared over the same years ----
full = checks[(pd.to_datetime(checks["first_date"]) <= pd.Timestamp("2013-01-10")) & checks["still_running"]]
codes = [c for c in navs if names[c] in set(full["fund"])]
closed = checks[~checks["still_running"]]
print("Funds with full history:", len(codes), "(including the index fund)")
print("Funds that closed or merged since 2013:", len(closed))

prices = pd.DataFrame({c: navs[c] for c in codes}).loc[START:].ffill().dropna()
returns = prices.pct_change().dropna()
years = (prices.index[-1] - prices.index[0]).days / 365.25

# ---- 4. Full-period scorecard: return, risk, Sharpe, worst fall ----
RISK_FREE = 0.065           # rough average Indian 1-year T-bill yield over the period
rows = []
for c in codes:
    cagr = (prices[c].iloc[-1] / prices[c].iloc[0]) ** (1 / years) - 1
    vol = returns[c].std() * 252 ** 0.5
    drawdown = (prices[c] / prices[c].cummax() - 1).min()
    rows.append({"fund": names[c], "index_fund": c == INDEX_CODE, "cagr_pct": round(cagr * 100, 2),
                 "volatility_pct": round(vol * 100, 2), "sharpe": round((cagr - RISK_FREE) / vol, 2),
                 "max_drawdown_pct": round(drawdown * 100, 1)})
score = pd.DataFrame(rows).sort_values("cagr_pct", ascending=False)
score.to_csv("output/scorecard.csv", index=False)
index_cagr = score.loc[score["index_fund"], "cagr_pct"].iloc[0]
active = score[~score["index_fund"]]
beat = (active["cagr_pct"] > index_cagr).sum()
print(f"\nPeriod: {prices.index[0].date()} to {prices.index[-1].date()} ({years:.1f} years)")
print(f"Nifty 50 index fund CAGR: {index_cagr}%")
print(f"Active funds beating it: {beat} of {len(active)}")
print(score.to_string(index=False))

# ---- 5. Rolling 3-year returns: how often does each active fund beat the index? ----
WINDOW = 252 * 3
rolling = (prices / prices.shift(WINDOW)) ** (1 / 3) - 1
rolling = rolling.dropna()
win_rate = {names[c]: (rolling[c] > rolling[INDEX_CODE]).mean() * 100 for c in codes if c != INDEX_CODE}
win_rate = pd.Series(win_rate).sort_values()
win_rate.round(1).to_csv("output/rolling_3y_win_rate.csv", header=["pct_of_3y_windows_beating_index"])
share_of_funds_ahead = (rolling.drop(columns=INDEX_CODE).gt(rolling[INDEX_CODE], axis=0)).mean(axis=1) * 100
print(f"\nMedian active fund beat the index in {win_rate.median():.0f}% of rolling 3-year windows")
print(f"On a typical day, {share_of_funds_ahead.median():.0f}% of active funds were ahead over the past 3 years")

# ---- 6. Charts ----
fig, ax = plt.subplots(figsize=(9, 6))
colors = ["#a44a2a" if v < 50 else "#2f6f4f" for v in win_rate]
ax.barh(win_rate.index, win_rate.values, color=colors)
ax.axvline(50, color="grey", linestyle="--")
ax.set_xlabel("% of rolling 3-year windows where the fund beat the Nifty 50 index fund")
ax.set_title("How often active large-cap funds beat a Nifty 50 index fund (2013 to 2026)")
plt.tight_layout()
plt.savefig("output/rolling_win_rate.png", dpi=150)

fig, ax = plt.subplots(figsize=(9, 4.5))
ax.plot(share_of_funds_ahead.index, share_of_funds_ahead.values, color="#a44a2a")
ax.axhline(50, color="grey", linestyle="--")
ax.set_ylabel("% of active funds ahead of the index")
ax.set_title("Share of active large-cap funds beating the index over the previous 3 years")
plt.tight_layout()
plt.savefig("output/share_ahead_over_time.png", dpi=150)

growth = prices / prices.iloc[0] * 100000
fig, ax = plt.subplots(figsize=(9, 5))
for c in codes:
    if c != INDEX_CODE:
        ax.plot(growth.index, growth[c], color="#cccccc", linewidth=0.8)
ax.plot(growth.index, growth[INDEX_CODE], color="#a44a2a", linewidth=2.2, label="Nifty 50 index fund")
ax.plot(growth.index, growth.drop(columns=INDEX_CODE).median(axis=1), color="#2f6f4f", linewidth=2, label="Median active fund")
ax.set_ylabel("Value of Rs 1 lakh invested in Jan 2013")
ax.set_title("Rs 1 lakh in each fund, January 2013 to today")
ax.legend()
plt.tight_layout()
plt.savefig("output/growth_of_1_lakh.png", dpi=150)
print("\nSaved charts and tables to output/")
