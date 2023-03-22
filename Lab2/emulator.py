import socket
import argparse
import struct
from typing import List, Tuple, Union
from collections import deque

Table_Entry = Tuple[Tuple, Tuple, int, int]
STRUCT_FORMAT = "!cIHIHI"


# Write our own wrapper class for the queue
class NetworkQueue:
    def __init__(self, queue_size: int) -> None:
        self.queue_size = queue_size
        self.queue = deque()

    def __len__(self) -> int:
        return len(self.queue)

    def enqueue(self, packet: bytes) -> None:
        if len(self.queue) < self.queue_size:
            self.queue.appendleft(packet)
        else:
            raise Exception("Queue is full")

    def dequeue(self) -> Union[bytes, None]:
        if len(self.queue) > 0:
            return self.queue.pop()
        else:
            return None


class Emulator:
    def __init__(
        self, port: int, queue_size: int, filename: str, log_name: str
    ) -> None:
        self.filename = filename
        self.port = port
        self.queue_size = queue_size
        self.log_name = log_name

        # format: (destination, next_hop, delay, loss_prob)
        self.forwarding_table = self.read_forwarding_table()

        self.high_priority_queue = NetworkQueue(self.queue_size)
        self.medium_priority_queue = NetworkQueue(self.queue_size)
        self.low_priority_queue = NetworkQueue(self.queue_size)

    def read_forwarding_table(self) -> List[Table_Entry]:
        entries: List[Table_Entry] = []
        # read the forwarding table
        with open(self.filename, "r") as f:
            for line in f:
                # Find our own emulator
                # TODO: not sure if this is the right way to do it
                if (
                    line
                    and socket.gethostbyname(line.split(" ")[0]) == "127.0.0.1"
                    and line.split(" ")[1] == str(self.port)
                ):
                    line = line.split(" ")
                    destination = (line[2], line[3])
                    next_hop = (line[4], line[5])
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Emulator")
    parser.add_argument("-p", help="the port of the emulator", type=int, required=True)
    parser.add_argument(
        "-q", help="the size of each of the three queues", type=int, required=True
    )
    parser.add_argument(
        "-f",
        help="the name of the file containing the static forwarding table in the format specified above",
        type=str,
        required=True,
    )
    parser.add_argument("-l", help="the name of the log file", type=str, required=True)

    args = parser.parse_args()
    # initialize Emulator
    Emulator(args.p, args.q, args.f, args.l)
