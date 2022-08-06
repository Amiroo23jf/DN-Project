import threading
import socket

class UE():
    def __init__(self, uid, interval,locations):
        self.uid = uid 
        self.interval = interval
        self.locations=locations
        
        return