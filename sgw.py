import socket
import threading 
import json 
import logging
import time 

class SGW():
    def __init__(self, port):
        self.host = "127.0.0.1"
        self.port = port
        self.enb_id_port_dict = dict()
        self.lock_dict = {"enb_id_port_dict" : threading.Lock(),}

        # simulation timing configurations
        self.sim_started = False
        self.start_time = None

        logging.debug("SGW with port number:("+ str(port) +") is successfully created.")

    def run_server(self, max_clients=50):
        # creating a socket and listening for connections
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        bound = False
        while not bound:
            try:
                s.bind((self.host, self.port))
                bound = True
            except OSError:
                time.sleep(0.02)
        s.listen(max_clients)

        # creating the locks
        enb_id_port_lock = threading.Lock()
        logging.debug("SGW server is running on port:(%d)", self.port)
        while True:

            # establish a connection with client
            c, addr = s.accept()
            client_thread = threading.Thread(target=self.handle_nodes, args=(c, addr))
            client_thread.start()

    def handle_nodes(self, c, addr):
        client_entity = "Unknown"
        client_uid = 0
        client_port = addr[1]
        while (True):
            
            # data recieved from client
            data = c.recv(1024)
            if not data:
                # the connection was closed
                break

            # decoding the data
            data_decoded = data.decode("utf-8")
            data_recieved = data.decode('utf-8').split("\END_OF_MSG")
            for data_decoded in data_recieved[:-1]:
                try:
                    if (len(data_decoded)!=0):
                        data_dict = json.loads(data_decoded)
                except:
                    logging.warning("SGW: Data recieved from "+client_entity+"("+str(client_uid)+") is corrupted")
                if (data_dict["type"] == 1):
                    client_entity = "ENB"
                    client_uid = data_dict["message"]
                    logging.info("SGW: eNodeB(" + str(client_uid) + ") is connected from port:(" + str(client_port) + ")")
                    self.lock_dict["enb_id_port_dict"].acquire()
                    self.enb_id_port_dict[client_uid] = client_port
                    self.lock_dict["enb_id_port_dict"].release()

                     # send a response to the client
            
    def connect_to_mme(self, mme_port):
        '''Establishing the connection from SGW to MME server on the given port'''
        HOST = "127.0.0.1"
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_status = s.connect_ex((HOST, mme_port))
        while (connection_status != 0):
            connection_status = s.connect_ex((HOST, mme_port))

        logging.info("SGW: Connection with MME is established on port:(%d)", mme_port)
            
        while True:
            pass

    def start_simulation(self, start_time):
        '''This method is called by LTESimulator when the simulation is started by giving the start time of 
        the simulation and setting the sim_started parameter to True'''
        self.start_time = start_time
        self.sim_started = True
