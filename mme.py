import socket
import threading 
import logging
import json
import time

class MME():
    def __init__(self, port, timeout):
        self.host = "127.0.0.1"
        self.port = port
        self.timeout = timeout

        # databases
        self.enb_id_port_dict = dict()
        self.lock_dict = {"enb_id_port_dict" : threading.Lock(), "distance_db": threading.Lock(), "ue_enb_db": threading.Lock()}
        self.distance_db = dict() # saves the distance between a user and an enb in a certain time
        self.enb_sockets = dict()
        self.ue_enb_db = dict()
        

        # simulation timing configurations
        self.sim_started = False
        self.start_time = None

        logging.debug("MME with port number:("+ str(port) +") is successfully created.")

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
        logging.debug("MME server is running on port:(%d)", self.port)
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
            
            # data received from client
            data = c.recv(2048)
            if not data:
                # the connection was closed
                break

            # decoding the data
            data_decoded = data.decode("utf-8")
            data_received = data.decode('utf-8').split("\END_OF_MSG")
            for data_decoded in data_received[:-1]:
                try:
                    if (len(data_decoded)!=0):
                        data_dict = json.loads(data_decoded)
                except:
                    logging.warning("MME: Data received from "+client_entity+"("+str(client_uid)+") is corrupted")
                if (data_dict["type"] == 2):
                    client_entity = "ENB"
                    client_uid = data_dict["message"]
                    logging.info("MME: eNodeB(" + str(client_uid) + ") is connected from port:(" + str(client_port) + ")")
                    self.lock_dict["enb_id_port_dict"].acquire()
                    self.enb_id_port_dict[client_uid] = client_port
                    self.enb_sockets[client_uid] = (c, threading.Lock())
                    self.lock_dict["enb_id_port_dict"].release()
                elif (data_dict["type"] == 5):
                    distance = data_dict["message"]["distance"]
                    user_uid = data_dict["message"]["user_uid"]
                    user_time = data_dict["message"]["user_time"]
                    logging.info("MME: Distance between ENB("+ str(client_uid) + ") and UE("+ str(user_uid) + ") at time " + 
                    "{:.2f}".format(user_time) + " is " + "{:.4f}".format(distance))

                    # send the new info to the enb assignment method
                    self.enb_assignment(client_uid, user_uid, user_time, distance)

                elif (data_dict["type"] == 15):
                    # check or set the entity of the client
                    if (client_entity == "ENB"):
                        pass # do nothing (however this case never happens)
                    elif(client_entity == "Unknown"):
                        client_entity == "SGW"
                    
                    if (client_entity == "SGW"):
                        dst = data_dict["type"]["dst"]
                        self.lock_dict["ue_enb_db"].acquire()
                        target_enb = self.ue_enb_db[dst].copy()
                        self.lock_dict["ue_enb_db"].release()

                        # sending a change route message 
                        self.change_route(dst, target_enb)

    def connect_to_sgw(self, sgw_port):
        '''Establishing the connection from MME to SGW on the given port'''
        HOST = "127.0.0.1"
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_status = s.connect_ex((HOST, sgw_port))
        while (connection_status != 0):
            connection_status = s.connect_ex((HOST, sgw_port))
        socket_lock = threading.Lock()
        self.sgw_socket = {"socket": s, "lock": socket_lock}
        logging.info("MME: Connection with SGW is established on port:(%d)", sgw_port)

    def send_to_sgw(self, msg):
        '''Sends the given message to the SGW server'''
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        self.sgw_socket["lock"].acquire()
        self.sgw_socket["socket"].send(msg_json.encode("utf-8"))
        self.sgw_socket["lock"].release()

    def start_simulation(self, start_time):
        '''This method is called by LTESimulator when the simulation is started by giving the start time of 
        the simulation and setting the sim_started parameter to True'''
        self.start_time = start_time
        self.sim_started = True

    def enb_assignment(self, enb_uid, user_uid, user_time, distance):
        '''This method finds that in a given time which eNodeB should be assigned to a user based on their distance'''
        self.lock_dict["distance_db"].acquire()
        if (user_uid, user_time) not in list(self.distance_db.keys()):
            self.distance_db[(user_uid, user_time)] = [(enb_uid, distance)]
            enb_assignment_thread = threading.Thread(target=self.find_best_enb, args=((user_uid, user_time), ))
            enb_assignment_thread.start()
        else :
            self.distance_db[(user_uid, user_time)].append((enb_uid, distance))
        self.lock_dict["distance_db"].release()

    def send_to_enb(self, enb_uid, msg):
        enb_socket, enb_socket_lock = self.enb_sockets[enb_uid]
        enb_socket_lock.acquire()
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        enb_socket.sendall(msg_json.encode("utf-8"))
        enb_socket_lock.release()
        

    def find_best_enb(self, user_data):
        '''This method checks the distance database of a given user and time for a certain time and finds the eNodeB with the lowest distance'''
        timeout = self.timeout
        t0 = time.time()
        while (time.time() <= t0 + timeout):
            self.lock_dict["distance_db"].acquire()
            enb_distance_list = self.distance_db[user_data].copy()
            best_enb_uid = min(enb_distance_list, key=(lambda x: x[1]))[0]
            self.lock_dict["distance_db"].release()

            if (len(enb_distance_list) == len(self.enb_id_port_dict)):
                logging.debug("MME: Data from all eNodeBs is collected for UE("+str(user_data[0])+") at time " + "{:.2f}".format(user_data[1]))
                break
            #time.sleep(timeout/10)
        
        logging.critical("MME: UE("+str(user_data[0])+") is assigned to ENB("+str(best_enb_uid)+") at time " + "{:.2f}".format(user_data[1]) + " with real time " + "{:.2f}".format(time.time() - self.start_time))
        #logging.info("MME: UE("+str(user_data[0])+") is assigned to ENB("+str(best_enb_uid)+") at time " + "{:.2f}".format(user_data[1]))

        # sending the User-eNodeB registration message to the eNodeB
        user_uid = user_data[0]
        if (user_uid not in list(self.ue_enb_db.keys())):
            self.lock_dict["ue_enb_db"].acquire()
            self.ue_enb_db[user_uid] = best_enb_uid
            self.lock_dict["ue_enb_db"].release()
            msg = {"type": 6, "message": {"uid":user_uid, "has_previous": False}}
            self.send_to_enb(best_enb_uid, msg)
            self.change_route(user_uid, best_enb_uid)
        elif (best_enb_uid != self.ue_enb_db[user_uid]):
            self.lock_dict["ue_enb_db"].acquire()
            last_enb_uid = self.ue_enb_db[user_uid]
            self.ue_enb_db[user_uid] = best_enb_uid
            self.lock_dict["ue_enb_db"].release()
            
            # send eNodeB Deregistration message
            msg = {"type": 6, "message": {"uid":user_uid, "has_previous":True, "previous_enb": last_enb_uid}}
            deregistration_msg = {"type": 8, "message": {"uid":user_uid, "next_enb": best_enb_uid}}
            self.send_to_enb(last_enb_uid, deregistration_msg)
            self.send_to_enb(best_enb_uid, msg)
            self.change_route(user_uid, best_enb_uid)
        
    def change_route(self, user_uid, enb_uid):
        '''Sends a change route message to the SGW server'''
        msg = {"type": 14, "message": {"dst": user_uid, "enb_uid": enb_uid}}
        self.send_to_sgw(msg)
        logging.info("MME: Sending the change route message: UE("+str(user_uid)+") --> ENB("+str(enb_uid)+")")
        
        

        
        
        
        
            
            
