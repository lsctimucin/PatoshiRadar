event = parse_transaction(
    data,
    tracked_mint=mint
)

if event is None:
    continue

print(
    f"🧪 V5.1 PARSER CHECK | "
    f"mint={mint} | "
    f"tracked={event.get('tracked')} | "
    f"sig={event.get('signature')}"
)

if not event.get("tracked"):
    continue

print(
    f"🎯 V5.1 PARSER MATCH | "
    f"{mint} | "
    f"sig={event.get('signature')}"
)

_record_event(event)
