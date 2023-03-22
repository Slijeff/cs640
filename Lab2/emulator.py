import socket
import argparse
from typing import List, Tuple, Union


class Emulator:
    def __init__(self, port: int, queue_size: int, filename: str, log_name: str) -> None:
        self.filename = filename
        self.port = port
        self.queue_size = queue_size
        self.log_name = log_name

        dest, next_hop, delay, prob = self.read_forwarding_table()
        print(dest, next_hop, delay, prob)

    def read_forwarding_table(self) -> Tuple[Tuple, Tuple, int, int]:
        destination = next_hop = delay = loss_prob = None
        # read the forwarding table
        with open(self.filename, "r") as f:
            for line in f:
                # Find our own emulator
                # TODO: not sure if this is the right way to do it
                if line and socket.gethostbyname(line.split(" ")[0]) == "127.0.0.1":
                    line = line.split(" ")
                    destination = (line[2], line[3])
                    next_hop = (line[4], line[5])
                    delay = int(line[6])
                    loss_prob = int(line[7])
                    break
                else:
                    continue

        return destination, next_hop, delay, loss_prob


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
    Emulator(args.p, args.q, args.f, args.l)
