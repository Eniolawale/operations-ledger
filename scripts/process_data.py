"""
process_data.py

Takes the three raw exports (signups, revenue, churn) and turns them into
a single clean monthly summary, ready for the dashboard.

This is the actual "automation" part of the project: instead of someone
manually pulling three CSVs into a spreadsheet every week and re-cleaning
them by hand, this script does it in one run.

Run:
    python scripts/process_data.py
Reads:
    data/raw_signups.csv, data/raw_revenue.csv, data/raw_churn.csv
Writes:
    data/monthly_summary.csv   (clean, human-readable)
    dashboard/data.json        (feeds the dashboard)
"""

import json
import pandas as pd

RAW_DIR = "data"
OUT_CSV = "data/monthly_summary.csv"
OUT_JSON = "dashboard/data.json"


def parse_mixed_dates(series):
    """Raw exports use three different date formats. Try each in turn
    instead of dropping anything pandas can't guess on its own."""
    parsed = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    mask = parsed.isna()
    parsed.loc[mask] = pd.to_datetime(series[mask], format="%d/%m/%Y", errors="coerce")
    mask = parsed.isna()
    parsed.loc[mask] = pd.to_datetime(series[mask], format="%d-%b-%Y", errors="coerce")
    return parsed


def load_signups():
    df = pd.read_csv(f"{RAW_DIR}/raw_signups.csv")
    df["date"] = parse_mixed_dates(df["date"])
    before = len(df)
    df = df.drop_duplicates(subset=["date", "source"], keep="first")
    dropped = before - len(df)
    df["month"] = df["date"].dt.to_period("M")
    monthly = df.groupby("month").size().rename("new_signups")
    return monthly, dropped


def load_revenue():
    df = pd.read_csv(f"{RAW_DIR}/raw_revenue.csv")
    df["date"] = parse_mixed_dates(df["date"])
    before = len(df)
    df = df.drop_duplicates(subset=["transaction_id"], keep="first")
    dropped_dupes = before - len(df)

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    blank_amounts = df["amount"].isna().sum()
    df = df.dropna(subset=["amount"])

    df = df[df["status"] != "failed"]  # failed charges never landed, exclude from revenue
    df["month"] = df["date"].dt.to_period("M")
    monthly_revenue = df.groupby("month")["amount"].sum().rename("net_revenue")
    monthly_active = df[df["amount"] > 0].groupby("month")["customer_id"].nunique().rename("paying_customers")
    return monthly_revenue, monthly_active, dropped_dupes, blank_amounts


def load_churn():
    df = pd.read_csv(f"{RAW_DIR}/raw_churn.csv")
    df["cancel_date"] = parse_mixed_dates(df["cancel_date"])
    df["month"] = df["cancel_date"].dt.to_period("M")
    monthly = df.groupby("month").size().rename("churned_customers")
    return monthly


def main():
    signups, dupes_dropped_signups = load_signups()
    revenue, paying_customers, dupes_dropped_revenue, blanks_dropped = load_revenue()
    churn = load_churn()

    summary = pd.concat([signups, revenue, paying_customers, churn], axis=1).fillna(0)
    summary = summary.sort_index()
    summary["new_signups"] = summary["new_signups"].astype(int)
    summary["churned_customers"] = summary["churned_customers"].astype(int)
    summary["paying_customers"] = summary["paying_customers"].astype(int)
    summary["net_revenue"] = summary["net_revenue"].round(2)

    # running active-customer estimate: cumulative paying customers minus cumulative churn
    summary["active_customers"] = (
        summary["paying_customers"].cumsum() - summary["churned_customers"].cumsum()
    ).clip(lower=0)

    summary["churn_rate_pct"] = (
        summary["churned_customers"] / summary["active_customers"].replace(0, pd.NA) * 100
    ).round(1).fillna(0)

    summary.index = summary.index.astype(str)
    summary = summary.reset_index().rename(columns={"index": "month"})

    summary.to_csv(OUT_CSV, index=False)

    payload = {
        "months": summary["month"].tolist(),
        "new_signups": summary["new_signups"].tolist(),
        "net_revenue": summary["net_revenue"].tolist(),
        "active_customers": summary["active_customers"].tolist(),
        "churned_customers": summary["churned_customers"].tolist(),
        "churn_rate_pct": summary["churn_rate_pct"].tolist(),
        "meta": {
            "duplicate_signup_rows_dropped": int(dupes_dropped_signups),
            "duplicate_revenue_rows_dropped": int(dupes_dropped_revenue),
            "revenue_rows_missing_amount_dropped": int(blanks_dropped),
        },
    }
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, indent=2)

    print("Cleaned and aggregated.")
    print(f"  Duplicate signup rows dropped: {dupes_dropped_signups}")
    print(f"  Duplicate revenue rows dropped: {dupes_dropped_revenue}")
    print(f"  Revenue rows with missing amount dropped: {blanks_dropped}")
    print(f"Wrote {OUT_CSV} and {OUT_JSON}")


if __name__ == "__main__":
    main()
