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
        #random.shuffle(needed_pieces)

        # CHARLOTTE WORKING ON THIS
        # maybe use the internal state for tracking this variable
        # of the pieces we have, what is their availability among the other peers
        # how many of the most rare pieces does each peer have
        # sort peers by this
        # av_dict = {} # count of other peers with this piece
        # for np in np_set: 
        #     peers_with_piece = 0
        #     for p in peers:
        #         if np in p.available_pieces:
        #             peers_with_piece += 1
        #     av_dict[np] = peers_with_piece
        # # design a metric to rank peers by the number of rare pieces they have
        # scored_peers = {}
        # for p in peers:

        # probably need to still think about breaking symmetries . . . randomize ties
        
        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful
        peers.sort(key=lambda p: p.id)
        # change sorting to rarest first

        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            for piece_id in random.sample(isect, n):
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

        # implement optimistic unchoking here --> is it just random?
        # also implement reciprocation here: this is where we make assumptions about
        # what makes a peer worth collaborting with?

        # get upload speed estimates for all of the requesters
        requester_rates = {} # r.peer_id -> pieces/round
        for r in requests:
            # use download rates as a proxy for upload rates
            p_history = history.peer_history(r.peer_id)
            # get the corresponding peer object
            try:
                peer = list(filter(lambda p: p.id == r.peer_id, peers))[0] #CONFIRM: okay to assume each peer ID only appears once in list?
            except:
                raise Exception("The requestor is not in the passed list of peers.")
            # Q: should I exclude this round as part of estimation of download/upload rates
            # units of this metric should be pieces/round
            peer_uploadrate_proxy = len(set(peer.available_pieces))/p_history.current_round()
            requester_rates[r.id] = peer_uploadrate_proxy
        # sort the requesters by the value of their rates greatest --> least
        # looking here will be helpful: https://careerkarma.com/blog/python-sort-a-dictionary-by-value/ 
        requester_rates_sorted = sorted(requester_rates.items(), key=lambda x: x[1], \
            reverse=True)
        # General Q: how do we incrementally test this thing?????

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"
            # requester
            request = random.choice(requests)
            chosen = [request.requester_id]
            # Evenly "split" my upload bandwidth among the one chosen requester
            bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
