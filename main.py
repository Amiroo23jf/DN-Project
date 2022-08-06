from eNodeB import eNodeB
class LTESimulator():
    def __init__(self, eNodeBsLocation, users):
        self.eNodeBsLocation = eNodeBsLocation
        self.users = users
        return
    
    def topology_configuration(self):
        eNodeBs = []
        for i in range(len(self.eNodeBsLocation)):
            