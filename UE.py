import threading
import socket
import logging
import time
import json

class UE():
    def __init__(self, user_info, enb_ports):
        self.uid =  user_info["uid"]
        self.interval = user_info["interval"]
        self.locations= user_info["locations"]
        self.enb_ports = enb_ports
        self.signaling_sockets = dict()

        # data channel 
        self.data_socket = {"socket": None, "lock": threading.Lock()}
        self.close_connection_lock = threading.Lock()
        self.close_connection = False
        self.data_enb_uid = {"uid": None, "lock": threading.Lock()}

        # session handling
        self.recv_sessions = {"sessions": list(), "lock": threading.Lock()} # holds the active sessions that the user is their receiver
        self.pending_sessions = {"sessions": list(), "lock": threading.Lock()} # holds sessions that are waiting for the ack
        self.trans_sessions = {"sessions": list(), "lock": threading.Lock()} # holds the active sessions that the user is their transmitter
        self.session_chunks = dict()
        self.session_contents = dict()

        # simulation timing configurations
        self.sim_started = False
        self.start_time = None 
        logging.debug("UE with uid:(%d) is successfully created", self.uid)

    def connect_enb_signalings(self):
        HOST = "127.0.0.1"
        for enb_uid in self.enb_ports.keys():
            enb_port = self.enb_ports[enb_uid]["signaling"]
            addr = (HOST, enb_port)
            signaling_connection = threading.Thread(target=self.connect_enb_signaling, args=(addr, enb_uid))
            signaling_connection.start()
    
    def connect_enb_signaling(self, enb_addr, enb_uid):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_status = s.connect_ex(enb_addr)
        while (connection_status != 0):
            connection_status = s.connect_ex(enb_addr)
        logging.info("UE("+str(self.uid)+"): Connection with ENB is established on port:("+str(enb_addr[1])+")")
        # saving the socket for future use
        socket_lock = threading.Lock()
        self.signaling_sockets[enb_uid] = {"socket":s, "lock": socket_lock}

        # sending signaling channel setup message
        msg = {"type":3, "message": self.uid}
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        logging.debug("UE(" + str(self.uid) + "): Sending the Signaling Channel Setup message to port:("+str(enb_addr[1])+")")
        s.sendall(msg_json.encode("utf-8"))

        # First Stage: Waiting for the simulation to start
        while True :
            if (self.sim_started):
                break

        #logging.debug("UE("+str(self.uid)+"): Simulation is started")
        # Second Stage: Simulation is started the position should be sent 

        # creating the list of location update times
        locations = self.locations.copy()
        interval = float(self.interval[:-1])
        update_times = list()
        t0 = 0
        for i in range(len(locations)):
            update_times.append(t0)
            t0 = t0 + interval

        signaling_handler = threading.Thread(target=self.handle_signaling, args=(s, socket_lock))
        signaling_handler.start()
        while True:
            if (len(update_times)>=1):
                next_update_time = update_times[0]
                new_location = locations[0]
                current_time = time.time() - self.start_time
                if (current_time >= next_update_time):
                    socket_lock.acquire()
                    self.send_new_location(new_location, next_update_time, enb_addr[1], s)
                    socket_lock.release()
                    locations.pop(0)
                    update_times.pop(0)
            
    def handle_signaling(self, s, socket_lock):
        '''Handles the signals received from the eNodeB'''
        while True:
            # data received from client
            #print("something is received")
            data = s.recv(1024)
            if not data:
                # the connection was closed
                break

            # decoding the data
            data_received = data.decode('utf-8').split("\END_OF_MSG")
            #print("UE("+str(self.uid)+"): '"+str(data_received) + "' received from ENB")
            for data_decoded in data_received[:-1]:
                try:
                    if (len(data_decoded)!=0):
                        data_dict = json.loads(data_decoded)
                except:
                    logging.warning("UE("+str(self.uid)+"): Data received from ENB is corrupted")
                if (data_dict["type"] == 7):
                    # create a new data channel
                    enb_uid = data_dict["message"]["uid"]
                    enb_port = self.enb_ports[enb_uid]["data"]
                    logging.info("UE("+str(self.uid)+"): New data channel should be created with ENB on port:(" + str(enb_port) + ")")
                    data_channel_thread = threading.Thread(target=self.create_data_channel, args=(enb_port, enb_uid))
                    if self.data_socket["socket"] == None:
                        data_channel_thread.start()
                    else: 
                        # close connection on socket self.data_socket and create the new data channel
                        self.close_connection_lock.acquire()
                        self.close_connection = True
                        self.close_connection_lock.release()


                        # waits until the previous channel is closed properly
                        while (self.close_connection):
                            time.sleep(0.05)
                        data_channel_thread.start()


                elif (data_dict["type"] == 9):
                    # Session creation message is received 
                    source = data_dict["message"]["source"]
                    dst = data_dict["message"]["dst"]
                    session_time = data_dict["message"]["time"]
                    session_id = (source, session_time)
                    logging.debug("UE("+str(self.uid)+"): Session Creation with me is received from UE("+str(source)+")")
                    if (dst != self.uid):
                        logging.error("UE("+str(self.uid)+"): The Session creation was not targeted for me")

                        ############ Handle Wrong Session Creation ############
                    else:
                        self.recv_sessions["lock"].acquire()
                        if (session_id in self.recv_sessions["sessions"]):
                            # This might happen when ack is not received by the session creator or it was received after a given timeout
                            self.recv_sessions["lock"].release()
                        else:
                            self.recv_sessions["sessions"].append(session_id)
                            self.recv_sessions["lock"].release()
                        self.ack_create_session(session_id)

                elif (data_dict["type"] == 10):
                    # session creation ack is received
                    source = data_dict["message"]["source"]
                    dst = data_dict["message"]["dst"]
                    session_time = data_dict["message"]["time"]
                    session_id = (source, session_time)
                    logging.debug("UE("+str(self.uid)+"): Session Creation ACK is received from UE("+str(source)+")")
                    if (dst != self.uid):
                        logging.error("UE("+str(self.uid)+"): The Session creation ACK was not targeted for me")

                        ############ Handle Wrong Session Creation ############
                    else: 
                        self.trans_sessions["lock"].acquire()
                        if (session_id in self.trans_sessions["sessions"]):
                            self.trans_sessions["lock"].release()
                        else:
                            self.trans_sessions["lock"].release()
                            self.pending_sessions["lock"].acquire()
                            if (session_id in self.pending_sessions["sessions"]):
                                self.pending_sessions["sessions"].remove(session_id)
                            self.pending_sessions["lock"].release()
                        



                

    def create_data_channel(self,enb_port, enb_uid):
        '''Creates a new data channel with a thread for receiving data and a thread for sending data'''
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_status = s.connect_ex(('127.0.0.1',enb_port))
        while (connection_status != 0):
            connection_status = s.connect_ex('127.0.0.1',enb_port)
        logging.critical("UE("+str(self.uid)+"): Data Channel with ENB on port:("+str(enb_port)+") is established")

        # change the data eNodeB UID
        self.data_enb_uid["lock"].acquire()
        self.data_enb_uid["uid"] = enb_uid
        self.data_enb_uid["lock"].release()

        # change the data channel socket
        self.data_socket["lock"].acquire()
        self.data_socket["socket"] = s
        
        # sending the users uid to the enb using the data channel
        msg = {"type": 17, "message":{"uid": self.uid}}
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        self.data_socket["socket"].sendall(msg_json.encode("utf-8"))
        self.data_socket["lock"].release()

        # run a data receiver thread
        data_channel_handler = threading.Thread(target=self.handle_data_channel, args=())
        data_channel_handler.start()

    def handle_data_channel(self):
        '''Handles the messages received from the data channel'''
        self.data_socket["socket"].settimeout(2)
        while True:
            # check if data channel should be closed 
            self.close_connection_lock.acquire()
            if (self.close_connection):
                # close the socket
                self.data_socket["lock"].acquire()
                self.data_socket["socket"].close()
                self.data_socket["lock"].release()

                # set the close connection to False which means that this channel is successfully closed
                self.close_connection = False
                #logging.critical("UE("+str(self.uid)+"): Data Channel with ENB on port:("+str(self.enb_ports[self.data_enb_uid]["data"])+") is closed")
                self.close_connection_lock.release()
                break
            self.close_connection_lock.release()


            # if data channel should not be closed, then continue receiving data
            

            ########### write receiver ###########
            try:
                if (self.data_socket["socket"]._closed == False):
                    data = self.data_socket["socket"].recv(1024)
                else:
                    data = None
            except socket.timeout:
                continue

            if not data:
                # the connection was closed
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
                    #logging.warning("ENB("+str(self.uid)+"): Data received from UE("+str()+") is corrupted")
                    pass
                if data_dict is None:
                    pass 
                elif (data_dict["type"] == 16):
                    source = data_dict["message"]["source"]
                    chunk_num = data_dict["message"]["chunk_num"]
                    session = tuple(data_dict["message"]["session"])
                    last_chunk = data_dict["message"]["last_chunk"]
                    chunk = data_dict["message"]["content"]
                    logging.info("UE("+str(self.uid)+"): The chunk("+str(chunk_num)+") of data from UE("+str(source)+") is received")

                    # adding the chunk to the session chunk
                    if session not in self.session_chunks.keys():
                        self.session_chunks[session] = [(chunk_num, chunk)]
                        logging.critical("UE("+str(self.uid)+"): chunk("+str(chunk_num)+") is received:\n '"+chunk+"'")
                        stick_chunks_thread = threading.Thread(target=self.chunk_stickng, args=(session, last_chunk))
                        stick_chunks_thread.start()
                    else:
                        try:
                            logging.critical("UE("+str(self.uid)+"): chunk("+str(chunk_num)+") is received:\n '"+chunk+"'")
                            self.session_chunks[session].append([chunk_num, chunk])

                        except:
                            pass
                    
    def chunk_stickng(self, session, last_chunk):
        '''Sticks the chunks of the same session together'''
        TIMEOUT = 10
        start_time = time.time()
        chunk_len = 1
        while True:
            if ((time.time() > start_time + TIMEOUT)):
                if((len(self.session_chunks[session]) == chunk_len)):
                    break
                else:
                    chunk_len = len(self.session_chunks[session])
                    #print(chunk_len)
                    start_time = time.time()
                    if (chunk_len == last_chunk + 1):
                        break
        
        self.session_chunks[session].sort(key=lambda x: x[0])
        content = ""
        for chunk in list(map(lambda x: x[1], self.session_chunks[session])):
            content += chunk
        self.session_contents[session] = content

        logging.critical("UE("+str(self.uid)+"): Content received in session:("+str(session)+") is \n\n '"+content+"' \n" )
        





    def start_simulation(self, start_time):
        '''This method is called by LTESimulator when the simulation is started by giving the start time of 
        the simulation and setting the sim_started parameter to True'''
        self.start_time = start_time
        self.sim_started = True

    def send_new_location(self, new_location, current_time, port, s):
        '''Sending the new location to the given port using the socket "s"''' 
        # sending location announcement message
        msg = {"type":0, "message":{"position":new_location, "uid":self.uid, "time":current_time}}
        msg_json = json.dumps(msg, indent=4) + "\END_OF_MSG"
        logging.debug("UE("+str(self.uid)+"): Sending position announcement in time:("+"{:.2f}".format(current_time)+") to port:("+str(port)+")")
        s.sendall(msg_json.encode("utf-8"))

    def send_data(self, dst, when, content, chunk_num):
        '''Runs a scenario and sends the content to the given destination'''
        logging.info("UE("+str(self.uid)+"): Sending data to UE("+str(dst)+") at time:("+"{:.2f}".format(when)+") with real time:("+"{:.2f}".format(time.time() - self.start_time)+")")
        self.create_session(dst, when)

        # now lets send the content to the given destination
        # splitting the content to the given number of chunks
        content_list = []
        content_len = len(content)
        chunk_len = content_len // chunk_num
        for i in range(chunk_num):
            if (i == chunk_num - 1):
                content_list.append(content[i*chunk_len:])
            else:
                content_list.append(content[i*chunk_len:(i+1)*chunk_len])
        
        # content_list is created. Now we should send the content

        for i in range(len(content_list)):
            chunk = content_list[i]
            msg = {"type": 16, "message": {"source": self.uid, "dst": dst, "session": (self.uid, when), "chunk_num": i, "last_chunk": chunk_num-1, 
                    "content": chunk}}
            msg_json = json.dumps(msg) + "\END_OF_MSG"
            # check if the socket is open
            self.data_socket["lock"].acquire()
            if (self.data_socket["socket"]._closed):
                self.data_socket["lock"].release()
                while (self.data_socket["socket"]._closed):
                    time.sleep(0.02) # can be replaced with pass
                
                # we again lock the socket in order to make sure it is not going to be closed in the sending period
                self.data_socket["lock"].acquire()


            # we now have a working socket that we can use to send 
            #print(self.data_socket["socket"]._closed)
            self.data_socket["socket"].sendall(msg_json.encode("utf-8"))
            self.data_socket["lock"].release()
            time.sleep(0.03)
            logging.critical("UE("+str(self.uid)+"): Sending chunk("+str(i)+") to UE("+str(dst)+")")




        
        
    
    def create_session(self, dst, when, ACK_TIMEOUT=1):
        '''Creating a new session to the given destination in the given time'''
        self.data_enb_uid["lock"].acquire()
        signaling_port = self.enb_ports[self.data_enb_uid["uid"]]["signaling"]
        logging.critical("UE("+str(self.uid)+"): Sending UE("+str(dst)+") a Session Creation Request via ENB("+str(self.data_enb_uid["uid"])+") on port:("+str(signaling_port)+")")
        session_id = (dst, when)
        msg = {"type": 9, "message":{"source":self.uid, "dst": dst, "time": when}}
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        self.signaling_sockets[self.data_enb_uid["uid"]]["lock"].acquire()
        self.signaling_sockets[self.data_enb_uid["uid"]]["socket"].sendall(msg_json.encode("utf-8"))
        self.signaling_sockets[self.data_enb_uid["uid"]]["lock"].release()
        self.data_enb_uid["lock"].release()

        # putting the session in the pending list
        self.pending_sessions["lock"].acquire()
        self.pending_sessions["sessions"].append(session_id)
        self.pending_sessions["lock"].release()

        # now we should wait until the session the ack is received
        send_time = time.time()
        while True:
            self.pending_sessions["lock"].acquire()
            if (session_id not in self.pending_sessions["sessions"]):
                self.pending_sessions["lock"].release()
                self.trans_sessions["lock"].acquire()
                self.trans_sessions["sessions"].append(session_id)
                self.trans_sessions["lock"].release()
                break
            else:
                
                self.pending_sessions["lock"].release()
                if (time.time() >= send_time + ACK_TIMEOUT):
                    self.data_enb_uid["lock"].acquire()
                    self.signaling_sockets[self.data_enb_uid["uid"]]["lock"].acquire()
                    self.signaling_sockets[self.data_enb_uid["uid"]]["socket"].sendall(msg_json.encode("utf-8"))
                    self.signaling_sockets[self.data_enb_uid["uid"]]["lock"].release()
                    self.data_enb_uid["lock"].release()
                    send_time = time.time()
        
        logging.critical("UE("+str(self.uid)+"): Session with UE("+str(dst)+") is successfully created (Request time:("+"{:.2f}".format(when)+
                         "), Creation time:("+"{:.2f}".format(time.time() - self.start_time)+")")
        
                

                

    def ack_create_session(self, session_id):
        '''Sends the ACK of the session creation message'''
        dst = session_id[0]
        when = session_id[1]
        
        self.data_enb_uid["lock"].acquire()
        signaling_port = self.enb_ports[self.data_enb_uid["uid"]]["signaling"]
        logging.critical("UE("+str(self.uid)+"): Sending UE("+str(dst)+") a Session Creation ACK via ENB("+str(self.data_enb_uid["uid"])+") on port:("+str(signaling_port)+
                        ") (Request time:("+"{:.2f}".format(when)+"), ACK time:("+"{:.2f}".format(time.time() - self.start_time) + "))")
        msg = {"type": 10, "message": {"source":self.uid, "dst": dst, "time": when}}

        # sending the ACK
        msg_json = json.dumps(msg) + "\END_OF_MSG"
        self.signaling_sockets[self.data_enb_uid["uid"]]["lock"].acquire()
        self.signaling_sockets[self.data_enb_uid["uid"]]["socket"].sendall(msg_json.encode("utf-8"))
        self.signaling_sockets[self.data_enb_uid["uid"]]["lock"].release()

        self.data_enb_uid["lock"].release()

        
