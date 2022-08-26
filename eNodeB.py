from sys import excepthook
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
        self.covered_users = []

        # buffers
        self.recv_buffer = {"buffers":dict(), "lock":threading.Lock()}
        self.trans_buffer = {"buffers":dict(), "lock":threading.Lock()}

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
        socket_lock = threading.Lock()
        self.sgw_socket = {"socket":s, "lock":socket_lock}
        msg = {"type":1, "message": self.uid}
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        logging.debug("ENB("+str(self.uid)+"): Sending the eNodeB-SGW connection message")
        socket_lock.acquire()
        s.sendall(msg_json.encode("utf-8"))
        socket_lock.release()

        # handling received packets from SGW
        while True :
             # data received from client
            data = s.recv(2048)
            if not data:
                # the connection was closed
                break
            
            # decoding the data
            data_received = data.decode('utf-8').split("\END_OF_MSG")
            for data_decoded in data_received[:-1]:
                try:
                    if (len(data_decoded)!=0):
                        data_dict = json.loads(data_decoded)
                except:
                    logging.warning("ENB("+str(self.uid)+"): Data received from SGW is corrupted")
                if (data_dict["type"] == 9):
                    dst = data_dict["message"]["dst"]
                    if dst not in self.covered_users:
                        logging.error("ENB("+str(self.uid)+"): UE("+str(dst)+") is not covered")
                        ############### do something about message for uncovered users ################

                    else:
                        logging.info("ENB("+str(self.uid)+"): Session Creation with UE("+str(dst)+") is received from SGW")
                        self.send_signal_to_user(dst, data_dict.copy())
                
                elif (data_dict["type"] == 10):
                    dst = data_dict["message"]["dst"]
                    if dst not in self.covered_users:
                        logging.error("ENB("+str(self.uid)+"): UE("+str(dst)+") is not covered")
                        ############### do something about message for uncovered users ################
                    
                    else:
                        logging.info("ENB("+str(self.uid)+"): Session Creation ACK for UE("+str(dst)+") is received from SGW")
                        self.send_signal_to_user(dst, data_dict.copy())
                
                elif ( data_dict["type"] == 16):
                    dst = data_dict["message"]["dst"]
                    chunk_num = data_dict["message"]["chunk_num"]
                    source = data_dict["message"]["source"]
                    if dst not in self.covered_users:
                        ############## The buffering and this kind of stuff should be handled here ################
                        # check if the data should be buffered
                        self.recv_buffer["lock"].acquire()
                        if dst in self.recv_buffer["buffers"].keys():
                            self.recv_buffer["buffers"][dst].append(data_dict)
                            logging.critical("ENB("+str(self.uid)+"): Data destined for UE("+str(dst)+") with chunk("+str(chunk_num)+") is buffered")
                        self.recv_buffer["lock"].release()
                        pass
                    else:
                        logging.info("ENB("+str(self.uid)+ "): The chunk("+str(chunk_num)+") of message from UE("+str(source)+") to UE("+str(dst)+") is received")
                        self.trans_buffer["lock"].acquire()
                        if (dst in self.trans_buffer["buffers"].keys()):
                            self.trans_buffer["buffers"][dst].append(data_dict)
                            self.trans_buffer["lock"].release()
                            logging.critical("ENB("+str(self.uid)+"): The chunk("+str(chunk_num)+") of message from UE("+str(source)+") to UE("+str(dst)+") is buffered")
                        else:
                            self.trans_buffer["lock"].release()
                            logging.critical("ENB("+str(self.uid)+"): The chunk("+str(chunk_num)+") of message from UE("+str(source)+") to UE("+str(dst)+") should be sent")
                            while ("data_socket" not in self.database[dst].keys()):
                                time.sleep(0.02)
                            self.send_data_to_user(dst, data_dict.copy())

                elif (data_dict["type"] == 11):
                    source_enb = data_dict["message"]["source_enb"]
                    user_id = data_dict["message"]["uid"]
                    logging.critical("ENB("+str(self.uid)+"): The buffered data of UE("+str(user_id)+") is requested from ENB("+str(source_enb)+")") 
                    buffered_data = threading.Thread(target=self.send_buffered_data, args=(source_enb, user_id))
                    buffered_data.start()

                elif (data_dict["type"] == 12):
                    user_id = data_dict["message"]["uid"]
                    data = data_dict["message"]["data"]

                    self.trans_buffer["lock"].acquire()
                    try:
                        self.trans_buffer["buffers"][user_id].append(data)
                    except:
                        print("ENB("+str(self.uid)+"): Error in adding chunk("+str(data["message"]["chunk_num"])+") of UE("+str(user_id)+") ")
                    self.trans_buffer["lock"].release()
                
                elif (data_dict["type"] == 13):
                    # handover completion message is received
                    user_id = data_dict["message"]["uid"]
                    
                    # delivering the buffered data to the user
                    logging.critical("ENB("+str(self.uid)+"): Handover Completion Message is received for UE(" + str(user_id)+")")
                    threading.Thread(target=self.deliver_buffered_data, args=(user_id, )).start()




    def deliver_buffered_data(self, user_id):
        '''Delivers the buffered data in the new eNodeB to the user'''
        self.trans_buffer["lock"].acquire()
        user_found = False
        if user_id in self.trans_buffer["buffers"].keys():
            user_found = True
            buffered_data = self.trans_buffer["buffers"][user_id]
            logging.critical("ENB("+str(self.uid)+"): Trans buffer of UE("+str(user_id)+") is removed")
            self.trans_buffer["buffers"].pop(user_id)
        self.trans_buffer["lock"].release()
        
        # sorting the buffered data
        if user_found:
            buffered_data.sort(key=lambda x: x["message"]["chunk_num"])
            for data_dict in buffered_data:
                dst = data_dict["message"]["dst"]
                msg = data_dict.copy()
                while ("data_socket" not in self.database[dst].keys()):
                    time.sleep(0.02)
                self.send_data_to_user(dst, msg)
            


    def connect_to_mme(self, mme_port):
        HOST = "127.0.0.1"
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_status = s.connect_ex((HOST, mme_port))
        while (connection_status != 0):
            connection_status = s.connect_ex((HOST, mme_port))

        logging.info("ENB("+str(self.uid)+"): Connection with MME is established on port:(%d)", mme_port)
        socket_lock = threading.Lock()
        self.mme_socket = {"socket":s, "lock":socket_lock}
        # sending a eNodeB-MME Connection message
        msg = {"type":2, "message": self.uid}
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        logging.debug("ENB("+str(self.uid)+"): Sending the eNodeB-MME connection message")
        socket_lock.acquire()
        s.sendall(msg_json.encode("utf-8"))
        socket_lock.release()
        while True :
            # data received from client
            data = s.recv(2048)
            if not data:
                # the connection was closed
                break

            # decoding the data
            data_received = data.decode('utf-8').split("\END_OF_MSG")
            for data_decoded in data_received[:-1]:
                try:
                    if (len(data_decoded)!=0):
                        data_dict = json.loads(data_decoded)
                except:
                    logging.warning("ENB("+str(self.uid)+"): Data received from MME is corrupted")
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
                    msg = {"type":7, "message": {"uid":self.uid}}
                    self.send_signal_to_user(user_uid, msg)
                    if (has_previous):
                        self.send_me_buffered_data(previous_enb, user_uid)
                        
                        # adding the uid to key of the dictionary of buffered messages
                        self.trans_buffer["lock"].acquire()
                        self.trans_buffer["buffers"][user_uid] = []
                        self.trans_buffer["lock"].release()


                    
                    

                elif (data_dict["type"] == 8):
                    # Release connection
                    user_uid = data_dict["message"]["uid"]
                    next_enb = data_dict["message"]["next_enb"]
                    self.covered_users.remove(user_uid)
                    logging.info("ENB("+str(self.uid)+"): Data channel with UE("+str(user_uid)+") is closed and it is now connected to ENB("
                    +str(next_enb)+")")
                    self.db_lock.acquire()
                    if ("data_socket" in self.database[user_uid].keys()):
                        self.database[user_uid].pop("data_socket")
                        self.database[user_uid].pop("data_lock")
                    self.db_lock.release()
                    
                    # Add the user uid as a key of the dictionary of data that should be buffered
                    self.recv_buffer["lock"].acquire()
                    self.recv_buffer["buffers"][user_uid] = []
                    self.trans_buffer["lock"].acquire()
                    if (user_uid in self.trans_buffer["buffers"].keys()):
                        self.recv_buffer["buffers"][user_uid] = self.trans_buffer["buffers"][user_uid].copy()
                        self.trans_buffer["buffers"].pop(user_uid)
                    self.trans_buffer["lock"].release()
                    self.recv_buffer["lock"].release()

    def send_me_buffered_data(self,previous_enb, user_uid):
        '''Sends a send me buffered data message to the previous eNodeB'''
        msg = {"type": 11, "message":{"uid":user_uid, "dst_enb":previous_enb, "source_enb":self.uid}}
        self.send_to_sgw(msg)   

    def send_buffered_data(self, next_enb, user_uid):
        '''Sends the buffered data to the next eNodeB''' 
        self.recv_buffer["lock"].acquire()
        if user_uid not in self.recv_buffer["buffers"].keys():
            logging.critical("ENB("+str(self.uid)+"): UE("+str(user_uid)+") has nothing in the received data buffer")
            self.recv_buffer["lock"].release()
        else:
            logging.critical("ENB("+str(self.uid)+"): Sending UE("+str(user_uid)+") buffered data to ENB("+str(next_enb)+")")
            buffered_data = self.recv_buffer["buffers"][user_uid]
            self.recv_buffer["buffers"].pop(user_uid)
            self.recv_buffer["lock"].release()
            for data in buffered_data:
                msg = {"type": 12, "message":{"uid": user_uid, "dst": next_enb, "data": data}}
                logging.critical("ENB("+str(self.uid)+"): Sending message chunk("+str(data["message"]["chunk_num"])+") of UE("+str(user_uid)+") to ENB("+str(next_enb) + ")")
                self.send_to_sgw(msg)
            
            # sending handover completion message
            logging.critical("ENB("+str(self.uid)+"): Sending handover completion to ENB("+str(next_enb)+") for UE("+str(user_uid)+")")
            msg = {"type": 13, "message":{"uid": user_uid, "dst": next_enb}}
            self.send_to_sgw(msg)
    




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

            # data received from client
            data = c.recv(1024)
            if not data:
                # the connection was closed
                break
            
            # decoding the data
            data_received = data.decode('utf-8').split("\END_OF_MSG")
            #print(data_received)
            for data_decoded in data_received[:-1]:
                try:
                    if (len(data_decoded)!=0):
                        data_dict = json.loads(data_decoded)
                    else :
                        data_dict = None
                except:
                    logging.warning("ENB("+str(self.uid)+"): Data received from UE("+str(client_uid)+") is corrupted")
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

                elif (data_dict["type"] == 9):
                    # session creation message 
                    logging.critical("ENB("+str(self.uid)+"): Session Creation is received from UE("+str(client_uid)+")")
                    msg = data_dict.copy()
                    self.send_to_sgw(msg)

                elif (data_dict["type"] == 10):
                    # session creation ack
                    logging.critical("ENB("+str(self.uid)+"): Session Creation ACK is received from UE("+str(client_uid)+")")
                    msg = data_dict.copy()
                    self.send_to_sgw(msg)
            
    
    def handle_data_nodes(self, c, addr):
        client_uid = None
        socket_lock = threading.Lock()
        while True:

            # data received from client
            try:
                data = c.recv(1024)
            except ConnectionResetError:
                break
            if not data:
                # the connection was closed
                logging.debug("ENB("+str(client_uid)+"): Connection with UE("+ str(client_uid)+") is closed")
                break
            
            # decoding the data
            data_received = data.decode('utf-8').split("\END_OF_MSG")
            for data_decoded in data_received[:-1]:
                try:
                    if (len(data_decoded)!=0):
                        data_dict = json.loads(data_decoded)
                    else :
                        data_dict = None
                except:
                    logging.warning("ENB("+str(self.uid)+"): Data received from UE("+str(client_uid)+") is corrupted")
                if data_dict is None:
                    pass
                elif (data_dict["type"] == 17):
                    # UID announcement after the data channel creation
                    client_uid = data_dict["message"]["uid"]
                    self.db_lock.acquire()
                    self.database[client_uid]["data_socket"] = c
                    self.database[client_uid]["data_lock"] = socket_lock
                    self.db_lock.release()
                
                elif (data_dict["type"] == 16):
                    # forward the data to SGW
                    logging.critical("ENB("+str(self.uid)+"): Data received UE("+str(client_uid)+") is sent to SGW")
                    self.send_to_sgw(data_dict)
                
                

                    
        

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
        self.mme_socket["lock"].acquire()
        self.mme_socket["socket"].sendall(msg_json.encode("utf-8"))
        self.mme_socket["lock"].release()

    def send_to_sgw(self, msg):
        '''Sends a message to the SGW server'''
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        self.sgw_socket["lock"].acquire()
        self.sgw_socket["socket"].sendall(msg_json.encode("utf-8"))
        self.sgw_socket["lock"].release()

    def send_signal_to_user(self, user_uid, msg):
        '''Sends a message to the user with the given user_uid and msg'''
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        c, socket_lock = self.database[user_uid]["signaling_socket"], self.database[user_uid]["signaling_lock"]
        socket_lock.acquire()
        c.sendall(msg_json.encode("utf-8"))
        socket_lock.release()
        #print("ENB("+str(self.uid)+"): Sending data '"+str(msg_json)+"' to UE("+str(user_uid)+")")

    def send_data_to_user(self, user_uid, msg):
        '''Sends the data to the user with the given uid and msg'''
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        try:
            c, socket_lock = self.database[user_uid]["data_socket"], self.database[user_uid]["data_lock"]
            socket_lock.acquire()
            c.sendall(msg_json.encode("utf-8"))
            socket_lock.release()
        except: 
            print("ENB("+str(self.uid)+"): Trying to send " + msg_json + "failed!")

        


    
