import argparse
import socket
from collections import defaultdict
from typing import DefaultDict, Tuple, List
import struct
from typing import Literal
from datetime import datetime
import time
STRUCT_FORMAT = "!cIHIHI"

class Requester:
    def __init__(self, port: int, filename: str, host_name: str, host_port: int, \
        window: int) -> None:
        self.receive_port = port
        self.UDP_IP = socket.gethostbyname(socket.gethostname())
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.UDP_IP, self.receive_port))
        self.filename = filename
        self.host_name = host_name
        self.host_port = host_port
        self.window = window
        self.tracker_info = self.read_tracker()
        self.sender_ports = []

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
        for dest in self.tracker_info[self.filename]:
            print(self.window)
            innerheader = struct.pack("!cII", "R".encode(), 0, self.window)
            send_addr = int.from_bytes(socket.inet_aton(self.UDP_IP), byteorder='big')
            recv_addr = int.from_bytes(socket.inet_aton(dest[1]), byteorder='big')
            header = struct.pack(STRUCT_FORMAT, "1".encode(),send_addr, self.receive_port, \
                        recv_addr,dest[2], len(innerheader))
            self.sock.sendto(
                header + innerheader + self.filename.encode(),
                (
                    dest[1],
                    self.host_port
                ),
            )
            self.receive_file(dest[1], dest[2])

    def receive_file(self, sender_address, sender_port) -> None:
        startTime = time.time()
        Data_packet_num = 0
        total_byte = 0
        log_store =[]
        with open(self.filename, "a") as file:
            request_type = "D"
            while request_type != "E":
                packet, req_addr = self.sock.recvfrom(8192)
                outterHeader = packet[:17]
                _, src_addr, src_port, dest_addr, dest_port,_ = struct.unpack(STRUCT_FORMAT, outterHeader)
                src_addr = socket.inet_ntoa(src_addr.to_bytes(4, byteorder='big'))
                dest_addr = socket.inet_ntoa(dest_addr.to_bytes(4, byteorder='big'))
                print(dest_addr)
                if dest_addr!= self.UDP_IP:
                    print("Received Packet dest addr not consistent with self address, expect ",self.UDP_IP,\
                        "received" , dest_addr)
                else:
                    self.sender_ports.append(req_addr[0])
                    outterPayload = packet[17:]
                    header = outterPayload[:9]
                    payload = outterPayload[9:]
                    headers = struct.unpack("!cII", header)
                    request_type, sequence, length, file_content = (
                        headers[0].decode(),
                        socket.htonl(headers[1]),
                        headers[2],
                        payload,
                    )
                    if Data_packet_num == 0 and request_type != "D":
                        print(
                            f"[Error] first packet recived should be a request with request type 'D', but got {request_type} instead."
                        )
                    
                    #send ACK
                    innerheader = struct.pack("!cII", "A".encode(), socket.htonl(sequence), 0)
                    outerheader = struct.pack(STRUCT_FORMAT, "1".encode(),int.from_bytes(socket.inet_aton(dest_addr), byteorder='big'), dest_port, \
                            int.from_bytes(socket.inet_aton(src_addr), byteorder='big'),src_port, len(innerheader))
                    self.sock.sendto(
                        outerheader+innerheader, (socket.gethostbyname(self.host_name), self.host_port) 
                    )
                    file.write(file_content.decode())
                    Data_packet_num += 1
                    total_byte += length
                    log_store.append([sender_address, sender_port, "D", sequence, length, file_content])

        for loginfo in log_store:
            self.log_info(loginfo[0],loginfo[1],loginfo[2],loginfo[3],loginfo[4],loginfo[5])
            
        self.log_info(sender_address, sender_port, "E", sequence, length, b"")
        duration = int((time.time() - startTime) * 1000)
        avg_packet = round(Data_packet_num / (duration / 1000))
        self.log_Summary(
            sender_address,
            sender_port,
            Data_packet_num,
            total_byte,
            duration,
            avg_packet,
        )

    def log_info(
        self,
        sender_address: str,
        sender_port: str,
        type: Literal["D", "E"],
        seq: int,
        length: int,
        payload: bytes,
    ) -> None:
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

    def log_Summary(
        self,
        sender_address: str,
        sender_port: str,
        Data_packet_num: int,
        total_byte: int,
        duration: int,
        avg_packet: int,
    ) -> None:
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
        "-w",
        help="the requester's window size",
        type=int,
        required=True,
    )
    args = parser.parse_args()
    requester = Requester(args.p, args.o, args.f, args.e, args.w)
