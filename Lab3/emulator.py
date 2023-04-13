import socket
import time
import argparse


class Emulator():
    def __init__(self, port: int, filename: str) -> None:
        self.port = port
        self.topo_file = filename
        
        self.ip = socket.gethostbyname(socket.gethostname())
        
        self.neighbors = [] # a list of (ip, port) pair that indicates the neighbors
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.ip, self.port))
        self.sock.setblocking(False)

        self.read_topology()
        
    def read_topology(self):
        with open(self.topo_file, 'r') as f:
            for line in f:
                # find itself in the topo_file
                line = line.split(' ')
                line = [x.replace('\n', '').split(',') for x in line]
                line = [(x[0], int(x[1])) for x in line]
                if line[0][0] == self.ip and line[0][1] == self.port:
                    self.neighbors = line[1:]

        print(self.neighbors)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Emulator")
    parser.add_argument("-p", help="the port of the emulator",
                        type=int, required=True)
    parser.add_argument(
        "-f", help="the topology file", type=str, required=True
    )

    arg = parser.parse_args()
    Emulator(arg.p, arg.f)


