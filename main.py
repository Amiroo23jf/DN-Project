from enodeb import eNodeB
from mme import MME
from sgw import SGW
from ue import UE
import threading
import logging
import random
import time
import json

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
        self.enb_dict = dict()
        self.ue_dict = dict()
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

        # dictionary mapping enb uids to ports
        enb_ports = dict()

        # lists for holding the threads
        enb_sgw_connections = []
        enb_mme_connections = []
        enb_signaling_servers = []
        enb_data_servers = []   
        user_enb_signalings = []
        
        for i in range(len(self.enb_locations)):
            enb_loc = self.enb_locations[i]
            enb = eNodeB(enb_loc, uid)
            self.enb_dict[uid] = enb
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
            
            enb_ports[uid] = {"signaling":port} # adding the signaling port in order to be used by UEs


            # creating data server
            port = port + 1
            self.ports["enb"+str(uid)+"-data"] = port
            enb_data_servers.append(threading.Thread(target=enb.run_server, args=(self.ports["enb"+str(uid)+"-data"],False)))
            enb_data_servers[i].start()

            enb_ports[uid]["data"] = port

            
            uid = uid + 1

        logging.debug("Topology is successfully configured")

        # creating the users 
        for i in range(len(self.users_info)):
            user_info = self.users_info[i]
            user = UE(user_info, enb_ports)
            uid = int(user_info["uid"])
            self.ue_dict[uid] = user
            user_enb_signalings.append(threading.Thread(target=user.connect_enb_signalings, args=()))
            user_enb_signalings[i].start()
        
        self.enb_sgw_connections = enb_sgw_connections
        self.enb_mme_connections = enb_mme_connections
        self.enb_signaling_servers = enb_signaling_servers
        self.enb_data_servers = enb_data_servers  
        self.user_enb_signalings = user_enb_signalings 
        
    def start_simulation(self, scenarios):
        '''Starting the simulation and initializing the timing on each entity'''
        self.start_time = time.time()
        
        self.mme.start_simulation(self.start_time)
        self.sgw.start_simulation(self.start_time)

        for enb in self.enb_dict.values():
            enb.start_simulation(self.start_time)
        
        for ue_entity in self.ue_dict.values():
            ue_entity.start_simulation(self.start_time)

        # running the senarios
        scenarios_queue = list(map(lambda x: {"source": int(x["source"]), "dst": int(x["dst"]), "when": float(x["when"][:-1]),
                                            "content": x["content"], "numberOfChunks": x["numberOfChunks"]}, scenarios))
        scenarios_queue.sort(key=lambda x: x["when"])
        
        while True:
            if (len(scenarios_queue) ==  0 ):
                break
            scenario = scenarios_queue[0]
            scenario_time = scenario["when"]
            if (time.time() >= scenario_time + self.start_time):
                source = scenario["source"]
                dst = scenario["dst"]
                when = scenario["when"]
                content = scenario["content"]
                chunk_num = scenario["numberOfChunks"]
                source_user = self.ue_dict[source]
                send_data_thread = threading.Thread(target=source_user.send_data, args=(dst, when, content, chunk_num))
                send_data_thread.start()
                scenarios_queue.pop(0)
            
                



        logging.debug("Simulation is started")
with open("user_info.json") as file:
    users_info_file = json.load(file)
users_info = []
for user in users_info_file["users"]:
    users_info.append(users_info_file[user])

with open("scenarios.json") as file:
    scenarios_file = json.load(file)
scenarios = []
for scenario in scenarios_file["scenarios"]:
    scenarios.append(scenarios_file[scenario])
scenarios[0]["content"] = """              _   
  __ _  _ __ | |_ 
 / _` || '__|| __|
| (_| || |   | |_ 
 \__,_||_|    \__|
                                
 .----------------.  .----------------.  .----------------.
| .--------------. || .--------------. || .--------------. |
| |      __      | || |  _______     | || |  _________   | |
| |     /  \     | || | |_   __ \    | || | |  _   _  |  | |
| |    / /\ \    | || |   | |__) |   | || | |_/ | | \_|  | |
| |   / ____ \   | || |   |  __ /    | || |     | |      | |
| | _/ /    \ \_ | || |  _| |  \ \_  | || |    _| |_     | |
| ||____|  |____|| || | |____| |___| | || |   |_____|    | |
| |              | || |              | || |              | |
| '--------------' || '--------------' || '--------------' |
 '----------------'  '----------------'  '----------------'
 _                            
| |    ___  _ _  ___  _ __    
| |__ / _ \| '_|/ -_)| '  \   
|____|\___/|_|  \___||_|_|_|  
                              
(_) _ __  ___ _  _  _ __   
| || '_ \(_-<| || || '  \  
|_|| .__//__/ \_,_||_|_|_| 
   |_|                     
    _       _           
 __| | ___ | | ___  _ _ 
/ _` |/ _ \| |/ _ \| '_|
\__,_|\___/|_|\___/|_|  

"""

# scenarios = [{ "source": "123456",
#         "dst": "123457",
#         "when": "4.3s",
#         "content": "this is a message to user 123457: what is this no no no this message should be delivered without error because your system should be perfect",
#         "numberOfChunks": 11}, 
#              { "source": "123457",
#         "dst": "123456",
#         "when": "3.9s",
#         "content": "hi how are you user 123456, im fine thank you what about you oh im doing very well man ha ha ha ha ha",
#         "numberOfChunks": 8},
#              { "source": "123456",
#         "dst": "123458",
#         "when": "10s",
#         "content": "this message is a little bit shorter but it works as well hah",
#         "numberOfChunks": 5}]

# users_info = [{"uid":12252, "interval":"15s", "locations":[(3,0), (3,3), (2.5,0), (0,2.5)]}, 
#               {"uid":76295, "interval":"15s", "locations":[(0,1), (1,0), (2.5,2.5), (8,5)]},
#               {"uid":7295, "interval":"15s", "locations":[(0,0), (5,0), (2,3), (-1,4)]}]

# user1_content = "Hello user 76295, my user id is 12252. Do you want to be my friend?"
# user2_content = "Hello user 7295, my user id is 76295. I hate you."
# scenarios = [{"source": "12252", "dst": "76295", "when": "8s", "content": user1_content, "numberOfChunks":5}, 
#              {"source": "76295", "dst": "7295", "when": "12s", "content": user2_content, "numberOfChunks":3}, 
#              {"source": "7295", "dst": "12252", "when": "17s", "content": user2_content, "numberOfChunks":3}]
# users_info = [{"uid":12252, "interval":"5s", "locations":[(1,5)]}, 
#               {"uid":76295, "interval":"5s", "locations":[(1,8)]},
#               {"uid":12252, "interval":"5s", "locations":[(9,6)]}]
lte_simulator = LTESimulator([(0,10),(15,0),(10,-15),(-10,-15), (-15, 0)], users_info, logging_level=logging.WARNING)
lte_simulator.topology_configuration()
time.sleep(3)
logging.info("------------------Starting the simulation----------------")
lte_simulator.start_simulation(scenarios)
