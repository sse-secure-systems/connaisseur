import inspect
import logging

from time import perf_counter


class Timings:
    __instance = None
    timings = []

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super(Timings, cls).__new__(cls)
        return cls.__instance

    def reset(self):
        self.timings = []

    def add(self, timing: str):
        self.timings.append(timing)


def timing(capture_args: list = None):
    def inner(f):
        def wrapper(*args, **kwargs):
            timings = Timings()

            ts = perf_counter()
            result = f(*args, **kwargs)
            te = perf_counter()

            if logging.root.level == logging.DEBUG:
                extra = []
                if capture_args:
                    signature = inspect.signature(f)
                    for capture_arg in capture_args:
                        for idx, sig_arg in enumerate(signature.parameters):
                            if str(sig_arg) == capture_arg:
                                if len(args) >= idx:
                                    extra.append(f"{sig_arg}: {args[idx]}")
                                elif kwargs.get(sig_arg):
                                    extra.append(f"{sig_arg}: {kwargs.get(sig_arg)}")

                timings.add(
                    f"{f.__name__}: {te-ts:2.6f} sec {f'({extra})' if extra else ''}"
                )
            return result

        return wrapper

    return inner
