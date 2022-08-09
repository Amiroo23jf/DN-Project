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
        self.data_socket = None
        self.close_connection_lock = threading.Lock()
        self.close_connection = False
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
        msg_json = json.dumps(msg, indent=4) + "\END_OF_MSG"
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

        socket_lock = threading.Lock()
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
        '''Handles the signals recieved from the eNodeB'''
        while True:
            # data recieved from client
            data = s.recv(2048)
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
                    logging.warning("UE("+str(self.uid)+"): Data recieved from ENB is corrupted")
                if (data_dict["type"] == 7):
                    # create a new data channel
                    enb_port = data_dict["message"]["port"]
                    logging.debug("UE("+str(self.uid)+"): New data channel should be created with ENB on port:(" + str(enb_port) + ")")
                    if self.data_socket == None:
                        self.create_data_channel(enb_port)
                    else: 
                        # close connection on socket self.data_socket and create the new data channel
                        self.close_connection_lock.acquire()
                        self.close_connection = True
                        self.close_connection_lock.release()
                        while (self.close_connection):
                            pass
                        self.create_data_channel(enb_port)
                

    def create_data_channel(self,enb_port):
        '''Creates a new data channel with a thread for receiving data and a thread for sending data'''
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_status = s.connect_ex(('127.0.0.1',enb_port))
        while (connection_status != 0):
            connection_status = s.connect_ex('127.0.0.1',enb_port)
        logging.info("UE("+str(self.uid)+"): Data Channel with ENB on port:("+str(enb_port)+") is established")
        self.data_socket = s
        while True:
            self.close_connection_lock.acquire()
            if (self.close_connection):
                s.close()
                logging.info("UE("+str(self.uid)+"): Data Channel with ENB on port:("+str(enb_port)+") is closed")
                self.close_connection = False
                self.close_connection_lock.release()
                break
            self.close_connection_lock.release()


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