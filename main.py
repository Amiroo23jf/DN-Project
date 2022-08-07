from enodeb import eNodeB
from mme import MME
from sgw import SGW
from ue import UE
import threading
import logging
import random

class LTESimulator():
    def __init__(self, enb_locations, users_info, logging_level=logging.INFO):
        '''Initializing the Simulator'''
        logging.basicConfig(format="%(levelname)s: %(message)s", level=logging_level)
        self.enb_locations = enb_locations
        self.users_info = users_info
        self.ports = dict()
        self.enb_list = list()
        return
    
    def topology_configuration(self):
        '''This method configures the topology by bringing up the MME and SGW servers and connecting eNodeBs to them'''
        # creating the MME
        # setting a random port number
        port = random.randint(10000,65000)
        self.ports["mme"] = port
        mme_entity = MME(port)
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
        for i in range(len(self.enb_locations)):
            enb_loc = self.enb_locations[i]
            enb = eNodeB(enb_loc, uid)
            self.enb_list.append(enb)
            # connecting the eNodeB to SGW server
            enb_sgw_connection = threading.Thread(target=enb.connect_to_sgw, args=(self.ports["sgw"],))
            enb_sgw_connection.start()

            # connecting the eNodeB to MME server
            enb_mme_connection = threading.Thread(target=enb.connect_to_mme, args=(self.ports["mme"],))
            enb_mme_connection.start()
            
            uid = uid + 1

        # creating the users 
        for i in range(len(self.users_info)):
            user_info = self.users_info[i]
            user = UE(user_info)

        
        logging.debug("Topology is successfully configured")
    
    def create_ue_enb_signaling(self):
        pass

users_info = [{"uid":12252, "interval":"2s", "locations":[(1,5), (2,5), (6,2), (8,1)]}, 
              {"uid":76295, "interval":"1s", "locations":[(1,8), (9,5), (3,2), (8,4)]},
              {"uid":12252, "interval":"2s", "locations":[(9,6), (9,1), (3,6), (2,1)]}]
lte_simulator = LTESimulator([(1,1),(2,2),(3,3)], users_info, logging_level=logging.DEBUG)
lte_simulator.topology_configuration()
