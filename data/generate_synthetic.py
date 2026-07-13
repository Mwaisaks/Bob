"""
generate_synthetic.py — M-Pesa SMS generator for Bob's three demo personas.

Produces 60-day SMS histories alongside ground-truth transaction records.
The ground-truth data is the eval target for Phase 2's Gemma parser.

Usage:
    python data/generate_synthetic.py [--seed 42]

Output:
    data/synthetic/brian.jsonl
    data/synthetic/wanjiku.jsonl
    data/synthetic/athman.jsonl
"""

import argparse
import json
import random
import string
from datetime import datetime, timedelta
from pathlib import Path

SYNTHETIC_DIR = Path(__file__).parent / "synthetic"
DAILY_LIMIT = 500_000.0
SHORT_URLS = ["https://saf.cx/kWQpy", "https://saf.cx/lPKcC", "https://saf.cx/mRTnQ"]

# Fuliza daily charge (simplified flat rate)
FULIZA_DAILY_CHARGE = 7.50
ZIIDI_DEDUCTION = 5.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def txn_code(rng: random.Random) -> str:
    """Realistic-looking M-Pesa reference code (U + 9 uppercase alphanumeric)."""
    chars = string.ascii_uppercase + string.digits
    return "U" + "".join(rng.choices(chars, k=9))


def fmt_amount(amount: float, uppercase: bool = False) -> str:
    prefix = "KSH" if uppercase else "Ksh"
    return f"{prefix}{amount:,.2f}"


def fmt_date(dt: datetime) -> str:
    """D/M/YY — Safaricom does not zero-pad."""
    return f"{dt.day}/{dt.month}/{str(dt.year)[-2:]}"


def fmt_time(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{hour}:{dt.minute:02d} {ampm}"


def mask_phone(phone: str) -> str:
    """Safaricom masks middle digits of sender phone in receive SMSes."""
    return phone[:4] + "***" + phone[-3:]


def rand_url(rng: random.Random) -> str:
    return rng.choice(SHORT_URLS)


def rand_dt(rng: random.Random, base: datetime, hour_min: int = 7, hour_max: int = 22) -> datetime:
    return base.replace(hour=rng.randint(hour_min, hour_max), minute=rng.randint(0, 59))


def saf_fee(amount: float, tx_type: str) -> float:
    """
    Simplified Safaricom fee table based on observed real SMSes.
    Most small sends are free post-2024 tariff revision.
    Paybill carries a tiered fee; Marapay airtime costs Ksh2.
    """
    if tx_type == "paybill":
        if amount <= 100:
            return 0.0
        elif amount <= 2500:
            return 15.0
        elif amount <= 5000:
            return 25.0
        return 35.0
    elif tx_type == "airtime_other":
        return 2.0
    return 0.0  # send_money, buy_goods, airtime_saf, ziidi


# ---------------------------------------------------------------------------
# SMS templates (wording matches real Safaricom messages)
# ---------------------------------------------------------------------------

def sms_send_money(rng, amount, name, phone, dt, balance, fee) -> str:
    daily = f"{DAILY_LIMIT - amount:,.2f}"
    return (
        f"{txn_code(rng)} Confirmed. {fmt_amount(amount)} sent to {name} "
        f"{phone} on {fmt_date(dt)} at {fmt_time(dt)}. "
        f"New M-PESA balance is {fmt_amount(balance)}. "
        f"Transaction cost, {fmt_amount(fee)}.  "
        f"Amount you can transact within the day is {daily}. "
        f"Download My OneApp on {rand_url(rng)}"
    )


def sms_buy_goods(rng, amount, merchant, dt, balance, fee) -> str:
    daily = f"{DAILY_LIMIT - amount:,.2f}"
    return (
        f"{txn_code(rng)} Confirmed. {fmt_amount(amount)} paid to {merchant}. "
        f"on {fmt_date(dt)} at {fmt_time(dt)}."
        f"New M-PESA balance is {fmt_amount(balance)}. "
        f"Transaction cost, {fmt_amount(fee)}. "
        f"Amount you can transact within the day is {daily}. "
        f"Download My OneApp on {rand_url(rng)}"
    )


def sms_paybill(rng, amount, business, account, dt, balance, fee) -> str:
    daily = f"{DAILY_LIMIT - amount:,.2f}"
    return (
        f"{txn_code(rng)} Confirmed. {fmt_amount(amount, uppercase=True)} sent to {business}. "
        f"for account {account} on {fmt_date(dt)} at {fmt_time(dt)} "
        f"New M-PESA balance is {fmt_amount(balance, uppercase=True)}. "
        f"Transaction cost, {fmt_amount(fee, uppercase=True)}."
        f"Amount you can transact within the day is {daily}. "
        f"Download My OneApp on {rand_url(rng)}"
    )


def sms_receive(rng, amount, sender_name, sender_phone, dt, balance) -> str:
    # Receive SMS has no transaction cost line and no daily limit — real Safaricom behaviour
    return (
        f"{txn_code(rng)} Confirmed.You have received {fmt_amount(amount)} from "
        f"{sender_name} {mask_phone(sender_phone)} on {fmt_date(dt)} at {fmt_time(dt)}  "
        f"New M-PESA balance is {fmt_amount(balance)}. "
        f"Download My OneApp on {rand_url(rng)}"
    )


def sms_airtime_saf(rng, amount, dt, balance) -> str:
    # Safaricom airtime/data — short format, no daily limit line
    return (
        f"{txn_code(rng)} Confirmed. {fmt_amount(amount)} sent to SAFARICOM DATA BUNDLES "
        f"for account SAFARICOM DATA BUNDLES on {fmt_date(dt)} at {fmt_time(dt)}. "
        f"New M-PESA balance is {fmt_amount(balance)}. Transaction cost, {fmt_amount(0.0)}."
    )


def sms_airtime_other(rng, amount, airtel_phone, dt, balance, fee) -> str:
    daily = f"{DAILY_LIMIT - amount:,.2f}"
    return (
        f"{txn_code(rng)} Confirmed. {fmt_amount(amount)} sent to MARAPAY SOLUTION "
        f"for account {airtel_phone} on {fmt_date(dt)} at {fmt_time(dt)} "
        f"New M-PESA balance is {fmt_amount(balance)}. "
        f"Transaction cost, {fmt_amount(fee)}."
        f"Amount you can transact within the day is {daily}. "
        f"Download My OneApp on {rand_url(rng)}"
    )


def sms_ziidi(rng, amount, dt, balance) -> str:
    # Ziidi fires automatically seconds after a send; distinct closing message
    daily = f"{DAILY_LIMIT - amount:,.2f}"
    return (
        f"{txn_code(rng)} Confirmed. {fmt_amount(amount)} sent to ZIIDI on "
        f"{fmt_date(dt)} at {fmt_time(dt)} "
        f"New M-PESA balance is {fmt_amount(balance)}. "
        f"Transaction cost, {fmt_amount(0.0)}."
        f"Amount you can transact within the day is {daily}. "
        f"Pay your water/KPLC bill conveniently using M-PESA APP or use Paybill option on Lipa Na M-PESA."
    )


def sms_fuliza_borrow(rng, borrow_amount, original_tx_amount, dt, balance) -> str:
    repay_date = dt + timedelta(days=3)
    return (
        f"{txn_code(rng)} Confirmed. Your M-PESA transaction of {fmt_amount(original_tx_amount)} "
        f"has been completed. Fuliza M-PESA amount of {fmt_amount(borrow_amount)}. "
        f"Repayment date: {fmt_date(repay_date)}. "
        f"Daily charge {fmt_amount(FULIZA_DAILY_CHARGE)}. "
        f"New M-PESA balance is {fmt_amount(balance)}."
    )


def sms_fuliza_repay(rng, repaid, outstanding, dt, balance) -> str:
    return (
        f"{txn_code(rng)} Confirmed. {fmt_amount(repaid)} repaid to Fuliza M-PESA on "
        f"{fmt_date(dt)} at {fmt_time(dt)}. Outstanding balance: {fmt_amount(outstanding)}. "
        f"New M-PESA balance is {fmt_amount(balance)}."
    )


# ---------------------------------------------------------------------------
# Ground truth record
# ---------------------------------------------------------------------------

def rec(sms_text, tx_type, amount, fee, counterparty, balance_after, dt,
        is_fuliza=False, fuliza_amount=0.0) -> dict:
    return {
        "sms": sms_text,
        "ground_truth": {
            "type": tx_type,
            "amount": round(amount, 2),
            "fee": round(fee, 2),
            "counterparty": counterparty,
            "balance_after": round(balance_after, 2),
            "timestamp": dt.isoformat(timespec="minutes"),
            "is_fuliza": is_fuliza,
            "fuliza_amount": round(fuliza_amount, 2),
        },
    }


# ---------------------------------------------------------------------------
# Brian Otieno — HELB boom-bust
# KU Year 2. HELB lands, 40% gone in week one. Fuliza by week three.
# ---------------------------------------------------------------------------

def generate_brian(start: datetime, rng: random.Random) -> list[dict]:
    bal = 823.50
    fuliza_owed = 0.0
    events = []

    def add(dt, tx_type, amount, fee, counterparty, sms_text, is_fuliza=False, f_amt=0.0):
        nonlocal bal
        events.append(rec(sms_text, tx_type, amount, fee, counterparty, bal, dt,
                          is_fuliza, f_amt))

    def send(dt, amount, name, phone, with_ziidi=True):
        nonlocal bal
        fee = saf_fee(amount, "send_money")
        bal -= (amount + fee)
        add(dt, "send_money", amount, fee, name,
            sms_send_money(rng, amount, name, phone, dt, bal, fee))
        if with_ziidi and bal >= ZIIDI_DEDUCTION:
            z_dt = dt + timedelta(seconds=rng.randint(3, 10))
            bal -= ZIIDI_DEDUCTION
            add(z_dt, "ziidi", ZIIDI_DEDUCTION, 0.0, "ZIIDI",
                sms_ziidi(rng, ZIIDI_DEDUCTION, z_dt, bal))

    def buy(dt, amount, merchant):
        nonlocal bal
        fee = saf_fee(amount, "buy_goods")
        bal -= (amount + fee)
        add(dt, "buy_goods", amount, fee, merchant,
            sms_buy_goods(rng, amount, merchant, dt, bal, fee))

    def paybill(dt, amount, business, account):
        nonlocal bal
        fee = saf_fee(amount, "paybill")
        bal -= (amount + fee)
        add(dt, "paybill", amount, fee, business,
            sms_paybill(rng, amount, business, account, dt, bal, fee))

    def receive(dt, amount, sender_name, sender_phone):
        nonlocal bal, fuliza_owed
        bal += amount
        add(dt, "receive", amount, 0.0, sender_name,
            sms_receive(rng, amount, sender_name, sender_phone, dt, bal))
        # Auto-repay Fuliza when money arrives
        if fuliza_owed > 0 and bal > fuliza_owed:
            r_dt = dt + timedelta(seconds=rng.randint(5, 15))
            repaid = fuliza_owed
            bal -= repaid
            fuliza_owed = 0.0
            add(r_dt, "fuliza_repay", repaid, 0.0, "FULIZA M-PESA",
                sms_fuliza_repay(rng, repaid, 0.0, r_dt, bal))

    def airtime(dt, amount):
        nonlocal bal
        bal -= amount
        add(dt, "airtime_saf", amount, 0.0, "SAFARICOM DATA BUNDLES",
            sms_airtime_saf(rng, amount, dt, bal))

    def fuliza(dt, tx_amount, borrow_amount):
        nonlocal bal, fuliza_owed
        # Fuliza covers the shortfall; balance stays near zero
        fuliza_owed += borrow_amount + FULIZA_DAILY_CHARGE
        bal += borrow_amount
        bal -= tx_amount
        add(dt, "fuliza_borrow", tx_amount, FULIZA_DAILY_CHARGE, "FULIZA M-PESA",
            sms_fuliza_borrow(rng, borrow_amount, tx_amount, dt, bal),
            is_fuliza=True, f_amt=borrow_amount)

    d = lambda n: rand_dt(rng, start + timedelta(days=n))

    # --- Pre-HELB (days 0-4): scraping by ---
    airtime(d(1), 30)
    buy(d(2), 80, "CAMPUS CAFETERIA")
    send(d(3), 50, "PETER  KAMAU", "0711223344")     # classmate asks for lunch money

    # --- Day 5: HELB lands ---
    helb_dt = rand_dt(rng, start + timedelta(days=5), 9, 11)
    receive(helb_dt, 12000.0, "HELB DISBURSEMENTS", "0800000001")

    # Rent goes first (responsible moment)
    paybill(rand_dt(rng, start + timedelta(days=5), 12, 16),
            4500.0, "KENYATTA UNIVERSITY HOSTELS", "BRN2024/0712340001")

    # --- Days 5-10: spending spree (HELB disbursement day effect) ---
    buy(d(5), 850, "NAIVAS KAHAWA WEST")              # grocery haul
    buy(d(6), 420, "JAVA HOUSE KU")                  # treat for Alice
    send(d(6), 500, "ALICE  NJERI", "0722334455")    # weekend plans
    buy(d(7), 1200, "CHICKEN INN THIKA RD")           # boys' night (group buy)
    airtime(d(8), 100)
    buy(d(9), 300, "QUICKMART KASARANI")
    send(d(9), 200, "PETER  KAMAU", "0711223344")    # Peter's share of a bet
    buy(d(10), 550, "CAMPUS CAFETERIA")

    # --- Days 11-20: slowing down, still okay ---
    buy(d(11), 120, "CAMPUS CAFETERIA")
    airtime(d(13), 50)
    buy(d(14), 200, "CAMPUS CAFETERIA")
    send(d(15), 300, "MUM OTIENO", "0700112233")     # sends some back home
    buy(d(17), 180, "CAMPUS CAFETERIA")
    buy(d(18), 90, "QUICKMART KASARANI")
    airtime(d(19), 50)
    buy(d(20), 250, "CAMPUS CAFETERIA")

    # --- Days 21-30: running on fumes, Fuliza starts ---
    buy(d(21), 100, "CAMPUS CAFETERIA")
    airtime(d(22), 30)

    # First Fuliza — embarrassing but "just this once"
    fuliza(d(23), 150, 160)
    buy(d(24), 150, "CAMPUS CAFETERIA")
    fuliza(d(25), 200, 210)
    send(d(26), 100, "ALICE  NJERI", "0722334455")   # she's not asking but he wants to
    airtime(d(27), 30)
    fuliza(d(28), 100, 110)
    buy(d(29), 80, "CAMPUS CAFETERIA")

    # --- Day 30: Mum sends emergency money ---
    mum_dt = rand_dt(rng, start + timedelta(days=30), 14, 18)
    receive(mum_dt, 1500.0, "MUM  OTIENO", "0700112233")   # Fuliza auto-repaid here

    # --- Days 31-45: second cycle, slightly more careful ---
    buy(d(31), 120, "CAMPUS CAFETERIA")
    airtime(d(32), 50)
    buy(d(34), 200, "CAMPUS CAFETERIA")
    buy(d(36), 350, "NAIVAS KAHAWA WEST")
    send(d(38), 150, "PETER  KAMAU", "0711223344")
    buy(d(40), 100, "CAMPUS CAFETERIA")
    airtime(d(42), 30)
    buy(d(44), 80, "CAMPUS CAFETERIA")
    buy(d(45), 180, "QUICKMART KASARANI")

    # --- Days 46-60: Fuliza again, same pattern ---
    buy(d(47), 120, "CAMPUS CAFETERIA")
    airtime(d(48), 30)
    fuliza(d(50), 120, 130)
    buy(d(51), 120, "CAMPUS CAFETERIA")
    fuliza(d(53), 80, 90)
    airtime(d(55), 30)
    fuliza(d(57), 200, 210)
    buy(d(58), 100, "CAMPUS CAFETERIA")
    fuliza(d(59), 150, 160)

    return sorted(events, key=lambda x: x["ground_truth"]["timestamp"])


# ---------------------------------------------------------------------------
# Wanjiku Kamau — the hustler
# USIU Year 3. Irregular income (mitumba + parents). Fee bleed, no buffer.
# ---------------------------------------------------------------------------

def generate_wanjiku(start: datetime, rng: random.Random) -> list[dict]:
    # Hustler starting balance — rent money gathered from last week's sales
    bal = 5000.00
    events = []

    def add(dt, tx_type, amount, fee, counterparty, sms_text):
        nonlocal bal
        events.append(rec(sms_text, tx_type, amount, fee, counterparty, bal, dt))

    def send(dt, amount, name, phone):
        nonlocal bal
        fee = saf_fee(amount, "send_money")
        bal -= (amount + fee)
        add(dt, "send_money", amount, fee, name,
            sms_send_money(rng, amount, name, phone, dt, bal, fee))
        # Wanjiku is on Ziidi too
        if bal >= ZIIDI_DEDUCTION:
            z_dt = dt + timedelta(seconds=rng.randint(3, 10))
            bal -= ZIIDI_DEDUCTION
            add(z_dt, "ziidi", ZIIDI_DEDUCTION, 0.0, "ZIIDI",
                sms_ziidi(rng, ZIIDI_DEDUCTION, z_dt, bal))

    def buy(dt, amount, merchant):
        nonlocal bal
        fee = saf_fee(amount, "buy_goods")
        bal -= (amount + fee)
        add(dt, "buy_goods", amount, fee, merchant,
            sms_buy_goods(rng, amount, merchant, dt, bal, fee))

    def paybill(dt, amount, business, account):
        nonlocal bal
        fee = saf_fee(amount, "paybill")
        bal -= (amount + fee)
        add(dt, "paybill", amount, fee, business,
            sms_paybill(rng, amount, business, account, dt, bal, fee))

    def receive(dt, amount, sender_name, sender_phone):
        nonlocal bal
        bal += amount
        add(dt, "receive", amount, 0.0, sender_name,
            sms_receive(rng, amount, sender_name, sender_phone, dt, bal))

    def airtime_other(dt, amount):
        nonlocal bal
        fee = saf_fee(amount, "airtime_other")
        bal -= (amount + fee)
        add(dt, "airtime_other", amount, fee, "MARAPAY SOLUTION",
            sms_airtime_other(rng, amount, "0738549222", dt, bal, fee))

    d = lambda n: rand_dt(rng, start + timedelta(days=n))

    # Wanjiku's income is irregular — simulate weekly parent sends + sales
    # Week 1
    receive(d(1), rng.randint(1500, 2800), "MUM  KAMAU", "0714556677")
    paybill(d(1), 5500, "CASA ROYALE APTS", "W1204")   # rent comes first
    airtime_other(d(2), 50)
    buy(d(2), 120, "TOI MARKET STALL 44")              # buying stock
    receive(d(3), rng.randint(900, 2200), "TONY  MUIRURI", "0733445566")  # mitumba sale
    send(d(3), 800, "GRACE  WANJIKU", "0711000111")    # supplier payment
    buy(d(4), 200, "EASTMATT KASARANI")
    airtime_other(d(5), 50)
    receive(d(5), rng.randint(700, 1800), "JANE  MUTHONI", "0722001122")  # customer pays
    send(d(5), 200, "JANE  MUTHONI", "0722001122")     # change (bought more than expected)
    buy(d(6), 180, "GIORDANO PIZZA USIU")              # treat after good sales day
    airtime_other(d(7), 30)

    # Week 2
    receive(d(8), rng.randint(1200, 2500), "MUM  KAMAU", "0714556677")
    airtime_other(d(9), 50)
    buy(d(9), 90, "EASTMATT KASARANI")
    receive(d(10), rng.randint(600, 1500), "TONY  MUIRURI", "0733445566")
    send(d(10), 600, "GRACE  WANJIKU", "0711000111")   # restock payment
    buy(d(11), 150, "TOI MARKET STALL 44")
    airtime_other(d(12), 30)
    buy(d(13), 200, "NAIVAS KASARANI")
    airtime_other(d(14), 50)
    receive(d(14), rng.randint(800, 1900), "JANE  MUTHONI", "0722001122")

    # Week 3 — slower sales week, fee bleed visible
    receive(d(15), rng.randint(1000, 2000), "MUM  KAMAU", "0714556677")
    airtime_other(d(15), 50)
    buy(d(16), 100, "EASTMATT KASARANI")
    send(d(17), 300, "TONY  MUIRURI", "0733445566")   # small restock
    airtime_other(d(18), 50)
    buy(d(19), 120, "GIORDANO PIZZA USIU")
    airtime_other(d(19), 30)
    paybill(d(20), 350, "KPLC PREPAID", "32400023456")
    # Only one sale this week
    receive(d(21), rng.randint(500, 1200), "JANE  MUTHONI", "0722001122")
    send(d(21), 500, "GRACE  WANJIKU", "0711000111")

    # Week 4
    receive(d(22), rng.randint(1500, 2500), "MUM  KAMAU", "0714556677")
    airtime_other(d(22), 50)
    buy(d(23), 100, "EASTMATT KASARANI")
    receive(d(24), rng.randint(900, 2000), "TONY  MUIRURI", "0733445566")
    send(d(24), 700, "GRACE  WANJIKU", "0711000111")
    airtime_other(d(25), 50)
    buy(d(26), 150, "NAIVAS KASARANI")
    receive(d(28), rng.randint(800, 1600), "JANE  MUTHONI", "0722001122")
    airtime_other(d(28), 30)

    # Month 2 — repeat pattern, slightly tighter
    receive(d(30), rng.randint(1200, 2200), "MUM  KAMAU", "0714556677")
    paybill(d(30), 5500, "CASA ROYALE APTS", "W1204")
    buy(d(31), 130, "TOI MARKET STALL 44")
    airtime_other(d(31), 50)
    receive(d(33), rng.randint(700, 1500), "TONY  MUIRURI", "0733445566")
    send(d(33), 500, "GRACE  WANJIKU", "0711000111")
    airtime_other(d(35), 50)
    receive(d(36), rng.randint(600, 1200), "JANE  MUTHONI", "0722001122")
    buy(d(37), 100, "EASTMATT KASARANI")
    airtime_other(d(38), 30)
    receive(d(40), rng.randint(1500, 2500), "MUM  KAMAU", "0714556677")
    airtime_other(d(40), 50)
    send(d(41), 400, "TONY  MUIRURI", "0733445566")
    paybill(d(49), 350, "KPLC PREPAID", "32400023456")
    receive(d(50), rng.randint(800, 1800), "JANE  MUTHONI", "0722001122")
    airtime_other(d(51), 50)
    receive(d(52), rng.randint(1000, 2000), "MUM  KAMAU", "0714556677")
    airtime_other(d(52), 30)
    send(d(54), 300, "GRACE  WANJIKU", "0711000111")
    buy(d(56), 160, "GIORDANO PIZZA USIU")
    airtime_other(d(58), 50)
    receive(d(59), rng.randint(700, 1500), "TONY  MUIRURI", "0733445566")

    return sorted(events, key=lambda x: x["ground_truth"]["timestamp"])


# ---------------------------------------------------------------------------
# Athman Hassan — the disciplined saver failing quietly
# Strathmore Year 4. Regular income. Subscriptions and "just 50 bob" leaks.
# ---------------------------------------------------------------------------

def generate_athman(start: datetime, rng: random.Random) -> list[dict]:
    # Starting balance represents money left from previous month's income
    bal = 15000.00
    events = []

    def add(dt, tx_type, amount, fee, counterparty, sms_text):
        nonlocal bal
        events.append(rec(sms_text, tx_type, amount, fee, counterparty, bal, dt))

    def send(dt, amount, name, phone):
        nonlocal bal
        fee = saf_fee(amount, "send_money")
        bal -= (amount + fee)
        add(dt, "send_money", amount, fee, name,
            sms_send_money(rng, amount, name, phone, dt, bal, fee))
        # Athman is on Ziidi
        if bal >= ZIIDI_DEDUCTION:
            z_dt = dt + timedelta(seconds=rng.randint(3, 10))
            bal -= ZIIDI_DEDUCTION
            add(z_dt, "ziidi", ZIIDI_DEDUCTION, 0.0, "ZIIDI",
                sms_ziidi(rng, ZIIDI_DEDUCTION, z_dt, bal))

    def buy(dt, amount, merchant):
        nonlocal bal
        fee = saf_fee(amount, "buy_goods")
        bal -= (amount + fee)
        add(dt, "buy_goods", amount, fee, merchant,
            sms_buy_goods(rng, amount, merchant, dt, bal, fee))

    def paybill(dt, amount, business, account):
        nonlocal bal
        fee = saf_fee(amount, "paybill")
        bal -= (amount + fee)
        add(dt, "paybill", amount, fee, business,
            sms_paybill(rng, amount, business, account, dt, bal, fee))

    def receive(dt, amount, sender_name, sender_phone):
        nonlocal bal
        bal += amount
        add(dt, "receive", amount, 0.0, sender_name,
            sms_receive(rng, amount, sender_name, sender_phone, dt, bal))

    def airtime(dt, amount=50):
        nonlocal bal
        bal -= amount
        add(dt, "airtime_saf", amount, 0.0, "SAFARICOM DATA BUNDLES",
            sms_airtime_saf(rng, amount, dt, bal))

    d = lambda n: rand_dt(rng, start + timedelta(days=n))

    # Month 1 starts mid-cycle (day 28 is payday)
    # Carry-over balance is 3240.75

    # Recurring expenses fire like clockwork
    paybill(d(2), 6000, "MADARAKA ESTATE MGT", "ATH2024/STR")       # rent
    paybill(d(5), 500, "ZUKU FIBER", "0734560003")                   # wifi
    paybill(d(10), 650, "SHOWMAX KENYA", "hassan.a@strathmore.edu")  # streaming
    send(d(15), 2000, "MUM  HASSAN", "0701234567")                   # monthly to mum
    paybill(d(20), 280, "KPLC PREPAID", "45600034567")               # electricity

    # Daily life: matatu, coffee, random buys
    airtime(d(1), 50)
    buy(d(1), 180, "STRATHMORE CAFETERIA")
    buy(d(3), 350, "NAIROBI JAVA WESTLANDS")                         # Java after work
    airtime(d(4), 100)
    buy(d(6), 120, "STRATHMORE CAFETERIA")
    buy(d(7), 480, "ARTCAFFE WESTLANDS")                             # team lunch (he pays and waits for refunds that never come)
    airtime(d(8), 50)
    buy(d(9), 200, "TOTAL ENERGIES MADARAKA")                        # matatu top-up
    buy(d(11), 150, "STRATHMORE CAFETERIA")
    airtime(d(12), 50)
    buy(d(13), 60, "UCHUMI LANGATA RD")                              # "just 50 bob" = snacks
    send(d(14), 500, "ABDI  OSMAN", "0712334455")                    # study group bought pizza
    buy(d(16), 180, "STRATHMORE CAFETERIA")
    airtime(d(17), 100)
    buy(d(18), 250, "NAIROBI JAVA WESTLANDS")
    buy(d(19), 80, "UCHUMI LANGATA RD")                              # another "quick stop"
    buy(d(21), 350, "ARTCAFFE WESTLANDS")
    airtime(d(22), 50)
    buy(d(23), 120, "STRATHMORE CAFETERIA")
    send(d(25), 300, "KEVIN  MWANGI", "0722445566")                  # colleague's baby shower
    buy(d(26), 200, "TOTAL ENERGIES MADARAKA")
    airtime(d(27), 50)

    # Day 28: salary arrives
    salary_dt = rand_dt(rng, start + timedelta(days=28), 9, 12)
    receive(salary_dt, 25000.0, "INNOVEX TECH LTD", "0800223344")

    # Savings attempt — targets 5,000 but only manages ~1,500
    paybill(d(28), 1500, "MSHWARI SAVINGS", "ATH_MSHWARI")
    # ... and then immediately spends some of it
    buy(d(29), 650, "NAIROBI JAVA WESTLANDS")                        # celebratory coffee (salary day ritual)
    airtime(d(29), 100)

    # Month 2 — exact same subscriptions, slightly larger "just 50 bob" total
    paybill(d(32), 6000, "MADARAKA ESTATE MGT", "ATH2024/STR")
    paybill(d(35), 500, "ZUKU FIBER", "0734560003")
    buy(d(33), 180, "STRATHMORE CAFETERIA")
    airtime(d(34), 50)
    buy(d(36), 320, "NAIROBI JAVA WESTLANDS")
    airtime(d(37), 100)
    buy(d(38), 90, "UCHUMI LANGATA RD")
    buy(d(39), 250, "STRATHMORE CAFETERIA")
    paybill(d(40), 650, "SHOWMAX KENYA", "hassan.a@strathmore.edu")
    airtime(d(41), 50)
    buy(d(42), 500, "ARTCAFFE WESTLANDS")
    send(d(44), 2000, "MUM  HASSAN", "0701234567")
    buy(d(45), 180, "STRATHMORE CAFETERIA")
    airtime(d(46), 50)
    buy(d(47), 75, "UCHUMI LANGATA RD")
    buy(d(48), 300, "TOTAL ENERGIES MADARAKA")
    paybill(d(50), 280, "KPLC PREPAID", "45600034567")
    airtime(d(51), 100)
    buy(d(52), 200, "NAIROBI JAVA WESTLANDS")
    send(d(53), 400, "ABDI  OSMAN", "0712334455")
    buy(d(54), 140, "STRATHMORE CAFETERIA")
    airtime(d(55), 50)
    buy(d(57), 350, "ARTCAFFE WESTLANDS")
    buy(d(58), 95, "UCHUMI LANGATA RD")
    airtime(d(59), 50)

    # Salary again — saves even less this month (only 800)
    salary_dt2 = rand_dt(rng, start + timedelta(days=58), 9, 12)
    receive(salary_dt2, 25000.0, "INNOVEX TECH LTD", "0800223344")
    paybill(d(58), 800, "MSHWARI SAVINGS", "ATH_MSHWARI")

    return sorted(events, key=lambda x: x["ground_truth"]["timestamp"])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

GENERATORS = {
    "brian": generate_brian,
    "wanjiku": generate_wanjiku,
    "athman": generate_athman,
}


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic M-Pesa SMS data")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--start", type=str, default="2026-06-01",
                        help="Simulation start date YYYY-MM-DD (default: 2026-06-01)")
    args = parser.parse_args()

    start_date = datetime.fromisoformat(args.start)
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

    for persona_id, generator_fn in GENERATORS.items():
        rng = random.Random(args.seed + hash(persona_id))
        events = generator_fn(start_date, rng)

        out_path = SYNTHETIC_DIR / f"{persona_id}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

        print(f"  {persona_id:10s} → {out_path}  ({len(events)} transactions)")

    print(f"\nDone. Output in {SYNTHETIC_DIR}")


if __name__ == "__main__":
    main()
