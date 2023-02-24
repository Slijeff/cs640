import argparse
import socket
import struct


class Sender:
    def __init__(
        self, port: int, req_port: int, rate: int, seq_no: int, length: int
    ) -> None:
        self.listen_port = port
        self.requester_port = req_port
        self.UDP_IP = "127.0.0.1"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.UDP_IP, self.listen_port))
        self.sock.settimeout(60)
        self.listen_to_request()

    def listen_to_request(self) -> None:
        try:
            print(f"[Info] Waiting for request on port {self.listen_port}")
            packet, req_addr = self.sock.recvfrom(8192)
            header = packet[:9]
            payload = packet[9:]
            headers = struct.unpack("!cII", header)
            request_type, file_requested = headers[0].decode(), payload.decode()
            if request_type != "R":
                print(
                    f"[Error] Should get a request with request type 'R', but got {request_type} instead."
                )
            print(request_type, file_requested)
        except TimeoutError:
            print("[Error] Waited too long for the request, exiting...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send packets")
    # use argparse to parse arguments
    parser.add_argument(
        "-p", help="The port on which the sender waits for requests", type=int
    )
    args = parser.parse_args()

    sender = Sender(args.p, 5678, 0, 0, 0)
