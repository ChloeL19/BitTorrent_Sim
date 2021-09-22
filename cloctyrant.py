#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import math
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class ClocTyrant(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        self.d  = {}#big dictionary of keys with their respective rates --> how to initialize it by 10
        self.u = {}
        self.gamma = 0.1 #change in utils #CHECK DATA TYPES 
        self.alpha = 0.2
        self.r = 3 
        self.S = 4
        self.peer_ratios = {} # keys: peer ids, values: {"u": upload rate, "d": download rate}
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = list(filter(needed, list(range(len(self.pieces)))))
        np_set = set(needed_pieces)  # sets support fast intersection ops.


        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)
        
        av_dict = {} # count of other peers with this piece
        
        for np in np_set: 
            peers_with_piece = 0
            for p in peers:
                if np in p.available_pieces:
                    peers_with_piece += 1
            av_dict[np] = peers_with_piece


        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful
        peers.sort(key=lambda p: p.id)
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set) #intersection between available pieces and needed pieces 
            n = min(self.max_requests, len(isect)) #need this but what do you do with isect 
            il = list(isect)# create isect list
            random.shuffle(il)# randomly shuffle isect list
            sorted(il, key=lambda x: av_dict[x])# sort isect list based on av_dict

            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time. ADD HERE
            for piece_id in random.sample(il, n): #DO YOU MEAN CHANGING THIS???
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)

        return requests

#dynamically adjust upload slots, unchoke based on unload and download speed, not equal-split policy, upload at min rate- upload rate increases if they don't reciprocate  
#unchoking everyone for which our upload capacity value is less than total capacity
#how many people i unchoke is how much given 
    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"

            # helper function for initialization
            # def initialize_ud():
            #     '''
            #     Initialize the peer_ratios dictionary to all 1s.
            #     '''
            #     for p in peers:
            #         self.peer_ratios[p.id]["u"] = 1
            #         self.peer_ratios[p.id]["d"] = 1

            # filler value for peers for whom we have no historical data: 1, assume perfect collab
            # divide the upload and download rates to get the ratios
            requester_ratios = {} # keys: requester ids, values: requester ratios
            random.shuffle(requests) # CONFIRM: break symmetries again with random shuffling?
            for r in requests:
                # if not in peer_ratios already, initialize their values in peer_ratios
                if r.requester_id not in self.peer_ratios.keys():
                    # initialize the peer_ratios upload/download metrics to the available history of requester
                    # use their full history to maximize amount of information used
                    # QUESTION: how do I get the number of rounds played by a peer???????
                    # sadly may not have ability to make this work: num_rounds_played = history.peer_history(peer_id=r.requester_id).current_round
                    
                    # look at just self.up_bw
                    
                    num_rounds_played = round
                    num_pieces_downloaded = len(set(list(filter(lambda p: p.id == r.requester_id, peers))[0].available_pieces))
                    # if this peer has no history, initialize to a constant
                    self.peer_ratios[r.requester_id] = {"u": 1, "d": 1}
                    # otherwise use history to initialize
                    if num_rounds_played != 0 and num_pieces_downloaded != 0:
                        self.peer_ratios[r.requester_id]["u"] = (num_pieces_downloaded/num_rounds_played)/4
                        self.peer_ratios[r.requester_id]["d"] = (num_pieces_downloaded/num_rounds_played)/4

                requester_ratios[r.requester_id] = self.peer_ratios[r.requester_id]\
                        ["d"]/self.peer_ratios[r.requester_id]["u"]  

            # sort this dictionary in descending order, get list of tuples (requester_id, ratio)
            requester_ratios_sorted = sorted(requester_ratios.items(), key=lambda x: x[1], \
                reverse=True)
            # Now we allocate according to this order to denomiator value worth of bandwidth
            # until we hit the max cap, or until we hit the end of all requesters
            chosen = []
            bws = []
            sum_up = 0
            counter = 0
            while sum_up < self.up_bw and \
                counter < len(requester_ratios_sorted):
                try:
                    pid = requester_ratios_sorted[counter][0]
                except:
                    import pdb; pdb.set_trace();
                peer_bw = self.peer_ratios[pid]["u"]
                if peer_bw > 0:
                    chosen.append(pid)
                    bws.append(peer_bw)
                sum_up += peer_bw
                counter += 1

            # assumption: if there is any bandwidth remainder, give it all to the top ranked peer
            if sum_up < self.up_bw:
                try:
                    bws[0] += math.floor(self.up_bw - sum_up)
                except:
                    import pdb; pdb.set_trace();
            # clean up: it's possible with this loop structure to over-allocate bandwidth
            # remove extra bandwidth 
            if sum_up > self.up_bw:
                try:
                    lost_bw = bws.pop()
                except:
                    import pdb; pdb.set_trace();
                while lost_bw < (sum_up - self.up_bw) and bws != []:
                    lost_bw = bws.pop()
                #import pdb; pdb.set_trace();

            if sum(bws) > self.up_bw:
                import pdb; pdb.set_trace();

            # update the estimates of upload and download rates
            for (pid, _rate_dict) in self.peer_ratios.items():
                unchoked_met1_bool = (pid in [d.from_id for d in history.downloads[round-1]])
                # now create a bool to indicate whether this peer is in the last r periods
                unchoked_metr_bool = True
                for r in range(round, max(0, round-self.r)): 
                    if pid not in [d.from_id for d in history.downloads[r]]:
                        unchoked_metr_bool = False
                if not unchoked_met1_bool:
                    self.peer_ratios[pid]["u"] *= (1 + self.alpha)
                if unchoked_met1_bool:
                    # SKETCHY AS FRICK
                    # update based on the amount of observed download rates
                    downloads_from_peer = [d for d in history.downloads[round-1] if d.from_id == pid]
                    total_pieces = len(set([d.piece for d in downloads_from_peer])) #imperfect estimate of number of pieces downloaded, inflated
                    self.peer_ratios[pid]["d"] += ((self.peer_ratios[pid]["d"]) -
                    (round/(round-1)**2) + (total_pieces/(round-1)))/(round/(round-1)) 
                    # I worked out this math . . . image of logic attached in the write-up
                    # denominator of previous rate value will always be current_round-1
                    # I want to add the rate in pieces/round to the old rate
                if unchoked_metr_bool:
                    self.peer_ratios[pid]["u"] *= (1 - self.gamma)

        #     ## NEW CODE STARTS HERE
        # + #list of what round it is and how much given in total- average - this should be dynamic upload rate 
        #     #based on average download rate of standard clients 
        #     capij = self.up_bw #is this max??

        #     if round == 0: 
        #         for peer in peers: 
        #             self.u = self.up_bw/self.S #4
        #             self.d = self.up_bw/self.S

        #     div_dict = {k: float(self.d[k])/self.u[k] for k in self.d}
        #     sorted_peers = {k: v for k, v in sorted(div_dict.items(), key=lambda x: x[1])}
        #     sum_up = 0 
        #     kpeer = []

        #     while sum_up <= capij:
        #         sum_up += 

        #     for peer in sorted_peers.keys(): 
        #         if sum_up > capij:
        
        #             break 
        #         sum_up += sorted_peers[peer]
        #         kpeer.append(peer)
        #     #need to unchoke peers 1 to k for which 

        #     for pr in peers: 
        #         downhist = history.download[round - 1]
        #         if pr in downhist.keys(): 
        #             SOMETHING 
        #         elif round => self.r: #greater than r: 
        #             self.u = (1 + self.alpha)self.u
        #         #upload_hist = self.uploads[round - 1]
        #         #upload_hist.keys()
        #         else:#the number of times been unchoked less than 3- download rate is rate from last round i think: 
        #             self.d = download

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
