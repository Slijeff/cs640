import socket
import pickle
import argparse
from emulator import Message
import time
class trace:
    def __init__(self, port: int, srcName: str, srcPort: int, destName: str, destPort: int, debugOption: int) -> None:
        self.IP = socket.gethostbyname(socket.gethostname())
        self.port = port
        self.srcName = srcName
        self.srcPort = srcPort
        self.destName = destName
        self.destPort = destPort
        self.debugOption = debugOption
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.IP, self.port))
        self.sock.setblocking(False)
        self.TTL = 0
        self.startRouteTrace()
        
    def startRouteTrace(self) ->None:
        responsed = False
        T = time.time()
        diff = 0
        while responsed == False and diff<10:
            message = Message((self.IP,self.port),'TRACE',None,self.TTL,None,
                            (self.destName,self.destPort))
            self.sock.sendto(message.to_bytes(),(self.srcName,self.srcPort))
            if self.debugOption:
                print("Sending ", message.ttl,message.source[0],message.source[1],
                     self.destName,self.destPort)
            self.sock.settimeout(2)
            try:
                response, _ = self.sock.recvfrom(8192)
            except:
                continue
            self.sock.settimeout(None)
            response = pickle.loads(response)
            assert type(response) == Message
            assert response.packet_type == 'TRACE'
            if self.debugOption:
                print("Receving", message.ttl,message.source[0],message.source[1],
                      message.destination[0],message.destination[1])
            print(self.TTL+1, response.source[0],response.source[1])
            if self.destName != response.source[0] or\
                self.destPort != response.source[1]:
                    self.TTL += 1
            else:
                responsed = True
            diff = time.time()-T

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Emulator")
    parser.add_argument("-a", 
                        help="the port that the routetrace listens on for incoming packets",
                        type=int, required=True)
    parser.add_argument("-b", 
                        help="source hostname", 
                        type=str, required=True
    )
    parser.add_argument("-c", 
                        help="source port", 
                        type=int, required=True
    )
    parser.add_argument("-d", 
                        help="destination hostname", 
                        type=str, required=True
    )
    parser.add_argument("-e", 
                        help="destination port", 
                        type=int, required=True
    )
    parser.add_argument("-f", 
                        help="Debug option", 
                        type=int, required=True
    )

    arg = parser.parse_args()
    e = trace(arg.a, arg.b, arg.c, arg.d, arg.e, arg.f)
