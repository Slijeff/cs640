import socket
from dataclasses import dataclass
import pickle
import time
import argparse
from typing import Dict, List, Optional, Set, Tuple, Literal, Union
from collections import defaultdict, deque
import logging

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

    def record_neighbor(self, neighbor: Address) -> Union[Tuple[Address, Literal["UP"]], None]:
        if neighbor not in [n[0] for n in self.neighbors]:
            # a neighbor is online
            self.neighbors.append((neighbor, time.time()))
            logging.debug(f"Neighbor {neighbor} is online")
            return (neighbor, 'UP')
        else:
            old = None
            for entry in self.neighbors:
                if entry[0] == neighbor:
                    old = entry
            assert old != None
            self.neighbors.remove(old)
            self.neighbors.append((neighbor, time.time()))
            logging.debug(f"Neighbor is already online, updated")

    def check_timeout(self) -> Union[Tuple[Address, Literal["DOWN"]], None]:
        for entry in self.neighbors:
            if time.time() - entry[1] > self.timeout:
                self.neighbors.remove(entry)
                logging.debug(
                    f"Neighbor {entry[0]} is offline due to timeout for {time.time() - entry[1]} seconds")
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
        # self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.address = (self.ip, self.port)
        self.lsm_interval = 1.5  # in seconds
        self.hello_interval = 1.5  # timeout for neighbor nodes
        self.timout = 3.5
        self.sequence_no = 0
        self.last_hello_sent = time.time()
        self.last_LSM_sent = time.time()
        self.offline_repr: Address = ('125.125.125.125', -1)
        # maps (dst_addr, dst_ip) to (next_hop_addr, next_hop_ip)
        self.forwarding_table: Dict[Address, Address] = {}
        self.all_nodes_except_self: List[Address] = []
        self.adj_list: Dict[Address, Set[Address]] = defaultdict(set)
        self.sequence_tracking: Dict[Address, int] = defaultdict(int)

        logging.basicConfig(
            format='[%(asctime)s]  === %(levelname)s ===  %(message)s', level=logging.INFO)
        logging.info("Emulator started on port %d", self.port)

        self.read_topology()
        self.ttl = len(self.all_nodes_except_self) + 1
        self.neighbor_list = NeighborList(
            set(self.neighbors), self.timout)
        self.build_forwarding_table()
        self.emulate()

    def read_topology(self) -> None:
        logging.info("Reading topology file")
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
        logging.debug(
            f"Found {len(self.neighbors)} neighbors; Total of {len(self.all_nodes_except_self) + 1} nodes are in the network")
        self.print_topology()
        self.print_forwarding_table()

    def update_adj_list(self, msg: Message) -> bool:
        """
        returns True if adjacency list changed, False if nothing changed
        """
        assert msg.seq_num != None, "For Link State packet, sequence number must be present"
        assert msg.neighbors != None, "For Link State packet, neighbor list must be present"
        assert msg.source in self.adj_list, "Source node not in topology file"

        if self.sequence_tracking[msg.source] >= msg.seq_num:
            logging.debug(f"Adjacency list remains the same because the received LSM is outdated")
            return False

        old = self.adj_list[msg.source]
        new = msg.neighbors

        if new:
            if old == new:
                self.sequence_tracking[msg.source] = msg.seq_num
                logging.debug(f"Adjacency list remains the same but the received LSM is newer")
                return False
            else:
                self.sequence_tracking[msg.source] = msg.seq_num
                self.adj_list[msg.source] = new
                logging.debug(f"Adjacency list changed")

        return True
    
    def print_topology(self) -> None:
        print()
        print("===  TOPOLOGY  ===")
        for k,v in self.adj_list.items():
            v = [str(s)[1:-1] for s in list(v)]
            print(str(k)[1:-1], ' '.join(v))
        print()
    
    def print_forwarding_table(self) -> None:
        print()
        print("===  FORWARDING TABLE  ===")
        for k,v in self.forwarding_table.items():
            if v != self.offline_repr:
                print(str(k)[1:-1], str(v)[1:-1])
        print()

    def build_forwarding_table(self, dead_node: Union[Address, None] = None) -> None:
        logging.info("Building forwarding table")
        if dead_node and not self.adj_list[self.address]:
            logging.debug("No neighbor is online, empty forwarding table")
            self.forwarding_table[dead_node] = self.offline_repr
            self.print_topology()
            self.print_forwarding_table()
            return
        for node in [x for x in self.all_nodes_except_self if x != dead_node]:
            result = self.forward_search(self.address, node)
            if result:
                self.forwarding_table[node] = result[1]
            else:
                self.forwarding_table[node] = self.offline_repr
            if dead_node:
                self.forwarding_table[dead_node] = self.offline_repr
        self.print_topology()
        self.print_forwarding_table()

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
        self.sock.sendto(msg.to_bytes(), dest)
        # pass

    def broadcast_to_neighbors(self, msg: Message) -> None:
        if self.adj_list[self.address]:
            for neighbor in self.adj_list[self.address]:
                self.send_msg(msg, neighbor)
            logging.debug(f"Sent a {msg.packet_type} packet to neighbors")
        else:
            logging.debug(f"Try to broadcast {msg.packet_type} but no neighbor is online")
    
    def broadcast_to_neighbors_except(self, msg: Message, _except: Address) -> None:
        if self.adj_list[self.address]:
            for neighbor in self.adj_list[self.address]:
                if neighbor != _except:
                    self.send_msg(msg, neighbor)
            logging.debug(f"Sent a {msg.packet_type} packet to neighbors")
        else:
            logging.debug(f"Try to broadcast {msg.packet_type} but no neighbor is online")

    def emulate_once(self, msg: Message) -> None:
        logging.info(f"Received {msg.packet_type} packet from {msg.source}")
        # If message is HELLO
        if msg.packet_type == "HELLO":
            result = self.neighbor_list.record_neighbor(msg.source)
            if result:
                self.adj_list[self.address].add(result[0])
                self.adj_list[result[0]].add(self.address)
                self.sequence_tracking[result[0]] = 0
                self.build_forwarding_table()
        # If message is Link State
        elif msg.packet_type == "LSM":
            assert msg.ttl != None, "For Link State packet, ttl must be present"
            if msg.ttl > 0:
                if self.update_adj_list(msg):
                    logging.info(f"Network topoloy changed according to a LSM from {msg.source}")
                    self.build_forwarding_table()
                msg.ttl -= 1
                self.broadcast_to_neighbors_except(msg, msg.source)

        # If message is Traceroute
        elif msg.packet_type == "TRACE":
            
            assert msg.destination != None, "For Traceroute packet, the destination must be present"
            assert msg.ttl != None, "For Traceroute packet, the ttl must be present"
            print("Inside TRACE", msg.ttl)
            if msg.ttl != 0:
                # forward it
                msg.ttl -= 1
                print("Inside TRACE > 0", msg, self.forwarding_table[msg.destination])
                self.send_msg(msg, self.forwarding_table[msg.destination])
            else:
                # change the source to itself and dest to source
                originator = msg.source
                msg.destination = originator
                msg.source = self.address
                # msg.ttl = 0
                # forward it
                self.send_msg(msg, msg.destination)

        

    def emulate(self) -> None:
        logging.info("Starting emulator main loop")
        while 1:
            try:
                packet, _ = self.sock.recvfrom(8092)
                msg = pickle.loads(packet)
                self.emulate_once(msg)
            except:
                pass

            # Send Hello to neighbors
            if time.time() - self.last_hello_sent >= self.hello_interval:
                self.last_hello_sent = time.time()
                self.broadcast_to_neighbors(Message(
                    source=self.address,
                    packet_type='HELLO'
                ))
            # Send LSM to neighbors
            if time.time() - self.last_LSM_sent >= self.lsm_interval:
                # print("adj_list: ", self.adj_list)
                # print("forwarding: ", self.forwarding_table)
                self.last_LSM_sent = time.time()
                self.broadcast_to_neighbors(Message(
                    source=self.address,
                    packet_type='LSM',
                    seq_num=self.sequence_no + 1,
                    ttl=self.ttl,
                    neighbors=self.adj_list[self.address]
                ))
                self.sequence_no += 1
            # Check if any neighbor is dead
            result = self.neighbor_list.check_timeout()
            if result:
                # Send new link state message and rebuild forwarding_table
                logging.info("Broadcasting dead neighbor to other nodes")
                if result[0] in self.adj_list[self.address]:
                    self.adj_list[self.address].remove(result[0])
                if self.address in self.adj_list[result[0]]:
                    self.adj_list[result[0]].remove(self.address)
                self.broadcast_to_neighbors(
                    Message(
                        source=self.address,
                        packet_type='LSM',
                        seq_num=self.sequence_no + 1,
                        ttl=self.ttl,  # maximum of 20 nodes, put 25 just to be safe
                        neighbors=self.adj_list[self.address]
                    )
                )
                self.sequence_no += 1
                self.build_forwarding_table(result[0])



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Emulator")
    parser.add_argument("-p", help="the port of the emulator",
                        type=int, required=True)
    parser.add_argument(
        "-f", help="the topology file", type=str, required=True
    )

    arg = parser.parse_args()
    e = Emulator(arg.p, arg.f)
