#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class ClocStd(Peer):

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

        # FIXME: consider holding randomly unchoked agents for three rounds

        # helper function
        def sort_requesters():
            '''
            Returns a sorted list of tuples [greatest --> least] of (requester ids, upload rates).
            Only computes these estimates for all available rounds of history.
            '''
            # create a dict of peers that have let us download in the full history
            friends = {} # key is peer id, value is number of blocks downloaded across all rounds
            for round in history.downloads:
                for download in round:
                    if download.from_id in friends.keys():
                        friends[download.from_id] += download.blocks
                    else:
                        friends[download.from_id] = download.blocks

            # get upload speed estimates for all of the requesters
            requester_rates = {} # r.peer_id -> blocks/round, seems more granular
            for r in requests:
                # use download rates as a proxy for upload rates
                if r.requester_id in friends:
                    peer_uploadrate_proxy = friends[r.requester_id]/len(history.downloads)
                    requester_rates[r.requester_id] = peer_uploadrate_proxy
            # sort the requesters by the value of their rates greatest --> least
            requester_rates_sorted = sorted(requester_rates.items(), key=lambda x: x[1], \
                reverse=True)
            return requester_rates_sorted
        
        # reciprocation and optimistic unchoking
        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"

            # assumption: if only four requestors, just unchoke those four and split bandwidth evenly
            if len(set([x.requester_id for x in requests])) <= 4:
                # get list of ids from this list, these are the chosen
                chosen = []
                for r in requests:
                    chosen.append(r.requester_id)
                bws = even_split(self.up_bw, len(set(chosen))) # use set to remove duplicates
            else:
                # otherwise return the sorted requesters
                sorted_requesters = sort_requesters()[:3]

                # if there are no sorted requestors, just continue to only unchoke requesters randomly
                chosen = []
                if sorted_requesters != []:
                    for (requester_id, _upload_rate) in sorted_requesters:
                        chosen.append(requester_id)
                
                # determine the remaining choked requesters
                choked_requests = list(filter(lambda x: x.requester_id not in set(chosen),\
                    requests))
                # randomly unchoke remaining choked requesters
                random_request = random.sample(choked_requests, 4-len(sorted_requesters))
                randomly_chosen = [r.requester_id for r in random_request]
                chosen = chosen + randomly_chosen
                # Evenly "split" my upload bandwidth among all chosen requestors
                bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads


## assumption: if a peer makes multiple requests, assume it doesn't matter which one is fulfilled. 