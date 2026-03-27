"""tutorial/setup_db.py - SQLite 샘플 DB 생성 스크립트."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "tutorial.db"


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 테이블 생성
    cur.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_purchase_date TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT,
            order_date TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    # 고객 데이터 (10명)
    now = datetime.now()
    customers = [
        (1, "김민수", "minsu@example.com",   (now - timedelta(days=365)).isoformat(), (now - timedelta(days=5)).isoformat()),
        (2, "이영희", "younghee@example.com", (now - timedelta(days=300)).isoformat(), (now - timedelta(days=120)).isoformat()),  # 이탈 고객
        (3, "박지훈", "jihoon@example.com",   (now - timedelta(days=200)).isoformat(), (now - timedelta(days=3)).isoformat()),
        (4, "최수정", "sujung@example.com",   (now - timedelta(days=150)).isoformat(), (now - timedelta(days=100)).isoformat()),  # 이탈 고객
        (5, "정다은", "daeun@example.com",    (now - timedelta(days=100)).isoformat(), (now - timedelta(days=1)).isoformat()),
        (6, "한서윤", "seoyun@example.com",   (now - timedelta(days=50)).isoformat(),  (now - timedelta(days=10)).isoformat()),
        (7, "오준호", "junho@example.com",    (now - timedelta(days=20)).isoformat(),  (now - timedelta(days=2)).isoformat()),   # 신규 고객
        (8, "윤하린", "harin@example.com",    (now - timedelta(days=10)).isoformat(),  (now - timedelta(days=7)).isoformat()),   # 신규 고객
        (9, "임서준", "seojun@example.com",   (now - timedelta(days=5)).isoformat(),   None),                                    # 신규, 구매 없음
        (10, "강예린", "yerin@example.com",   (now - timedelta(days=2)).isoformat(),   None),                                    # 신규, 구매 없음
    ]
    cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", customers)

    # 주문 데이터 (25건)
    orders = [
        (1,  1, 45000,  "completed",  (now - timedelta(days=5)).isoformat(),  (now - timedelta(days=5)).isoformat()),
        (2,  1, 32000,  "completed",  (now - timedelta(days=30)).isoformat(), (now - timedelta(days=30)).isoformat()),
        (3,  1, 18000,  "completed",  (now - timedelta(days=60)).isoformat(), (now - timedelta(days=60)).isoformat()),
        (4,  2, 55000,  "completed",  (now - timedelta(days=120)).isoformat(),(now - timedelta(days=120)).isoformat()),
        (5,  2, 27000,  "completed",  (now - timedelta(days=150)).isoformat(),(now - timedelta(days=150)).isoformat()),
        (6,  3, 120000, "completed",  (now - timedelta(days=3)).isoformat(),  (now - timedelta(days=3)).isoformat()),
        (7,  3, 65000,  "completed",  (now - timedelta(days=20)).isoformat(), (now - timedelta(days=20)).isoformat()),
        (8,  3, 43000,  "completed",  (now - timedelta(days=45)).isoformat(), (now - timedelta(days=45)).isoformat()),
        (9,  4, 88000,  "completed",  (now - timedelta(days=100)).isoformat(),(now - timedelta(days=100)).isoformat()),
        (10, 4, 15000,  "cancelled",  (now - timedelta(days=110)).isoformat(),(now - timedelta(days=110)).isoformat()),
        (11, 5, 72000,  "completed",  (now - timedelta(days=1)).isoformat(),  (now - timedelta(days=1)).isoformat()),
        (12, 5, 34000,  "completed",  (now - timedelta(days=15)).isoformat(), (now - timedelta(days=15)).isoformat()),
        (13, 5, 29000,  "completed",  (now - timedelta(days=40)).isoformat(), (now - timedelta(days=40)).isoformat()),
        (14, 6, 51000,  "completed",  (now - timedelta(days=10)).isoformat(), (now - timedelta(days=10)).isoformat()),
        (15, 6, 19000,  "pending",    (now - timedelta(days=2)).isoformat(),  (now - timedelta(days=2)).isoformat()),
        (16, 7, 96000,  "completed",  (now - timedelta(days=2)).isoformat(),  (now - timedelta(days=2)).isoformat()),
        (17, 7, 41000,  "completed",  (now - timedelta(days=8)).isoformat(),  (now - timedelta(days=8)).isoformat()),
        (18, 8, 23000,  "completed",  (now - timedelta(days=7)).isoformat(),  (now - timedelta(days=7)).isoformat()),
        (19, 8, 67000,  None,         (now - timedelta(days=3)).isoformat(),  (now - timedelta(days=3)).isoformat()),   # status NULL
        (20, 1, 55000,  "completed",  (now - timedelta(days=90)).isoformat(), (now - timedelta(days=90)).isoformat()),
        (21, 3, 38000,  "refunded",   (now - timedelta(days=70)).isoformat(), (now - timedelta(days=70)).isoformat()),
        (22, 5, 82000,  "completed",  (now - timedelta(days=60)).isoformat(), (now - timedelta(days=60)).isoformat()),
        (23, 6, 44000,  "completed",  (now - timedelta(days=35)).isoformat(), (now - timedelta(days=35)).isoformat()),
        (24, 7, 31000,  None,         (now - timedelta(days=15)).isoformat(), (now - timedelta(days=15)).isoformat()),  # status NULL
        (25, 3, 99000,  "completed",  (now - timedelta(days=1)).isoformat(),  (now - timedelta(hours=2)).isoformat()),
    ]
    cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", orders)

    conn.commit()
    conn.close()

    print(f"DB 생성 완료: {DB_PATH}")
    print(f"  customers: 10명 (이탈 2명, 신규 4명)")
    print(f"  orders: 25건 (completed 20, cancelled 1, pending 1, refunded 1, NULL 2)")


if __name__ == "__main__":
    main()
