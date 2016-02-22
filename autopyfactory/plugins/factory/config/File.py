#!/usr/bin/env python

import logging

from autopyfactory.apfexceptions import ConfigFailure
from autopyfactory.configloader import Config, ConfigManager
from autopyfactory.interfaces import ConfigInterface


class File(ConfigInterface):

    def __init__(self, factory):

        self.log = logging.getLogger("main.configplugin")
        self.factory = factory
        self.fcl = factory.fcl
        self.log.info('ConfigPlugin: Object initialized.')

    def getConfig(self):

        qcl = None

        # 1. we try to read the list of files in queueConf and create a config loader
        qcf = None
        try:
            qcf = self.fcl.get('Factory', 'queueConf')    # the configuration files for queues are a list of URIs
            self.log.debug("queues.conf file(s) = %s" % qcf)
            qcl_files = ConfigManager().getConfig(sources=qcf)
        except:
            pass
        
        # 2. we try to read the directory in queueDirConf and create a config loader
        qcd = None
        try:
            qcd = self.fcl.get('Factory', 'queueDirConf') # the configuration files for queues are in a directory
            if qcd == "None" or qcd == "":
                qcd = None
            if qcd:
                self.log.debug("queues.conf directory = %s" % qcd)
                qcl_dir = ConfigManager().getConfig(configdir=qcd)
        except:
            pass
        
        # 3. we merge both loader objects
        try:
            if qcf and qcd:
                qcl = qcl_files
                self.qcl.merge(qcl_dir)
            elif qcf and not qcd:
                qcl = qcl_files
            elif not qcf and qcd:
                qcl = qcl_dir
            else:
                self.log.error('no files or directory with queues configuration specified')
                raise ConfigFailure('no files or directory with queues configuration specified')
        except Exception, err:
            self.log.error('Failed to create queues ConfigLoader object')
            raise ConfigFailure('Failed to create queues ConfigLoader: %s' %err)

        self.log.info('queues ConfigLoader object created')
        return qcl
