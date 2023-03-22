import socket
import argparse


class Emulator:
    def __init__(self, port: int, queue_size: int, filename: str, log_name: str) -> None:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Emulator")
    parser.add_argument(
        "-p",
        help="the port of the emulator",
        type=int,
        required=True
    )
    parser.add_argument(
        "-q",
        help="the size of each of the three queues",
        type=int,
        required=True
    )
    parser.add_argument(
        "-f",
        help="the name of the file containing the static forwarding table in the format specified above",
        type=str,
        required=True
    )
    parser.add_argument(
        "-l",
        help="the name of the log file",
        type=str,
        required=True
    )

    args = parser.parse_args()
    # initialize Emulator
