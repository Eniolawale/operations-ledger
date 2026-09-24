"""
generate_raw_data.py

Simulates the kind of messy raw exports an early-stage startup actually has:
mixed date formats, duplicate rows, missing values, a few bad entries.

This is NOT real company data. It's synthetic, generated to give the
cleaning/processing script something realistic to work with.

Run:
    python scripts/generate_raw_data.py
Produces:
    data/raw_signups.csv
    data/raw_revenue.csv
    data/raw_churn.csv
"""

import csv
import random
from datetime import date, timedelta

random.seed(42)

START = date(2025, 1, 1)
MONTHS = 15  # just over a year of "history"

DATE_FORMATS = [
    lambda d: d.strftime("%Y-%m-%d"),
    lambda d: d.strftime("%d/%m/%Y"),
    lambda d: d.strftime("%d-%b-%Y"),
]

SOURCES = ["organic", "referral", "paid_ads", "waitlist", ""]


def daterange_months(start, n):
    y, m = start.year, start.month
    out = []
    for _ in range(n):
        out.append(date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def random_day_in_month(d):
    day = random.randint(1, 27)
    return date(d.year, d.month, day)


def messy_date(d):
    fmt = random.choice(DATE_FORMATS)
    return fmt(d)


def gen_signups():
    rows = []
    base = 18
    for i, month in enumerate(daterange_months(START, MONTHS)):
        # gentle upward trend with noise
        count = max(3, int(base + i * 2.1 + random.gauss(0, 4)))
        for _ in range(count):
            d = random_day_in_month(month)
            rows.append(
                {
                    "date": messy_date(d),
                    "signups": 1,
                    "source": random.choice(SOURCES),
                    "notes": "" if random.random() > 0.05 else "duplicate_entry",
                }
            )
    # inject a few literal duplicate rows, on purpose
    for _ in range(6):
        rows.append(random.choice(rows).copy())
    random.shuffle(rows)
    return rows


def gen_revenue(signup_rows):
    rows = []
    txn_id = 1000
    active_customers = 0
    for i, month in enumerate(daterange_months(START, MONTHS)):
        active_customers += random.randint(8, 20)
        n_txns = max(5, active_customers // 2)
        for _ in range(n_txns):
            d = random_day_in_month(month)
            amount = round(random.choice([9500, 15000, 25000, 42000]) * random.uniform(0.9, 1.1), 2)
            status = random.choices(
                ["paid", "paid", "paid", "refunded", "failed"], weights=[70, 15, 10, 3, 2]
            )[0]
            if status == "refunded":
                amount = -abs(amount)
            rows.append(
                {
                    "transaction_id": f"TXN{txn_id}",
                    "date": messy_date(d),
                    "customer_id": f"CUST{random.randint(1, active_customers + 1):04d}",
                    "amount": amount if random.random() > 0.03 else "",  # a few blanks
                    "status": status,
                }
            )
            txn_id += 1
    # duplicate a handful of transaction ids (common export bug)
    for _ in range(4):
        dup = random.choice(rows).copy()
        rows.append(dup)
    random.shuffle(rows)
    return rows


def gen_churn():
    rows = []
    reasons = ["too_expensive", "missing_features", "switched_competitor", "no_longer_needed", ""]
    for i, month in enumerate(daterange_months(START, MONTHS)):
        if i < 2:
            continue  # no churn in the first two months, nobody's had time to leave
        n_churn = random.randint(1, max(2, i))
        for _ in range(n_churn):
            d = random_day_in_month(month)
            rows.append(
                {
                    "customer_id": f"CUST{random.randint(1, 200):04d}",
                    "cancel_date": messy_date(d),
                    "reason": random.choice(reasons),
                }
            )
    random.shuffle(rows)
    return rows


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    signups = gen_signups()
    revenue = gen_revenue(signups)
    churn = gen_churn()

    write_csv("data/raw_signups.csv", signups, ["date", "signups", "source", "notes"])
    write_csv("data/raw_revenue.csv", revenue, ["transaction_id", "date", "customer_id", "amount", "status"])
    write_csv("data/raw_churn.csv", churn, ["customer_id", "cancel_date", "reason"])

    print(f"Generated {len(signups)} signup rows, {len(revenue)} revenue rows, {len(churn)} churn rows.")
