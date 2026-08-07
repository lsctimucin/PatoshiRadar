from datetime import datetime

creator_history = {}


def update_creator(creator):

    now = datetime.utcnow()

    if creator not in creator_history:
        creator_history[creator] = {
            "count": 1,
            "first_seen": now,
            "last_seen": now
        }

        return {
            "count": 1,
            "is_new": True,
            "minutes": 0
        }

    last_seen = creator_history[creator]["last_seen"]

    minutes = int((now - last_seen).total_seconds() / 60)

    creator_history[creator]["count"] += 1
    creator_history[creator]["last_seen"] = now

    return {
        "count": creator_history[creator]["count"],
        "is_new": False,
        "minutes": minutes
    }
