from enodeb import eNodeB
from mme import MME
from sgw import SGW
from ue import UE
import threading
import logging
import random
import time

class LTESimulator():
    def __init__(self, enb_locations, users_info, logging_level=logging.INFO):
        '''Initializing the Simulator'''
        if (logging_level==logging.INFO):
            logging.basicConfig(format="%(message)s", level=logging_level)
        else:
            logging.basicConfig(format="-%(levelname)s- %(message)s", level=logging_level)
        self.enb_locations = enb_locations
        self.users_info = users_info
        self.ports = dict()
        self.enb_list = list()
        self.ue_list = list()
        self.mme_timeout = self.find_timeout(users_info)
        return
    
    def find_timeout(self, users_info):
        min_time = float("inf")
        for user in users_info:
            user_interval = float(user["interval"][:-1])
            if (user_interval < min_time):
                min_time = user_interval
        return min_time/4

    def topology_configuration(self):
        '''This method configures the topology by bringing up the MME and SGW servers and connecting eNodeBs to them'''
        # creating the MME
        # setting a random port number
        port = random.randint(10000,65000)
        self.ports["mme"] = port
        mme_entity = MME(port, self.mme_timeout)
        mme_server_thread = threading.Thread(target=mme_entity.run_server, args=())
        mme_server_thread.start()
        self.mme = mme_entity
        
        # creating the SGW
        port = port + 1
        self.ports["sgw"] = port
        sgw_entity = SGW(port)
        sgw_server_thread = threading.Thread(target=sgw_entity.run_server, args=())
        sgw_server_thread.start()
        self.sgw = sgw_entity

        # connecting MME to SGW
        mme_connect_to_sgw = threading.Thread(target=mme_entity.connect_to_sgw, args=(self.ports["sgw"],))
        mme_connect_to_sgw.start()

        # connecting SGW to MME
        sgw_connect_to_mme = threading.Thread(target=sgw_entity.connect_to_mme, args=(self.ports["mme"],))
        sgw_connect_to_mme.start()

        # creating the eNodeBs
        ## just a initial uid
        uid = 5000 

        # list containing the tuples of enb uids and ports
        enb_signaling_ports = []

        # lists for holding the threads
        enb_sgw_connections = []
        enb_mme_connections = []
        enb_signaling_servers = []
        enb_data_servers = []   
        user_enb_signalings = []
        
        for i in range(len(self.enb_locations)):
            enb_loc = self.enb_locations[i]
            enb = eNodeB(enb_loc, uid)
            self.enb_list.append(enb)
            # connecting the eNodeB to SGW server
            enb_sgw_connections.append(threading.Thread(target=enb.connect_to_sgw, args=(self.ports["sgw"],)))
            enb_sgw_connections[i].start()

            # connecting the eNodeB to MME server
            enb_mme_connections.append(threading.Thread(target=enb.connect_to_mme, args=(self.ports["mme"],)))
            enb_mme_connections[i].start()

            # creating signaling server
            port = port + 1
            self.ports["enb"+str(uid)+"-signaling"] = port
            enb_signaling_servers.append(threading.Thread(target=enb.run_server, args=(self.ports["enb"+str(uid)+"-signaling"],True)))
            enb_signaling_servers[i].start()
            
            enb_signaling_ports.append(port) # adding the signaling port in order to be used by UEs


            # creating data server
            port = port + 1
            self.ports["enb"+str(uid)+"-data"] = port
            enb_data_servers.append(threading.Thread(target=enb.run_server, args=(self.ports["enb"+str(uid)+"-data"],False)))
            enb_data_servers[i].start()
            
            uid = uid + 1

        logging.debug("Topology is successfully configured")

        # creating the users 
        for i in range(len(self.users_info)):
            user_info = self.users_info[i]
            user = UE(user_info)
            self.ue_list.append(user)
            user_enb_signalings.append(threading.Thread(target=user.connect_enb_signalings, args=(enb_signaling_ports, )))
            user_enb_signalings[i].start()
        
        self.enb_sgw_connections = enb_sgw_connections
        self.enb_mme_connections = enb_mme_connections
        self.enb_signaling_servers = enb_signaling_servers
        self.enb_data_servers = enb_data_servers  
        self.user_enb_signalings = user_enb_signalings 
        
    def start_simulation(self):
        '''Starting the simulation and initializing the timing on each entity'''
        self.start_time = time.time()
        
        self.mme.start_simulation(self.start_time)
        self.sgw.start_simulation(self.start_time)

        for enb in self.enb_list:
            enb.start_simulation(self.start_time)
        
        for ue_entity in self.ue_list:
            ue_entity.start_simulation(self.start_time)

        logging.debug("Simulation is started")
users_info = [{"uid":12252, "interval":"4s", "locations":[(3,0), (3,3), (2.5,0), (0,2.5)]}, 
              {"uid":76295, "interval":"4.2s", "locations":[(0,1), (1,0), (2.5,2.5), (8,5)]},
              {"uid":7295, "interval":"5.3s", "locations":[(0,0), (5,0), (2,3), (-1,4)]}]

# users_info = [{"uid":12252, "interval":"5s", "locations":[(1,5)]}, 
#               {"uid":76295, "interval":"5s", "locations":[(1,8)]},
#               {"uid":12252, "interval":"5s", "locations":[(9,6)]}]
lte_simulator = LTESimulator([(2,0),(2,2),(0,2)], users_info, logging_level=logging.INFO)
lte_simulator.topology_configuration()
time.sleep(2)
logging.info("------------------Starting the simulation----------------")
lte_simulator.start_simulation()
