import socket
from dataclasses import dataclass
import pickle
# import time
import argparse
from typing import Dict, List, Optional, Tuple, Literal, Union

Address = Tuple[str, int]
LinkState = Tuple[Address, int] # address and cost to that address

@dataclass
class Message:
    creator: Address
    packet_type: Literal["HELLO", "LSM"]
    seq_num: Optional[int] = None
    ttl: Optional[int] = None
    neighbors: Optional[List[LinkState]] = None 


    def to_bytes(self) -> bytes:
        return pickle.dumps(self)

class Emulator():
    def __init__(self, port: int, filename: str) -> None:
        self.port = port
        self.topo_file = filename
        
        self.neighbors: List[Address] = [] # a list of (ip, port) pair that indicates the neighbors
       
        self.ip = socket.gethostbyname(socket.gethostname())
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.ip, self.port))
        self.sock.setblocking(False)
        
        self.lsp_interval = 0.5 # in seconds
        self.forwarding_table: Dict[Address, Address] = {} # maps (dst_addr, dst_ip) to (next_hop_addr, next_hop_ip)

        self.read_topology()
        
    def read_topology(self) -> List[Address]:
        topology = [] 
        with open(self.topo_file, 'r') as f:
            for line in f:
                # find itself in the topo_file
                line = line.split(' ')
                line = [x.replace('\n', '').split(',') for x in line]
                line = [(x[0], int(x[1])) for x in line]
                if line[0][0] == self.ip and line[0][1] == self.port:
                    topology = line[1:]
        
        assert topology != []
        return topology
    
    def send_msg(self, msg: Message, dest: Address):
        self.sock.sendto(msg.to_bytes(), dest)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Emulator")
    parser.add_argument("-p", help="the port of the emulator",
                        type=int, required=True)
    parser.add_argument(
        "-f", help="the topology file", type=str, required=True
    )

    arg = parser.parse_args()
    e = Emulator(arg.p, arg.f)

