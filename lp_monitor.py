import threading
import time

from solana_rpc import check_lp

watch_list = {}


def add_token(mint):
    watch_list[mint] = False


def start():

    def worker():

        while True:

            for mint in list(watch_list.keys()):

                if watch_list[mint]:
                    continue

                lp = check_lp(mint)

                if lp:

                    print(f"LP bulundu : {mint}")

                    watch_list[mint] = True

            time.sleep(3)

    threading.Thread(
        target=worker,
        daemon=True
    ).start()
