import socket
import pickle
import argparse
from emulator import Message

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
        self.TTL = 0
        self.startRouteTrace()
        
    def startRouteTrace(self) ->None:
        responsed = False
        while responsed == False:
            message = Message((self.IP,self.port),'TRACE',None,self.TTL,None,
                            (self.destName,self.destPort))
            self.sock.sendto(message.to_bytes(),(self.srcName,self.srcPort))
            if self.debugOption:
                print(message.ttl,message.source[0],message.source[1],
                     self.destName,self.destPort)
            response, _ = self.sock.recvfrom(8192)
            response = pickle.loads(response)
            assert type(response) == Message
            assert response.packet_type == 'TRACE'
            if self.debugOption:
                print(message.ttl,message.source[0],message.source[1],
                      message.destination[0],message.destination[1])
            print(self.TTL+1, response.destination[0],response.destination[1])
            if self.destName != response.destination[0] or\
                self.destPort != response.destination[1]:
                    self.TTL += 1
            else:
                responsed = True
        

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
