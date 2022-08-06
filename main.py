from entities import eNodeB
import logging

class LTESimulator():
    def __init__(self, eNodeBsLocation, users):
        self.eNodeBsLocation = eNodeBsLocation
        self.users = users
        return
    
    def topology_configuration(self):
        # creating the MME
        mme = MME()

        eNodeBs = []
        uid = 5000 # just a random initial uid
        for i in range(len(self.eNodeBsLocation)):
            eNodeBLocation = self.eNodeBsLocation[i]
            enb = eNodeB(eNodeBLocation, uid)
            uid = uid + 1
