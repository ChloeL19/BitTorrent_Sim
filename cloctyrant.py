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
        self.gamma = 0.1 
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

        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set) 
            n = min(self.max_requests, len(isect)) 
            il = list(isect)# create isect list
            random.shuffle(il)# randomly shuffle isect list
            sorted(il, key=lambda x: av_dict[x])# sort isect list based on av_dict

            for piece_id in random.sample(il, n): 
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

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            # filler value for peers for whom we have no historical data: 1, assume perfect collab
            # divide the upload and download rates to get the ratios
            requester_ratios = {} # keys: requester ids, values: requester ratios
            random.shuffle(requests) # break symmetries again with random shuffling, for extra safety
            for r in requests:
                # if not in peer_ratios already, initialize their values in peer_ratios
                if r.requester_id not in self.peer_ratios.keys(): 
                    blocks_uploaded_lst = [] # amount of blocks uploaded to this requester in past
                    for rnd in history.uploads:
                        if rnd != []:
                            blocks_uploaded_lst += [u.bw for u in rnd if u.to_id == r.requester_id]
                    # initialize values of u and d
                    self.peer_ratios[r.requester_id] = {"u": 1, "d": 1} # previously 1
                    if len(blocks_uploaded_lst) != 0:
                        self.peer_ratios[r.requester_id]["u"] = (len(blocks_uploaded_lst)/round)/4
                        self.peer_ratios[r.requester_id]["d"] = (len(blocks_uploaded_lst)/round)/4

                requester_ratios[r.requester_id] = self.peer_ratios[r.requester_id]\
                        ["d"]/self.peer_ratios[r.requester_id]["u"]  

            # sort this dictionary in descending order, get list of tuples (requester_id, ratio)
            requester_ratios_sorted = sorted(requester_ratios.items(), key=lambda x: x[1], \
                reverse=True)
            # Now we allocate according to this order 
            # we allocate the denomiator of each ratio
            # until we hit the max cap, or until we hit the end of all requesters
            chosen = []
            bws = []
            sum_up = 0
            counter = 0
            # FIXME: STILL EXCEEDING BANDWIDTH HERE!!!
            
            while sum_up < self.up_bw and \
                counter < len(requester_ratios_sorted):
                pid = requester_ratios_sorted[counter][0]
                peer_bw = self.peer_ratios[pid]["u"]
                if peer_bw > 0:
                    chosen.append(pid)
                    bws.append(peer_bw)
                sum_up += peer_bw
                counter += 1

            # assumption: if there is any bandwidth remainder, give it all to the top ranked peer
            if sum_up < self.up_bw:
                bws[0] += math.floor(self.up_bw - sum_up)

            # assumptiopn: clean up: it's possible with this loop structure to over-allocate bandwidth
            # remove extra bandwidth by deleting the agents with least amount
            # this will also overshoot slightly in some cases . . . add back bandwidth to top
            # agent again so we use exactly all of it
            if sum_up > self.up_bw:
                lost_bw = bws.pop()
                while lost_bw < (sum_up - self.up_bw) and bws != []:
                    lost_bw = bws.pop()

            # update the estimates of upload and download rates
            for (pid, _rate_dict) in self.peer_ratios.items():
                # boolean indicator for whether peer unchoked me in last round
                unchoked_met1_bool = (pid in [d.from_id for d in history.downloads[round-1]])
                # now create a bool to indicate whether this peer unchoked me in the last r periods
                unchoked_metr_bool = True
                for r in range(round, max(0, round-self.r)): 
                    if pid not in [d.from_id for d in history.downloads[r]]:
                        unchoked_metr_bool = False
                
                # update as described in textbook
                if not unchoked_met1_bool:
                    self.peer_ratios[pid]["u"] *= (1 + self.alpha)
                if unchoked_met1_bool:
                    # update based on the amount of observed download rates
                    downloads_from_peer = [d for d in history.downloads[round-1] if d.from_id == pid]
                    total_blocks = len(set([d.blocks for d in downloads_from_peer])) 
                    self.peer_ratios[pid]["d"] = total_blocks/(round - 1)
                if unchoked_metr_bool:
                    self.peer_ratios[pid]["u"] *= (1 - self.gamma)
        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
