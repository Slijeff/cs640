from ast import List
import subprocess as sub
from sys import argv
import time

if __name__ == "__main__":
    topo_file = argv[1]
    ports = []
    with open(topo_file, "r") as f:
        for line in f:
            line = line.split(" ")
            ports.append(line[0].split(",")[1])
    
    proc_list = []
    for p in ports[::]:
        prc = sub.Popen(["python3", "emulator.py", "-p", p, "-f", topo_file], stdout=sub.PIPE)
        proc_list.append(prc)
    try:
        proc_list[0].wait()
    except KeyboardInterrupt:
        print("terminating...")
        for p in proc_list:
            p.terminate()
        print("terminated")