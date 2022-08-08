import threading
import socket
import json
import logging
import time


class eNodeB():
    def __init__(self, location, uid):
        self.location = location
        self.uid = uid
        self.host = "127.0.0.1"

        # initializing the dictionaries
        self.lock_dict = {"ue_id_port_dict" : threading.Lock(),}
        self.ue_id_port_dict = dict()

        # simulation timing configurations
        self.sim_started = False
        self.start_time = None

        logging.debug("eNodeB with uid: "+ str(self.uid) + " is successfully created.")

    def connect_to_sgw(self, sgw_port):
        HOST = "127.0.0.1"
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_status = s.connect_ex((HOST, sgw_port))
        while (connection_status != 0):
            connection_status = s.connect_ex((HOST, sgw_port))

        logging.info("ENB("+str(self.uid)+"): Connection with SGW is established on port:(%d)", sgw_port)
        # sending a eNodeB-SGW Connection message
        msg = {"type":1, "message": self.uid}
        msg_json = json.dumps(msg, indent=4)
        logging.debug("ENB("+str(self.uid)+"): Sending the eNodeB-SGW connection message")
        s.sendall(msg_json.encode("utf-8"))
        while True :
            pass

    def connect_to_mme(self, mme_port):
        HOST = "127.0.0.1"
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_status = s.connect_ex((HOST, mme_port))
        while (connection_status != 0):
            connection_status = s.connect_ex((HOST, mme_port))

        logging.info("ENB("+str(self.uid)+"): Connection with MME is established on port:(%d)", mme_port)
        # sending a eNodeB-MME Connection message
        msg = {"type":2, "message": self.uid}
        msg_json = json.dumps(msg, indent=4)
        logging.debug("ENB("+str(self.uid)+"): Sending the eNodeB-MME connection message")
        s.sendall(msg_json.encode("utf-8"))
        while True :
            pass

    def run_server(self, port, signaling, max_clients=100):
        if signaling:  
            # the server is for signaling
            self.signaling_port = port
            client_handler = self.handle_signaling_nodes
        else:
            # the server is for data
            self.data_port = port
            client_handler = self.handle_data_nodes
        
        # creating a socket and listening for connections
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        bound = False
        while not bound:
            try:
                s.bind((self.host, port))
                bound = True
            except OSError:
                time.sleep(0.02)
        s.listen(max_clients)
        if signaling:
            logging.debug("ENB("+str(self.uid)+") signaling server is running on port:(%d)", self.signaling_port)
        else:
            logging.debug("ENB("+str(self.uid)+") data server is running on port:(%d)", self.data_port)
        while True:

            # establish a connection with client
            c, addr = s.accept()
            client_thread = threading.Thread(target=client_handler, args=(c, addr))
            client_thread.start()

    def handle_signaling_nodes(self, c, addr):
        client_uid = 0
        client_port = addr[1]
        while True:

            # data recieved from client
            data = c.recv(1024)
            if not data:
                # the connection was closed
                break
            
            # decoding the data
            data_decoded = data.decode("utf-8")
            data_dict = json.loads(data_decoded)
            if (data_dict["type"] == 3):
                client_uid = data_dict["message"]
                logging.info("ENB("+str(self.uid)+"): UE(" + str(client_uid) + ") is connected from port:(" + str(client_port) + ")")
                self.lock_dict["ue_id_port_dict"].acquire()
                self.ue_id_port_dict[client_uid] = client_port
                self.lock_dict["ue_id_port_dict"].release()
        return 
    
    def handle_data_nodes(self, c, addr):
        client_uid = 0
        client_port = addr[1]
        while True:

            # data recieved from client
            data = c.recv(1024)
            if not data:
                # the connection was closed
                break
        return 

    def start_simulation(self, start_time):
        '''This method is called by LTESimulator when the simulation is started by giving the start time of 
        the simulation and setting the sim_started parameter to True'''
        self.start_time = start_time
        self.sim_started = True