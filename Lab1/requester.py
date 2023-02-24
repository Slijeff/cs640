import argparse
import socket


class Requester:
    def __init__(self, port: str, filename: str) -> None:
        self.UDP_PORT = 1234
        self.UDP_IP = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.UDP_IP, self.UDP_PORT))
        self.filename = filename


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Request packets")
    # use argparse to parse arguments
    parser.add_argument(
        "-p", help="The port on which the requester waits for packets", type=str
    )
    parser.add_argument(
        "-o", help="The name of the file that is being requested", type=str
    )
    args = parser.parse_args()
    requester = Requester(args.p, args.o)
