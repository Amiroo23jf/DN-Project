import threading
import socket
import json
import logging


class eNodeB():
    def __init__(self, location, uid):
        self.location = location
        self.uid = uid
        logging.debug("eNodeB with uid: "+ str(self.uid) + " is successfully created.")

    def connect_to_sgw(self, sgw_port):
        HOST = "127.0.0.1"
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_status = s.connect_ex((HOST, sgw_port))
        while (connection_status != 0):
            connection_status = s.connect_ex((HOST, sgw_port))

        logging.info("ENB"+str(self.uid)+": Connection with SGW is established on port:(%d)", sgw_port)
        # sending a eNodeB-SGW Connection message
        msg = {"type":1, "message": self.uid}
        msg_json = json.dumps(msg, indent=4)
        logging.debug("Sending the eNodeB-SGW connection message from eNodeB with uid: " + str(self.uid))
        s.sendall(msg_json.encode("utf-8"))
        while True :
            pass

    def connect_to_mme(self, mme_port):
        HOST = "127.0.0.1"
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_status = s.connect_ex((HOST, mme_port))
        while (connection_status != 0):
            connection_status = s.connect_ex((HOST, mme_port))

        logging.info("ENB"+str(self.uid)+": Connection with MME is established on port:(%d)", mme_port)
        # sending a eNodeB-MME Connection message
        msg = {"type":2, "message": self.uid}
        msg_json = json.dumps(msg, indent=4)
        logging.debug("Sending the eNodeB-MME connection message from eNodeB with uid: " + str(self.uid))
        s.sendall(msg_json.encode("utf-8"))
        while True :
            pass