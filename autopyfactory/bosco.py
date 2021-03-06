#!/bin/env python
#
# module to wrap bosco_cluster and related functionality
# .bosco/clusterlist
# .bosco/.pass
# entry=griddev03.racf.bnl.gov max_queued=-1 cluster_type=slurm
#

import logging
import os
import subprocess
import shutil
import threading
import time

# Added to support running module as script from arbitrary location. 
from os.path import dirname, realpath, sep, pardir
fullpathlist = realpath(__file__).split(sep)
prepath = sep.join(fullpathlist[:-2])
import sys
sys.path.insert(0, prepath)

# module level threadlock
boscolock = threading.Lock()
boscoaddlock = threading.Lock()

class BoscoCluster(object):


    def __init__(self, entry, cluster_type='pbs', port=22, max_queued=-1,  ):
        self.log = logging.getLogger('autopyfactory')
        self.entry = entry
        (self.user, self.host) = entry.split('@')
        self.port = port
        self.max_queued = max_queued
        self.cluster_type = cluster_type
        self.log.debug("Init complete. ")

    def getentry(self):
        s += "entry=%s max_queueud=%d cluster_type=%s " % (self.entry, self.max_queued, self.cluster_type) 
        return s
    
    def __str__(self):
        return self.getentry()
    

class _boscocli(object):
    """
    Encapsulates all bosco_cluster command functionality. 
    
    """

    def __init__(self):
        self.log = logging.getLogger('autopyfactory')
        self.log.debug("Initializing bosco module...")
        self.boscopubkeyfile = os.path.expanduser("~/.ssh/bosco_key.rsa.pub")
        self.boscoprivkeyfile = os.path.expanduser("~/.ssh/bosco_key.rsa")
        self.boscopassfile = os.path.expanduser("~/.bosco/.pass")
        self.boscokeydir = os.path.expanduser("~/.ssh")
        self.boscodir = os.path.expanduser('~/.bosco')
        if os.path.exists(self.boscokeydir) and os.path.isdir(self.boscokeydir):
            self.log.debug("boscokeydir exists.")
        else:
            self.log.debug("Making boscokeydir.")
            os.makedirs(self.boscokeydir)
        if os.path.exists(self.boscodir) and os.path.isdir(self.boscodir):
            self.log.debug('bosco dir exists')
        else:
            self.log.debug("Making boscodir.")
            os.makedirs(self.boscodir)

    def _checkbosco(self):
        """
        Confirm BOSCO is installed. 
        """
        self.log.debug("Checking to see if local bosco_cluster is on path...")
        isinstalled = False
        exetouse = None
        for path in os.environ['PATH'].split(os.pathsep):
            path = path.strip('"')
            exefile = os.path.join(path,'bosco_cluster')
            if os.path.isfile(exefile) and os.access(exefile, os.X_OK):
                isinstalled = True
                exetouse = exefile
        if not isinstalled:
            self.log.error('Missing dep. bosco_cluster not on PATH: %s' % os.environ['PATH'])
            #raise MissingDependencyFailure('Missing dep. bosco_cluster not on PATH: %s' % os.environ['PATH'] )
        else:
            self.log.debug("Using bosco_cluster: %s" % exetouse )
        return isinstalled
   
   
    def _getBoscoClusters(self):
        """
        [jhover@grid05 ~]$ bosco_cluster -l
        griddev03.racf.bnl.gov/slurm
            
        """
        cmd = 'bosco_cluster -l '
        self.log.debug("cmd is %s" % cmd) 
        before = time.time()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        out = None
        (out, err) = p.communicate()
        delta = time.time() - before
        self.log.debug('It took %s seconds to issue the command' %delta)
        self.log.debug('%s seconds to issue command' %delta)
        if p.returncode == 0 or p.returncode == 2:
            self.log.debug('Leaving with OK return code.')
        else:
            self.log.warning('Leaving with bad return code. rc=%s err=%s' %(p.returncode, err )) 
        self.clusters = []
        lines = out.split("\n")
        self.log.debug("got %d lines" % len(lines))
        for line in lines:
            self.log.debug("line is %s" % line)
            if line.strip() == 'No clusters configured':
                self.log.debug("No clusters configured.")
            elif len(line) < 2:
                self.log.debug('empty line discarded')
            else:
                host, batch = line.split('/')
                #  entry, cluster_type='pbs', port=22, max_queued=-1,
                self.log.debug('got entry from bosco: %s %s Making object... ' % (host, batch))
                bentry = BoscoCluster(entry=host, cluster_type=batch)
                self.log.debug('made bentry object, appending.')
                self.clusters.append(bentry)
                
        return self.clusters

    def _clusteradd(self, 
                    user,  
                    host, 
                    port, 
                    batch, 
                    pubkeyfile, 
                    privkeyfile, 
                    passfile=None):
        self.log.info("Setting up cluster %s@%s/%s " % (user, host, batch))                 
        
        self.log.debug("ensuring pubkeyfile") 
        shutil.copy(pubkeyfile, self.boscopubkeyfile)
        shutil.copy(pubkeyfile, os.path.expanduser("~/.ssh/id_rsa.pub") )
        self.log.debug("ensuring privkeyfile") 
        shutil.copy(privkeyfile, self.boscoprivkeyfile)        
        shutil.copy(privkeyfile, os.path.expanduser("~/.ssh/id_rsa")) 
        if passfile:
            self.log.debug("ensuring passfile")        
            shutil.copy(passfile, self.boscopassfile )
        
        self._start_agent(pubkeyfile, privkeyfile, passfile)        
        
        self.log.debug("getting add lock")
        boscoaddlock.acquire()     
        try:
            cmd = 'bosco_cluster -a %s@%s %s ' % (user, host, batch)
            self.log.debug("cmd is %s" % cmd) 
            before = time.time()
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            out = None
            (out, err) = p.communicate()        
            self.log.debug('bosco_cluster -a output was %s' % out)
            delta = time.time() - before
            self.log.debug('It took %s seconds to issue the command' %delta)
            self.log.debug('%s seconds to issue command' %delta)
            
            # remove bosco files to ensure account separation...
            for fn in [self.boscopubkeyfile, self.boscoprivkeyfile, self.boscopassfile ]:
                try:
                    self.log.debug("removing %s" % fn) 
                    os.remove(fn)
                except OSError:
                    # file might not exist
                    pass
                except TypeError:
                    # passfile might be None
                    pass
        except Exception, e:
            self.log.exception("Exception during bosco_cluster -a installation. ")
        finally:
            self.log.debug("releasing add lock")
            boscoaddlock.release()
            
                
    def _start_agent(self, pubkeyfile, privkeyfile, passfile=None):
        self.log.debug('cmd is ssh-agent')
        cmd = 'ssh-agent '
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        out = None
        (out,err) = p.communicate()
        lines = out.split('\n')
        for line in lines:
            self.log.debug('line is %s' % line)
            exp = line.split(';')
            if '=' in line:
                (k,v) = exp[0].split('=')
                if k == 'SSH_AUTH_SOCK':
                    os.environ['SSH_AUTH_SOCK'] = v
                    self.log.debug('setting SSH_AUTH_SOCK= %s' % v )
                elif k == 'SSH_AGENT_PID':
                    os.environ['SSH_AGENT_PID'] = v
                    self.log.debug('setting SSH_AGENT_PID= %s' % v )
                else:
                    pass
        self.log.debug('SSH agent started, environment set....')
         
        #cmd = '/usr/bin/bosco_ssh_start --key %s --pass %s ' % (privkeyfile, passfile) 
        cmd = 'bosco_ssh_start --key %s --nopass ' % privkeyfile
        self.log.debug('cmd is %s' % cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        out = None
        (out,err) = p.communicate()
        self.log.debug('ssh_start completed.')

        cmd = 'ssh-add -l ' 
        self.log.debug('cmd is %s' % cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        out = None
        (out,err) = p.communicate()
        self.log.debug('ssh-add -l : %s' % out)        


    def _clusteraddnative(self,host,batch):
        self.log.info("Setting up cluster %s/%s " % (host,batch))

             
    
    def _checktarget(self, user, host, port, batch, pubkeyfile, privkeyfile, passfile=None ):
        """
        Ensure bosco_cluster has been run.         
        """
        #Ensure paths
        pubkeyfile = os.path.expanduser(pubkeyfile)
        privkeyfile = os.path.expanduser(privkeyfile)
        try:
            passfile = os.path.expanduser(passfile)
        except AttributeError:
            pass
        
        self.log.debug("Checking to see if remote bosco is installed and up to date...")
        host = host.lower()
        batch = batch.lower()
        try:
            self.log.debug("getting lock")
            boscolock.acquire()
            clist = self._getBoscoClusters()
            self.log.debug("got list of %d clusters" % len(clist))
            found = False
            for c in clist:
                if c.user == user and c.host == host and c.cluster_type == batch:
                    found = True
            if not found:
                self.log.info("Setting up cluster %s/%s " % (host,batch))
                self._clusteradd(user, host, port, batch, pubkeyfile, privkeyfile, passfile)
            else:
                self.log.debug("Cluster %s@%s/%s already set up." % (user,host,batch))    
            
        except Exception, e:
            self.log.exception("Exception during bosco remote installation. ")
    
        finally:
            self.log.debug("releasing lock")
            boscolock.release()
            


# Singleton implementation
class BoscoCLI(object):

    instance = None

    def __new__(cls, *k, **kw):
        if not BoscoCLI.instance:
            BoscoCLI.instance = _boscocli(*k, **kw)
        return BoscoCLI.instance

           
# ============================================================================= 
            
if __name__ == '__main__':
    # Set up logging. 
    debug = 0
    info = 0
    
    # Check python version 
    major, minor, release, st, num = sys.version_info
    
    # Set up logging, handle differences between Python versions... 
    # In Python 2.3, logging.basicConfig takes no args
    #
    FORMAT23="[ %(levelname)s ] %(asctime)s %(filename)s (Line %(lineno)d): %(message)s"
    FORMAT24=FORMAT23
    FORMAT25="[%(levelname)s] %(asctime)s %(module)s.%(funcName)s(): %(message)s"
    FORMAT26=FORMAT25
    
    if major == 2:
        if minor ==3:
            formatstr = FORMAT23
        elif minor == 4:
            formatstr = FORMAT24
        elif minor == 5:
            formatstr = FORMAT25
        elif minor == 6:
            formatstr = FORMAT26
        elif minor == 7:
            formatstr = FORMAT26
    
    log = logging.getLogger('autopyfactory')
    hdlr = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(FORMAT23)
    hdlr.setFormatter(formatter)
    log.addHandler(hdlr)
    
    if debug: 
        log.setLevel(logging.DEBUG) # Override with command line switches
    if info:
        log.setLevel(logging.INFO) # Override with command line switches
    log.debug("Logging initialized.")      
    
    bcli = BoscoCLI()
    bcli._checktarget('gridev03.racf.bnl.gov', 'slurm', '~/etc/apf/jhover/pass')
    
    
