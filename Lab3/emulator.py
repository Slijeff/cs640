import socket
from dataclasses import dataclass
import pickle
import time
import argparse
from typing import Dict, List, Optional, Set, Tuple, Literal
from collections import defaultdict, deque

Address = Tuple[str, int]


@dataclass
class Message:
    source: Address
    packet_type: Literal["HELLO", "LSM", "TRACE"]
    seq_num: Optional[int] = None
    ttl: Optional[int] = None
    # since the cost is always 1, we only send adjacent nodes
    neighbors: Optional[Set[Address]] = None
    destination: Optional[Address] = None

    def to_bytes(self) -> bytes:
        return pickle.dumps(self)


class NeighborList:
    def __init__(self, neighbors: Set[Address], timeout: float) -> None:
        self.neighbors: List[Tuple[Address, float]] = []
        self.timeout = timeout

        for n in neighbors:
            self.neighbors.append((n, time.time()))

    def record_neighbor(self, neighbor: Address) -> Tuple[Address, Literal["UP"]] | None:
        if neighbor not in self.neighbors:
            # a neighbor is online
            self.neighbors.append((neighbor, time.time()))
            return (neighbor, 'UP')
        else:
            old = None
            for entry in self.neighbors:
                if entry[0] == neighbor:
                    old = entry
            assert old != None
            self.neighbors.remove(old)
            self.neighbors.append((neighbor, time.time()))

    def check_timeout(self) -> Tuple[Address, Literal["DOWN"]] | None:
        for entry in self.neighbors:
            if time.time() - entry[1] > self.timeout:
                self.neighbors.remove(entry)
                return (entry[0], "DOWN")


class Emulator:
    def __init__(self, port: int, filename: str) -> None:
        self.port = port
        self.topo_file = filename

        # a list of (ip, port) pair that indicates the neighbors
        self.neighbors: List[Address] = []

        self.ip = socket.gethostbyname(socket.gethostname())
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.ip, self.port))
        self.sock.setblocking(False)

        # for testing purpose
        # self.ip = '2.0.0.0'

        self.address = (self.ip, self.port)
        self.lsp_interval = 0.5  # in seconds
        self.hello_interval = 0.5  # timeout for neighbor nodes
        self.sequence_no = 0
        # maps (dst_addr, dst_ip) to (next_hop_addr, next_hop_ip)
        self.forwarding_table: Dict[Address, Address] = {}
        self.all_nodes_except_self: List[Address] = []
        self.adj_list: Dict[Address, Set[Address]] = defaultdict(set)
        self.sequence_tracking: Dict[Address, int] = defaultdict(int)

        self.read_topology()
        self.neighbor_list = NeighborList(
            set(self.neighbors), self.hello_interval)
        self.build_forwarding_table()

    def read_topology(self) -> None:
        topology = []
        with open(self.topo_file, 'r') as f:
            for line in f:
                # find itself in the topo_file
                line = line.split(' ')
                line = [x.replace('\n', '').split(',') for x in line]
                line = [(x[0], int(x[1])) for x in line]
                # add to adjacency list
                self.adj_list[line[0]] |= set(line[1:])
                # add to topology
                if not topology and line[0][0] == self.ip and line[0][1] == self.port:
                    topology = line[1:]
                # record all other nodes in the network except itself
                else:
                    self.sequence_tracking[line[0]] = 0
                    self.all_nodes_except_self.append(line[0])

        assert topology != []
        self.neighbors = topology

    def update_adj_list(self, msg: Message) -> bool:
        """
        returns True if adjacency list changed, False if nothing changed
        """
        assert msg.seq_num != None, "For Link State packet, sequence number must be present"
        assert msg.neighbors != None, "For Link State packet, neighbor list must be present"
        assert msg.source in self.adj_list, "Source node not in topology file"

        if self.sequence_tracking[msg.source] >= msg.seq_num:
            return False

        old = self.adj_list[msg.source]
        new = msg.neighbors

        if new:
            if old == new:
                self.sequence_tracking[msg.source] = msg.seq_num
                return False
            else:
                self.sequence_tracking[msg.source] = msg.seq_num
                self.adj_list[msg.source] = new

        return True

    def build_forwarding_table(self) -> None:
        for node in self.all_nodes_except_self:
            self.forwarding_table[node] = self.forward_search(self.address, node)[
                1]

    def forward_search(self, start: Address, goal: Address) -> List[Address]:
        frontier = deque([(start, [start])])
        visited: Set[Address] = set()

        while frontier:
            current, path = deque.popleft(frontier)
            visited.add(current)

            for neighbor in self.adj_list[current]:
                if neighbor == goal:
                    return path + [neighbor]
                elif neighbor not in visited:
                    frontier.append((neighbor, path + [neighbor]))

        return []

    def send_msg(self, msg: Message, dest: Address) -> None:
        # self.sock.sendto(msg.to_bytes(), dest)
        pass

    def broadcast_to_neighbors(self, msg: Message) -> None:
        for neighbor in self.adj_list[self.address]:
            self.send_msg(msg, neighbor)

    def emulate_once(self, msg: Message) -> None:
        # If message is HELLO
        if msg.packet_type == "HELLO":
            self.neighbor_list.record_neighbor(msg.source)
        # If message is Link State
        elif msg.packet_type == "LSM":
            assert msg.ttl != None, "For Link State packet, ttl must be present"
            if msg.ttl > 0:
                if self.update_adj_list(msg):
                    self.build_forwarding_table()
                msg.ttl -= 1
                self.broadcast_to_neighbors(msg)

        # If message is Traceroute
        elif msg.packet_type == "TRACE":

            assert msg.destination != None, "For Traceroute packet, the destination must be present"
            assert msg.ttl != None, "For Traceroute packet, the ttl must be present"

            if msg.ttl > 0:
                # forward it
                msg.ttl -= 1
                self.send_msg(msg, self.forwarding_table[msg.destination])
            else:
                # change the source to itself and dest to source
                originator = msg.source
                msg.destination = originator
                msg.source = self.address
                msg.ttl = 999
                # forward it
                self.send_msg(msg, self.forwarding_table[msg.destination])

        # Check if any neighbor is dead
        result = self.neighbor_list.check_timeout()
        if result:
            # Send new link state message and rebuild forwarding_table
            self.adj_list[self.address].remove(result[0])
            self.broadcast_to_neighbors(
                Message(
                    source=self.address,
                    packet_type='LSM',
                    seq_num=self.sequence_no + 1,
                    ttl=25,  # maximum of 20 nodes, put 25 just to be safe
                    neighbors=self.adj_list[self.address]
                )
            )
            self.sequence_no += 1
            self.build_forwarding_table()
        
    def emulate(self) -> None:
        while 1:
            try:
                packet, _ = self.sock.recvfrom(8092)
                msg = pickle.loads(packet)
                self.emulate_once(msg)
            except:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Emulator")
    parser.add_argument("-p", help="the port of the emulator",
                        type=int, required=True)
    parser.add_argument(
        "-f", help="the topology file", type=str, required=True
    )

    arg = parser.parse_args()
    e = Emulator(arg.p, arg.f)
