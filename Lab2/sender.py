import argparse
import socket
import struct
import math
import time
from typing import Literal
from datetime import datetime
STRUCT_FORMAT = "!cIHIHI"

class Sender:
    def __init__(
        self, port: int, req_port: int, rate: int, seq_no: int, length: int, priority: int, \
            host_name: str, host_port: int, timeout:int 
    ) -> None:
        self. total_packet_sent = 0
        self.total_retransmit = 0
        self.listen_port = port
        self.requester_port = req_port
        self.requester_address = None
        self.rate = rate
        self.sequence_no = 1
        self.length = length
        self.UDP_IP = "127.0.0.1"
        self.priority = priority
        self.host_name = host_name
        self.host_port = host_port
        self.timeout = timeout
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.UDP_IP, self.listen_port))
        self.sock.settimeout(60)
        self.listen_to_request()

    def listen_to_request(self) -> None:
        try:
            packet, req_addr = self.sock.recvfrom(8192)
            self.requester_address = req_addr[0]
            outterHeader = packet[:17]
            outterPayload = packet[17:]
            header = outterPayload[:9]
            payload = outterPayload[9:]
            headers = struct.unpack("!cII", header)
            outterHeaders = struct.unpack(STRUCT_FORMAT, outterHeader)
            priority, src_addr, src_port, dest_addr, dest_port,length = outterHeaders[0].decode(), \
                outterHeaders[1:5].decode(),outterHeaders[5:7].decode(), outterHeaders[7:11].decode(), \
                outterHeaders[11:13].decode(), outterHeaders[13:17].decode()
            request_type, file_requested, window_size = headers[0].decode(), payload.decode(),headers[5:].decode()
            if request_type != "R":
                print(
                    f"[Error] Should get a request with request type 'R', but got {request_type} instead."
                )
            self.send_file(file_requested, priority, src_addr, src_port, dest_addr, dest_port, length, window_size)
        except TimeoutError:
            print("[Error] Waited too long for the request, exiting...")

    def send_file(self, filename: str, priority: int, src_addr: int, src_port: int, \
        dest_addr: int, dest_port: int, length: int, window_size:int) -> None:
        # read in the requested file
        content = b""
        with open(filename, "r") as f:
            content = f.read().encode()
        filesize = len(content)

        headers = []
        sequence_nos = []
        innerheaders = []
        if filesize <= self.length:
            innerheader = struct.pack(
                    "!cII", "D".encode(), socket.htonl(self.sequence_no), filesize)
            headers.append(
                    struct.pack(STRUCT_FORMAT, socket.htonl(self.priority),socket.htonl(dest_addr), socket.htonl(dest_port), \
                        socket.htonl(src_addr),socket.htonl(src_port), len(innerheader))
            )
            sequence_nos.append(self.sequence_no)
            innerheaders.append(innerheader)
            self.sequence_no += 1
        else:
            num_packets = math.ceil(filesize / self.length)
            last_payload_length = filesize % self.length
            for i in range(num_packets):
                if i == num_packets - 1:
                    # last packet
                    innerheader = struct.pack(
                            "!cII", "D".encode(), socket.htonl(self.sequence_no), last_payload_length)
                    headers.append(
                        struct.pack(STRUCT_FORMAT, socket.htonl(self.priority),socket.htonl(dest_addr), socket.htonl(dest_port), \
                            socket.htonl(src_addr),socket.htonl(src_port), len(innerheader))
                    )
                    sequence_nos.append(self.sequence_no)
                    self.sequence_no += 1
                    innerheaders.append(innerheader)
                else:
                    innerheader = struct.pack(
                            "!cII", "D".encode(), socket.htonl(self.sequence_no), self.length)
                    headers.append(
                        struct.pack(STRUCT_FORMAT, socket.htonl(self.priority),socket.htonl(dest_addr), socket.htonl(dest_port), \
                            socket.htonl(src_addr),socket.htonl(src_port), len(innerheader))
                    )
                    sequence_nos.append(self.sequence_no)
                    self.sequence_no += 1
                    innerheaders.append(innerheader)

        file_parts = []
        for i in range(len(headers)):
            file_parts.append(content[i * self.length : (i + 1) * self.length])

        header_and_payload = [
            header + innerheader + payload for header, innerheader, payload in zip(headers, innerheaders,file_parts)
        ]

        # send the packets with rate limit, don't need to wait for ACK
        for i in range(len(header_and_payload)):
            self.sock.sendto(
                header_and_payload[i], (self.requester_address, self.host_port)
            )
            self.total_packet_sent +=1
            trial = 1
            ack = False
            while trial <=5 and ack == False:
                try:
                    self.sock.settimeout(self.timeout)
                    packet, _ = self.sock.recvfrom(8192)
                    self.sock.settimeout(None)
                    outterPayload = packet[17:]
                    header = outterPayload[:9]
                    headers = struct.unpack("!cII", header)
                    request_type, seq_no = headers[0].decode(),headers[1:5].decode()
                    if request_type != "A":
                        print(
                            f"[Error] Should get a ack packet with request type 'A', but got {request_type} instead."
                            )
                    elif seq_no != i+1:
                        print(
                            f"[Error] Wrong sequnence number in ack packet, should be {i+1}, but got {request_type} instead."
                            )
                    else:
                        ack = True
                except TimeoutError:
                    self.sock.sendto(
                        header_and_payload[i], (self.requester_address, self.host_port)
                    )
                    self.total_retransmit +=1
                    self.total_packet_sent +=1
                    trial +=1
            if trial > 5 and ack == False:
                print(
                    f"[Error] transmission failed for packet with sequnence number {i+1}, moving to next packet."
                )
                        
            time.sleep(1 / self.rate)

        # send END packet
        finalInner = struct.pack("!cII", "E".encode(), socket.htonl(self.sequence_no), 0)
        self.sock.sendto(
             struct.pack(STRUCT_FORMAT, socket.htonl(self.priority),socket.htonl(dest_addr), socket.htonl(dest_port), \
                            socket.htonl(src_addr),socket.htonl(src_port), len(innerheader)) + finalInner,
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
    parser.add_argument(
        "-f",
        help="The host name of the emulator",
        type=str,
        required=True,
    )
    parser.add_argument(
        "-e",
        help="The port of the emulator",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-i",
        help="The priority of the sent packets",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-t",
        help="The timeout for retransmission for lost packets in the unit of milliseconds",
        type=int,
        required=True,
    )
    args = parser.parse_args()

    sender = Sender(args.p, args.g, args.r, args.q, args.l, args.f, args.e, args.i, args.t)
