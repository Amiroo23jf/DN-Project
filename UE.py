import threading
import socket
import logging
import time
import json

class UE():
    def __init__(self, user_info):
        self.uid =  user_info["uid"]
        self.interval = user_info["interval"]
        self.locations= user_info["locations"]

        # simulation timing configurations
        self.sim_started = False
        self.start_time = None 
        logging.debug("UE with uid:(%d) is successfully created", self.uid)

    def connect_enb_signalings(self, enb_ports):
        HOST = "127.0.0.1"
        for i in range(len(enb_ports)):
            enb_port = enb_ports[i]
            addr = (HOST, enb_port)
            signaling_connection = threading.Thread(target=self.connect_enb_signaling, args=(addr,))
            signaling_connection.start()
    
    def connect_enb_signaling(self, enb_addr):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_status = s.connect_ex(enb_addr)
        while (connection_status != 0):
            connection_status = s.connect_ex(enb_addr)
        logging.info("UE("+str(self.uid)+"): Connection with ENB is established on port:("+str(enb_addr[1])+")")
        
        # sending signaling channel setup message
        msg = {"type":3, "message": self.uid}
        msg_json = json.dumps(msg, indent=4)
        logging.debug("UE(" + str(self.uid) + "): Sending the Signaling Channel Setup message to port:("+str(enb_addr[1])+")")
        s.sendall(msg_json.encode("utf-8"))

        # First Stage: Waiting for the simulation to start
        while True :
            if (self.sim_started):
                break

        #logging.debug("UE("+str(self.uid)+"): Simulation is started")
        # Second Stage: Simulation is started the position should be sent 
        while True:
            pass

    def start_simulation(self, start_time):
        '''This method is called by LTESimulator when the simulation is started by giving the start time of 
        the simulation and setting the sim_started parameter to True'''
        self.start_time = start_time
        self.sim_started = True
        
