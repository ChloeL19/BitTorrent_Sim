#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging
import math
from messages import Upload, Request
from util import even_split
from peer import Peer

class ClocPropShare(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
    
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
        
        #create an array - loop through keys from dict- whoever has most rare piece first in array. 
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
        print("hi", requests)
        return requests


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

            #request = random.choice(requests)
            chosen = []
            bws= []
            # Evenly "split" my upload bandwidth among the one chosen requester
            #bws = even_split(self.up_bw, len(chosen))

            requester_l = [r.requester_id for r in requests]
            last_round = history.downloads[round-1]
            non_share = []

            #if round is 0 or no intersection between last round downloaders and requesters
            if round == 0 or list(set(requester_l) & set([ob.from_id for ob in last_round])) == []: 
                chosen = random.sample([r.requester_id for r in requests], min(len(requests), 4)) #is it peers or r.requester_id for r in requests --> gets error:chosen = [request.requester_id]
                bws = even_split(self.up_bw, len(chosen)) 
            else: 
                for obj in last_round: 
                    #if downloader is in requester list
                    if obj.from_id in requester_l: 
                        allocate_bw = ((obj.blocks/sum([o.blocks for o in last_round]))*0.9)
                        chosen.append(obj.from_id)
                        bws.append(math.floor(self.up_bw * allocate_bw))
                    else: 
                        #add downloader to a non-shared list for optimistic unchoking
                        non_share.append(obj.from_id)
                if non_share != []: 
                    #optimistic unchoking
                    chosen.append(random.choice(non_share))
                    bws.append(math.floor(0.1*self.up_bw))

        #check if there is extra bandwidth to allocate
        if sum(bws)<self.up_bw and sum(bws) != 0: 
            val = math.floor((self.up_bw - sum(bws))/len(bws))
            bws = [x + val for x in bws]

        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
        return uploads