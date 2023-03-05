import argparse
import socket
import struct
import math
import time
from typing import Literal
from datetime import datetime


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
            packet, req_addr = self.sock.recvfrom(8192)
            self.requester_address = req_addr[0]
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
        sequence_nos = []
        if filesize <= self.length:
            headers.append(
                struct.pack(
                    "!cII", "D".encode(), socket.htonl(self.sequence_no), filesize
                )
            )
            sequence_nos.append(self.sequence_no)
            self.sequence_no += filesize
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
                    sequence_nos.append(self.sequence_no)
                    self.sequence_no += last_payload_length
                else:
                    headers.append(
                        struct.pack(
                            "!cII",
                            "D".encode(),
                            socket.htonl(self.sequence_no),
                            self.length,
                        )
                    )
                    sequence_nos.append(self.sequence_no)
                    self.sequence_no += self.length

        file_parts = []
        for i in range(len(headers)):
            file_parts.append(content[i * self.length : (i + 1) * self.length])

        header_and_payload = [
            header + payload for header, payload in zip(headers, file_parts)
        ]

        # send the packets with rate limit, don't need to wait for ACK
        for i in range(len(header_and_payload)):
            self.sock.sendto(
                header_and_payload[i], (self.requester_address, self.requester_port)
            )
            self.log_info("D", sequence_nos[i], file_parts[i])
            time.sleep(1 / self.rate)

        # send END packet
        self.sock.sendto(
            struct.pack("!cII", "E".encode(), socket.htonl(self.sequence_no), 0),
            (self.requester_address, self.requester_port),
        )
        self.log_info("E", self.sequence_no, b"")

    def log_info(self, type: Literal["D", "E"], seq: int, payload: bytes) -> None:
        if type == "D":
            print(f"-----DATA Packet-----")
            print(f"send time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"requester addr: {self.requester_address}: {self.requester_port}")
            print(f"Sequence num: {seq}")
            print(f"payload: {payload[:4].decode()}")
            print(f"---------------------")
        elif type == "E":
            print(f"-----END Packet------")
            print(f"send time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"requester addr: {self.requester_address}: {self.requester_port}")
            print(f"Sequence num: {seq}")
            print(f"payload: {payload.decode()}")
            print(f"---------------------")


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
