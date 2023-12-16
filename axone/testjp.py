from multiprocessing import Process


class ClassA:
    def __init__(self):
        self.class_b = ClassB(self.callback)

    def callback(self, data):
        print(f"Callback in ClassA called with data: {data}")


class ClassB:
    def __init__(self, callback):
        self.callback = callback
        self.process = Process(target=self.run)
        self.process.start()

    def run(self):
        print("Running in a separate process")
        data = "Hello from ClassB"
        self.callback(data)

    def join(self):
        self.process.join()


if __name__ == "__main__":
    a = ClassA()
    a.class_b.join()
