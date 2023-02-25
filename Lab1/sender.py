import argparse
import socket
import struct
import math


class Sender:
    def __init__(
        self, port: int, req_port: int, rate: int, seq_no: int, length: int
    ) -> None:
        self.listen_port = port
        self.requester_port = req_port
        self.requester_address = None
        self.rate = rate
        self.sequence_no = seq_no
        self.length = length
        self.UDP_IP = "127.0.0.1"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.UDP_IP, self.listen_port))
        self.sock.settimeout(60)
        self.listen_to_request()

    def listen_to_request(self) -> None:
        try:
            print(f"[Info] Waiting for request on port {self.listen_port}")
            packet, req_addr = self.sock.recvfrom(8192)
            self.requester_address = req_addr
            header = packet[:9]
            payload = packet[9:]
            headers = struct.unpack("!cII", header)
            request_type, file_requested = headers[0].decode(), payload.decode()
            if request_type != "R":
                print(
                    f"[Error] Should get a request with request type 'R', but got {request_type} instead."
                )
            self.send_file(file_requested)
        except TimeoutError:
            print("[Error] Waited too long for the request, exiting...")

    def send_file(self, filename: str) -> None:
        # read in the requested file
        content = b""
        with open(filename, "r") as f:
            content = f.read().encode()
        filesize = len(content)

        headers = []
        if filesize <= self.length:
            headers.append(
                struct.pack(
                    "!cII", "D".encode(), socket.htonl(self.sequence_no), filesize
                )
            )
        else:
            num_packets = math.ceil(filesize / self.length)
            last_payload_length = filesize % self.length
            for i in range(num_packets):
                if i == num_packets - 1:
                    # last packet
                    headers.append(
                        struct.pack(
                            "!cII",
                            "D".encode(),
                            socket.htonl(self.sequence_no),
                            last_payload_length,
                        )
                    )
                headers.append(
                    struct.pack(
                        "!cII",
                        "D".encode(),
                        socket.htonl(self.sequence_no),
                        self.length,
                    )
                )
                self.sequence_no += i * self.length
        print(headers)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send packets")
    # use argparse to parse arguments
    parser.add_argument(
        "-p",
        help="The port on which the sender waits for requests",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-g", help="The port on which the requester is waiting", type=int, required=True
    )
    parser.add_argument(
        "-r",
        help="The number of packets to be sent per second",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-q",
        help="The initial sequence of the packet exchange",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-l",
        help="The length of the payload (in bytes) in the packets",
        type=int,
        required=True,
    )
    args = parser.parse_args()

    sender = Sender(args.p, args.g, args.r, args.q, args.l)
