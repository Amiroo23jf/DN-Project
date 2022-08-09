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

        # initializing the database
        self.database = dict()

        # initializing the locks
        self.db_lock = threading.Lock()
        self.mme_send_lock = threading.Lock()
        self.covered_users = []

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
        self.sgw_socket = s
        msg = {"type":1, "message": self.uid}
        msg_json = json.dumps(msg) + "\END_OF_MSG"
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
        self.mme_socket = s
        # sending a eNodeB-MME Connection message
        msg = {"type":2, "message": self.uid}
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        logging.debug("ENB("+str(self.uid)+"): Sending the eNodeB-MME connection message")
        s.sendall(msg_json.encode("utf-8"))
        while True :
            # data recieved from client
            data = s.recv(2048)
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
                    logging.warning("ENB("+str(self.uid)+"): Data recieved from MME is corrupted")
                if (data_dict["type"] == 6):
                    user_uid = data_dict["message"]["uid"]
                    has_previous = data_dict["message"]["has_previous"]
                    if (has_previous):
                        previous_enb = data_dict["message"]["previous_enb"]
                        logging.info("ENB("+str(self.uid)+"): UE("+str(user_uid)+") is in my cell and it was previously connected to ENB("+
                        str(previous_enb)+")")
                    else:
                        logging.info("ENB("+str(self.uid)+"): UE("+str(user_uid)+") is in my cell and it had no previous ENB")
                    self.covered_users.append(user_uid)
                    # send User-eNodeB Connection
                    msg = {"type":7, "message": {"port":self.data_port}}
                    self.send_signal_to_user(user_uid, msg)
                    

                elif (data_dict["type"] == 8):
                    # Release connection
                    user_uid = data_dict["message"]["uid"]
                    next_enb = data_dict["message"]["next_enb"]
                    self.covered_users.remove(user_uid)
                    logging.info("ENB("+str(self.uid)+"): Data channel with UE("+str(user_uid)+") is closed and it is now connected to ENB("
                    +str(next_enb)+")")
                    
                    ##### Fill this part to buffer the data received ####


                    

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
            data_recieved = data.decode('utf-8').split("\END_OF_MSG")
            for data_decoded in data_recieved[:-1]:
                try:
                    if (len(data_decoded)!=0):
                        data_dict = json.loads(data_decoded)
                    else :
                        data_dict = None
                except:
                    logging.warning("ENB("+str(self.uid)+"): Data recieved from UE("+str(client_uid)+") is corrupted")
                if data_dict is None:
                    pass
                elif (data_dict["type"] == 3):
                    client_uid = data_dict["message"]
                    logging.info("ENB("+str(self.uid)+"): UE(" + str(client_uid) + ") is connected from port:(" + str(client_port) + ")")
                    self.db_lock.acquire()
                    self.database[client_uid] = {"signaling_socket": c, "signaling_lock": threading.Lock()}
                    self.db_lock.release()
                
                elif (data_dict["type"] == 0):
                    # saving the distance between the UE and ENB in the database
                    new_position = data_dict["message"]["position"]
                    distance = self.calculate_distance(new_position)
                    user_time = data_dict["message"]["time"]
                    self.db_lock.acquire()
                    self.database[client_uid]["distance"] = distance
                    self.db_lock.release()

                    # sending a user distance message to the MME
                    msg = {"type":5, "message": {"distance":distance,"user_uid":client_uid, "user_time":user_time}}
                    self.send_to_mme(msg)
                    logging.debug("ENB("+str(self.uid)+"): Sending User Distance of UE(" + str(client_uid)+") to MME")


        return 
    
    def handle_data_nodes(self, c, addr):
        client_uid = None
        client_port = addr[1]
        while True:

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
                    else :
                        data_dict = None
                except:
                    logging.warning("ENB("+str(self.uid)+"): Data recieved from UE("+str(client_uid)+") is corrupted")
                if data_dict is None:
                    pass
        

    def start_simulation(self, start_time):
        '''This method is called by LTESimulator when the simulation is started by giving the start time of 
        the simulation and setting the sim_started parameter to True'''
        self.start_time = start_time
        self.sim_started = True

    def calculate_distance(self, new_position):
        '''Calculates the distance between the new position and the position of the eNodeB'''
        x_pos = new_position[0]
        y_pos = new_position[1]

        distance = ((x_pos - self.location[0])**2 + (y_pos - self.location[1])**2)**0.5
        return distance

    def send_to_mme(self, msg):
        '''Sends a message to the MME server'''
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        self.mme_socket.sendall(msg_json.encode("utf-8"))

    def send_signal_to_user(self, user_uid, msg):
        '''Sends a message to the user  with the given user_uid and msg'''
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        c, socket_lock = self.database[user_uid]["signaling_socket"], self.database[user_uid]["signaling_lock"]
        socket_lock.acquire()
        c.sendall(msg_json.encode("utf-8"))
        socket_lock.release()

        


    
