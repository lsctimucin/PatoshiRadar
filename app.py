from pump_monitor import PumpMonitor


def new_token(data):

    print("===================================")
    print(data)
    print("===================================")


monitor = PumpMonitor(new_token)

monitor.start()

print("Patoshi Radar çalışıyor...")

while True:
    pass
