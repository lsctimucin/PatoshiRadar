from creator_1 import TARGET_CREATORS


KEYWORDS = [
    "patoshi",
    "pat",
    "turan",
    "pato",
    "patos",
    "enes",
    "parad",
    "paradot",
    "paradotor",
    "patosh",
]


def keyword_match(name, symbol):
    text = f"{name} {symbol}".lower()

    return any(keyword in text for keyword in KEYWORDS)


def creator_match(creator):
    return creator in TARGET_CREATORS
