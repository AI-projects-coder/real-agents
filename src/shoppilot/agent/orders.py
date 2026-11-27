"""Fake order database. Stands in for the real order service (dates relative to today)."""
import datetime as dt

_today = dt.date.today()


def _days_ago(n: int) -> str:
    return (_today - dt.timedelta(days=n)).isoformat()


ORDERS = {
    "48213": {"order_id": "48213", "customer_id": "C-7", "items": ["Blue electric kettle", "2-slice toaster"],
              "total_inr": 3499, "status": "delivered", "delivered_on": _days_ago(5)},
    "51877": {"order_id": "51877", "customer_id": "C-7", "items": ["UltraBook 14 laptop"],
              "total_inr": 64999, "status": "delivered", "delivered_on": _days_ago(3)},
    "39002": {"order_id": "39002", "customer_id": "C-12", "items": ["Wireless headphones"],
              "total_inr": 2199, "status": "delivered", "delivered_on": _days_ago(45)},
    "60415": {"order_id": "60415", "customer_id": "C-12", "items": ["Running shoes, size 9"],
              "total_inr": 1899, "status": "shipped", "delivered_on": None,
              "eta": (_today + dt.timedelta(days=2)).isoformat()},
}
