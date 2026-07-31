def on_message(self, ws, message):

    print("GELEN VERİ:")
    print(message)

    try:
        data = json.loads(message)
        self.callback(data)

    except Exception as e:
        print(e)
