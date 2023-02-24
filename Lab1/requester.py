import argparse
import socket
from collections import defaultdict


class Requester:
    def __init__(self, port: int, filename: str) -> None:
        self.receive_port = port
        self.UDP_IP = "127.0.0.1"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.UDP_IP, self.receive_port))
        self.filename = filename
        self.tracker_info = self.read_tracker()

    def read_tracker(self) -> defaultdict:
        info = defaultdict(list)
        with open("tracker.txt", "r") as f:
            for line in f:
                line = line.replace("\n", "").split(" ")
                info[line[0]].append((int(line[1]), line[2], line[3]))

        # format: {filename: [(ID, hostname, port), (ID, hostname, port)]} sorted by ID
        for v in info.values():
            v.sort(key=lambda x: x[0])

        return info


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Request packets")
    # use argparse to parse arguments
    parser.add_argument(
        "-p", help="The port on which the requester waits for packets", type=int
    )
    parser.add_argument(
        "-o", help="The name of the file that is being requested", type=str
    )
    args = parser.parse_args()
    requester = Requester(args.p, args.o)
