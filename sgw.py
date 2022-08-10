import socket
import threading 
import json 
import logging
import time 

class SGW():
    def __init__(self, port, table_max_length = 10):
        self.host = "127.0.0.1"
        self.port = port
        self.enb_id_port_dict = dict()
        self.lock_dict = {"enb_id_port_dict" : threading.Lock(),}
        self.enb_sockets = dict()
        
        # routing table 
        self.routing_table = {"table":dict(), "lock": threading.Lock(), "max_length":table_max_length}

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
        socket_lock = threading.Lock()
        while (True):
            
            # data recieved from client
            data = c.recv(1024)
            if not data:
                # the connection was closed
                break

            # decoding the data
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
                    self.enb_sockets[client_uid] = {"socket":c, "lock": socket_lock}
                    logging.info("SGW: eNodeB(" + str(client_uid) + ") is connected from port:(" + str(client_port) + ")")
                    self.lock_dict["enb_id_port_dict"].acquire()
                    self.enb_id_port_dict[client_uid] = client_port
                    self.lock_dict["enb_id_port_dict"].release()

                elif (data_dict["type"] == 9):
                    # session creation message
                    source_uid = data_dict["message"]["source"]
                    dst_uid = data_dict["message"]["dst"]
                    logging.critical("SGW: Session Creation is recieved from UE("+str(source_uid)+")")
                    target_enb = self.route_packet(dst_uid)

                    # send to target enodeb
                    msg = data_dict.copy()
                    self.send_to_enb(target_enb, msg)

                elif (data_dict["type"] == 14):
                    # change route message is received 
                    dst = data_dict["message"]["dst"] 
                    enb_uid = data_dict["message"]["enb_uid"]
                    logging.debug("SGW: Changing route: UE("+str(dst)+") --> ENB("+str(enb_uid)+")")
                    self.change_route(dst, enb_uid)
            
    def connect_to_mme(self, mme_port):
        '''Establishing the connection from SGW to MME server on the given port'''
        HOST = "127.0.0.1"
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_status = s.connect_ex((HOST, mme_port))
        while (connection_status != 0):
            connection_status = s.connect_ex((HOST, mme_port))

        logging.info("SGW: Connection with MME is established on port:(%d)", mme_port)

        socket_lock = threading.Lock()
        self.mme_socket = {"socket": s, "lock": socket_lock}

    def sent_to_mme(self, msg):
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        self.mme_socket["lock"].acquire()
        self.mme_socket["socket"].sendall(msg_json.encode("utf-8"))
        self.mme_socket["lock"].release()

    def send_to_enb(self, enb_uid, msg):
        '''Sends the given message to the eNodeB with the given UID'''
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        self.enb_sockets[enb_uid]["lock"].acquire()
        self.enb_sockets[enb_uid]["socket"].sendall(msg_json.encode("utf-8"))
        self.enb_sockets[enb_uid]["lock"].release()

    def start_simulation(self, start_time):
        '''This method is called by LTESimulator when the simulation is started by giving the start time of 
        the simulation and setting the sim_started parameter to True'''
        self.start_time = start_time
        self.sim_started = True

    def route_packet(self, dst):
        '''Finds the eNodeB to which the packet with the given destination should be sent'''
        while True:
            self.routing_table["lock"].acquire()
            if (dst in self.routing_table["table"].keys()):
                target_enb = self.routing_table["table"][dst]
                self.routing_table["lock"].release()
                break
            else:  
                self.routing_table["lock"].release()
                time.sleep(0.1)
        return target_enb


    def ask_route(self, dst):
        '''Sends an ask route request with the given destionation to the MME server'''
        msg = {"type": 15, "message": {"dst": dst}}
        self.send_to_mme(msg)
        logging.debug("SGW: Ask route request for UE("+str(dst)+") is sent to the MME server")

    def change_route(self, dst, enb_uid):
        '''Changes the routing table for the given destination to the given eNodeB UID'''
        self.routing_table["lock"].acquire()
        table_length = len(self.routing_table["table"].keys())

        # removing from the routing table if it is full
        if (table_length == self.routing_table["max_length"]):
            self.remove_from_table()

        # adding the entry to the routing table
        self.routing_table["table"][dst] = enb_uid
        self.routing_table["lock"].release()
 
    def remove_from_table(self):
        '''Removes one of the entries from the routing table'''
        first_key = self.routing_table["table"].keys()[0]
        self.routing_table["table"].pop(first_key)


        

        

    
            

