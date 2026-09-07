from creator_1 import TARGET_CREATORS


KEYWORDS = [
    "patoshi",
    "pats",
    "turan",
    "pato",
    "patos",
    "paradot",
    "paradotor",
    "patosh",
    "patoshimeme",
    "$patoshi",
    "$pat",
]


def keyword_match(name, symbol):

    text = f"{name} {symbol}".lower()

    for keyword in KEYWORDS:
        if keyword in text:
            return keyword

    return None


def creator_match(creator):

    for creator_name, wallet in TARGET_CREATORS.items():

        if creator == wallet:
            return creator_name

    return None
