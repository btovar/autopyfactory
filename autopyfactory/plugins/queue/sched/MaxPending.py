#! /usr/bin/env python
#

from autopyfactory.interfaces import SchedInterface
import logging


class MaxPending(SchedInterface):
    id = 'maxpending'
    
    def __init__(self, apfqueue, config, section):

        try:
            self.apfqueue = apfqueue                
            self.log = logging.getLogger('autopyfactory.sched.%s' %apfqueue.apfqname)

            self.max_pilots_pending = self.apfqueue.qcl.generic_get(self.apfqueue.apfqname, 'sched.maxpending.maximum', 'getint')
            self.allow_negative = self.apfqueue.qcl.generic_get(self.apfqueue.apfqname, 'sched.maxpending.allow_negative', 'getboolean', True)
            self.log.debug("SchedPlugin: Object initialized.")
        except Exception, ex:
            self.log.error("SchedPlugin: object initialization failed. Raising exception")
            raise ex

    def calcSubmitNum(self, n=0):
        self.log.debug('Starting with n=%s' %n)
        queueinfo = self.apfqueue.batchstatus_plugin.getInfo(queue = self.apfqueue.apfqname)
        out = n
        msg = None
    
        if not queueinfo:
            out = n
            msg = "MaxPending:comment=No queueinfo."
        else:
            pending_pilots = queueinfo.pending
            self.log.debug('Pending is %s' % pending_pilots)
            if pending_pilots == 0:
                # if no pending, there may be free slots, so we impose no limit
                out = n
                self.log.debug('No pending, submit full input %s' % n)
            else:
                if self.max_pilots_pending is not None:
                    tosubmit = self.max_pilots_pending - pending_pilots                   
                    if not self.allow_negative and tosubmit < 0:
                        self.log.debug('Negative output not allowed, and tosubmit less than 0, so 0.')
                        tosubmit = 0
                    out = min(n, tosubmit )
                         
            msg = "MaxPending:in=%s,pending=%s,maxpending=%s,ret=%s" %(n, 
                                                             pending_pilots, 
                                                             self.max_pilots_pending, 
                                                             out)
        self.log.info(msg)
        return (out, msg)
