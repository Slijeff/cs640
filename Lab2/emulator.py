import socket
import argparse
import struct
from typing import List, Tuple, Union
from collections import deque
from time import time
import logging

Address = Tuple[str, int]
Table_Entry = Tuple[Tuple, Tuple, int, int]
Queue_Entry = Tuple[bytes, float, Address, Address]
STRUCT_FORMAT = "!cIHIHI"


# Write our own wrapper class for the queue
class NetworkQueue:
    def __init__(self, queue_size: int) -> None:
        self.queue_size = queue_size
        self.queue = deque()

    def __len__(self) -> int:
        return len(self.queue)

    def enqueue(self, packet: bytes, dest: Address, hop: Address) -> None:
        if len(self.queue) < self.queue_size:
            # includes current time when enqueuing in miliseconds
            self.queue.appendleft((packet, time() * 1000, dest, hop))
        else:
            raise Exception("Queue is full")

    def dequeue(self) -> Union[Queue_Entry, None]:
        if len(self.queue) > 0:
            return self.queue.pop()
        else:
            return None

    def peek(self) -> Union[Queue_Entry, None]:
        return self.queue[-1] if len(self.queue) > 0 else None


class Emulator:
    def __init__(
        self, port: int, queue_size: int, filename: str, log_name: str
    ) -> None:
        self.filename = filename
        self.port = port
        self.queue_size = queue_size
        self.log_name = log_name
        self.UDP_IP = "127.0.0.1"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.UDP_IP, self.port))
        # making it non-blocking
        self.sock.setblocking(False)
        self.currently_delaying: Queue_Entry = None

        # format: (destination, next_hop, delay, loss_prob)
        self.forwarding_table = self.read_forwarding_table()

        self.high_priority_queue = NetworkQueue(self.queue_size)
        self.medium_priority_queue = NetworkQueue(self.queue_size)
        self.low_priority_queue = NetworkQueue(self.queue_size)
        self.end_packet_queue = NetworkQueue(self.queue_size)

        logging.basicConfig(
            format='[%(asctime)s]\t%(message)s', filename=self.log_name, level=logging.DEBUG)
        logging.info("Emulator started on port %d", self.port)

        self.start()

    def read_forwarding_table(self) -> List[Table_Entry]:
        entries: List[Table_Entry] = []
        # read the forwarding table
        with open(self.filename, "r") as f:
            for line in f:
                # Find our own emulator
                if (
                    line
                    and socket.gethostname() == line.split(" ")[0]
                    and line.split(" ")[1] == str(self.port)
                ):
                    line = line.split(" ")
                    destination = (line[2], int(line[3]))
                    next_hop = (line[4], int(line[5]))
                    delay = int(line[6])
                    loss_prob = int(line[7])
                    entries.append((destination, next_hop, delay, loss_prob))
                else:
                    continue
        return entries

    def route_packet(self, incoming_packet: bytes) -> None:

        # unpack the packet
        header = incoming_packet[:17]
        payload = incoming_packet[17:]
        priority, src_addr, src_port, dest_addr, dest_port, length = struct.unpack(
            STRUCT_FORMAT, header
        )

        destination = (dest_addr, int(dest_port))

        if not self.lookup_by_destination(destination):
            self.log("No forwarding entry found", src_addr, src_port,
                     dest_addr, dest_port, priority, length)

        try:
            if priority == 1:
                self.high_priority_queue.enqueue(
                    incoming_packet, destination, self.lookup_by_destination(destination))
            elif priority == 2:
                self.medium_priority_queue.enqueue(
                    incoming_packet, destination, self.lookup_by_destination(destination))
            elif priority == 3:
                self.low_priority_queue.enqueue(
                    incoming_packet, destination, self.lookup_by_destination(destination))
        except:
            # test if is END packet
            packet_type, seq, _ = struct.unpack("!cII", payload)
            if packet_type == b"E":
                self.end_packet_queue.enqueue(
                    incoming_packet, destination, self.lookup_by_destination(destination))

            self.log(f"Dropped because queue {priority} is full",
                     src_addr, src_port, dest_addr, dest_port, priority, length)

        # get a packet from the queues if there's no currently delayed packet
        if not self.currently_delaying:
            for Q in [self.high_priority_queue, self.medium_priority_queue, self.low_priority_queue]:
                if Q.peek():
                    self.currently_delaying = Q.dequeue()
                    break
        else:
            # decide if the delay is over and should be forwarded
            if time() * 1000 - self.currently_delaying[1] <= self.lookup_by_destination(self.currently_delaying[2]):
                # forward
                self.sock.sendto(
                    self.currently_delaying[0], self.currently_delaying[3])
                self.currently_delaying = None

    def lookup_by_destination(self, destination: Address) -> Union[Table_Entry, None]:
        """Returns the routing table entry that has the given destination address.

        If there is no such entry, returns None.

        """
        for e in self.forwarding_table:
            if destination == e[0]:
                return e
        return None

    def log(self, message: str, src_addr: str, src_port: int, dest_addr: str, dest_port: int, priority: int, payload_size: int) -> None:
        logging.info("%s\t[src-%s:%d, dst-%s:%d, priority-%d, payload_size-%d]",
                     message, src_addr, src_port, dest_addr, dest_port, priority, payload_size)

    def start(self) -> None:
        while 1:
            try:
                packet, sender_addr = self.sock.recvfrom(8192)
                self.route_packet(packet)
            except:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Emulator")
    parser.add_argument("-p", help="the port of the emulator",
                        type=int, required=True)
    parser.add_argument(
        "-q", help="the size of each of the three queues", type=int, required=True
    )
    parser.add_argument(
        "-f",
        help="the name of the file containing the static forwarding table in the format specified above",
        type=str,
        required=True,
    )
    parser.add_argument("-l", help="the name of the log file",
                        type=str, required=True)

    args = parser.parse_args()
    # initialize Emulator
    Emulator(args.p, args.q, args.f, args.l)
