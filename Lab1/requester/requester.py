import argparse
import socket
from collections import defaultdict
from typing import DefaultDict, Tuple, List
import struct
from typing import Literal
from datetime import datetime
import time

class Requester:
    def __init__(self, port: int, filename: str) -> None:
        self.receive_port = port
        self.UDP_IP = "127.0.0.1"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.UDP_IP, self.receive_port))
        self.filename = filename
        self.tracker_info = self.read_tracker()

        self.send_request()

    def read_tracker(self) -> DefaultDict[str, List[Tuple[int, str, int]]]:
        info = defaultdict(list)
        with open("tracker.txt", "r") as f:
            for line in f:
                line = line.replace("\n", "").split(" ")
                info[line[0]].append(
                    (int(line[1]), socket.gethostbyname(line[2]), int(line[3]))
                )

        # format: {filename: [(ID, hostname, port), (ID, hostname, port)]} sorted by ID
        for v in info.values():
            v.sort(key=lambda x: x[0])

        return info

    def send_request(self) -> None:
        header = struct.pack("!cII", "R".encode(), 0, 0)
        for dest in self.tracker_info[self.filename]:
            self.sock.sendto(
                header + self.filename.encode(),
                (
                    dest[1],
                    dest[2],
                ),
            )
            print(f"[Info] Sent to {dest[1]} at port {dest[2]}")
            self.receive_file(dest[1], dest[2])
    
    def receive_file(self,sender_address,sender_port) -> None:
        startTime = time.time()
        Data_packet_num = 0
        total_byte = 0        
        packet, req_addr = self.sock.recvfrom(8192)
        with open(self.filename,'a') as file:
            header = packet[:9]
            payload = packet[9:]
            headers = struct.unpack("!cII", header)
            request_type, sequence, length, file_content = headers[0].decode(), socket.htonl(headers[1]), \
                headers[2], payload
            if request_type != "D":
                print(
                    f"[Error] first packet recived should be a request with request type 'D', but got {request_type} instead."
                )
            while request_type!="E":
                try:
                    self.log_info(sender_address, sender_port, "D", sequence, length, file_content)
                    file.write(file_content.decode())
                    Data_packet_num += 1
                    total_byte += length
                    self.sock.settimeout(60)
                    packet, req_addr = self.sock.recvfrom(8192)
                    self.sock.settimeout(None)
                    header = packet[:9]
                    payload = packet[9:]
                    headers = struct.unpack("!cII", header)
                    request_type, sequence, length, file_content = headers[0].decode(), socket.htonl(headers[1]), \
                        headers[2], payload
                except TimeoutError:
                    print("[Error] Waited too long for the request, exiting...")
                    exit()
                    
        self.log_info(sender_address, sender_port, "E", sequence, length, b"")
        duration = int((time.time() - startTime) *1000)
        avg_packet = int((duration/1000)/Data_packet_num)
        self.log_Summary(sender_address, sender_port,Data_packet_num,total_byte,duration,avg_packet)
                

    def log_info(self, sender_address: str, sender_port:str, type: Literal["D", "E"], seq: int, length:int, payload: bytes) -> None:
        if type == "D":
            print(f"-----DATA Packet-----")
            print(f"recv time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"sender addr: {sender_address}: {sender_port}")
            print(f"Sequence num: {seq}")
            print(f"length:: {length}")
            print(f"payload: {payload[:4].decode()}")
            print(f"---------------------")
        elif type == "E":
            print(f"-----END Packet------")
            print(f"recv time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"sender addr: {sender_address}: {sender_port}")
            print(f"Sequence num: {seq}")
            print(f"length:: {length}")
            print(f"payload: {payload.decode()}")
            print(f"---------------------")
            
    def log_Summary(self, sender_address: str, sender_port:str, Data_packet_num: int, total_byte:int, duration: int, avg_packet: int) -> None:
        print("Summary")
        print(f"sender addr: {sender_address}: {sender_port}")
        print(f"Total Data packets: {Data_packet_num}")
        print(f"total Data bytes: {total_byte}")
        print(f"Average packets/second: {avg_packet}")
        print(f"Duration of the test: {duration}ms")
            
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Request packets")
    # use argparse to parse arguments
    parser.add_argument(
        "-p",
        help="The port on which the requester waits for packets",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-o",
        help="The name of the file that is being requested",
        type=str,
        required=True,
    )
    args = parser.parse_args()
    requester = Requester(args.p, args.o)
