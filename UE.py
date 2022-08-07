import threading
import socket
import logging
import time

class UE():
    def __init__(self, user_info):
        self.uid =  user_info["uid"]
        self.interval = user_info["interval"]
        self.locations= user_info["locations"]
        logging.debug("UE with uid:(%d) is successfully created", self.uid)

    