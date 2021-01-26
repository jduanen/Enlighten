#!/usr/bin/env python3
"""
Tool for monitoring solar array using Blink(1) USB device

Works with the Enphase Enlighten Systems API

This needs three values to access the Enphase API -- an API key, a user ID,
 and (for some, but not all commands) a system ID.
These values can be obtained from a configuration (YAML) file, and the values
 contained within this file can be overriden with command-line options.
If any of these values is not found in the configuration file, or given on the
 command line, then and attempt will be made to obtain it from one of these
 environment variables: ENPHASE_API_KEY, ENPHASE_UID, and ENPHASE_SYSID.

If sysId not given, the ID of the first system found will be used.

The "Watt" plan allows 10 hits/min and 10,000 hits/month for free.

N.B. Blink1() uses css3 color names
"""


import argparse
import json
import logging
import os
import sys
import time

import yaml

from blink1.blink1 import Blink1
from enphase import Enlighten


DEF_CONF_FILE = "./.enphase.yml"
DEF_LOG_LEVEL = "WARNING"
DEF_RATE = 4    # default: poll every 15 mins

UPDATE_RATE = 6 * 60 * 60  # Envoy updates server every six hours on Cellular
UPDATE_RATE = 15 * 60      # Envoy updates server every 15 mins on WiFi
STATS_RATE = 5 * 60        # stats are sampled in 5 min intervals

#### TODO document this

#### TODO add signal handler and shut down gracefully

def run(options):
    try:
        blink = Blink1()
    except:
        logging.error("Failed to connect to blink(1) device")
        sys.exit(1)
    nliten = Enlighten(options['uid'], options['apiKey'], options['sysId'])
    if options['verbose']:
        json.dump(nliten.allSystems, sys.stdout, indent=4)

    summary = nliten.summary()
    numModules = summary['modules']
    maxPower = summary['size_w']
    lastReport = summary['last_report_at']
    lastInterval = summary['last_interval_end_at']
    logging.info(f"Summary: numModules={numModules}, maxPower={maxPower}, lastReport={lastReport}, lastInterval={lastInterval}")
    #### TODO test for late reports, turn on error light and loop until good

    pollInterval = (60 * 60) / options['rate']
    pollInterval = 3    #### TMP TMP TMP
    run = True
    run = 4    #### TMP TMP TMP
    logging.info(f"Start polling: polling interval={pollInterval} secs")
    blink.fade_to_color(300, 'chartreuse')
    while run:
        stats = nliten.stats()
        now = time.time()
        logging.debug(f"Stats: {stats['meta']}")
        blink.fade_to_color(300, 'yellow')
        if stats['meta']['last_report_at'] < now - UPDATE_RATE:
            logging.info(f"Reporting Late: last report={stats['meta']['last_report_at']}, now={now}")
            blink.fade_to_color(100, 'orange', ledn=2)
        if stats['meta']['status'] != "normal":
            logging.info("")
            blink.fade_to_color(300, 'red', ledn=1)
        else:
            blink.fade_to_color(300, 'green', ledn=2)
        time.sleep(pollInterval)
        run += -1  #### TMP TMP TMP
    logging.info("Shutting down")
    blink.off()
    blink.close()


def getOps():
    usage = f"Usage: {sys.argv[0]} [-v] " + \
             "[-c <confFile>] [-L <logLevel>] [-l <logFile>] " + \
             "[-i] [-r <rate>]" + \
             "[-a <apiKey>] [-u <uid>] [-s <sysId>]"
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-a", "--apiKey", action="store", type=str,
        help="Enphase Enlighten Systems API key")
    ap.add_argument(
        "-c", "--confFile", action="store", type=str,
        default=DEF_CONF_FILE, help="Path to YAML file with configuration information")
    ap.add_argument(
        "-i", "--isoFormat", action="store_true", default=False,
        help="Print datetime values in iso8601 format")
    ap.add_argument(
        "-L", "--logLevel", action="store", type=str, default=DEF_LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level")
    ap.add_argument(
        "-l", "--logFile", action="store", type=str,
        help="Path to location of logfile (create it if it doesn't exist)")
    ap.add_argument(
        "-r", "--rate", action="store", type=int, choices=range(1, 4),
        default=DEF_RATE,
        help="Rate to poll the Enlighten server (in calls per hour)")
    ap.add_argument(
        "-s", "--sysId", action="store", type=str,
        help="Enphase Enlighten System Id")
    ap.add_argument(
        "-u", "--uid", action="store", type=str,
        help="Enphase Enlighten User Id")
    ap.add_argument(
        "-v", "--verbose", action="count", default=0, help="Print debug info")
    opts = ap.parse_args()

    if not os.path.exists(opts.confFile):
        print(f"Error: Configuration file not found: {opts.confFile}")
        sys.exit(1)
    with open(opts.confFile, "r") as f:
        confs = list(yaml.load_all(f, Loader=yaml.Loader))
        if len(confs) < 1:
            print(f"Error: Empty configuration file: {opts.confFile}")
            sys.exit(1)
        elif len(confs) > 1:
            print(f"Warning: Using the first document in configuration file: {opts.confFile}")
    conf = confs[0]

    if opts.logLevel:
        conf['logLevel'] = opts.logLevel
    elif 'logLevel' not in conf:
        conf['logLevel'] = DEF_LOG_LEVEL
    logLevel = conf['logLevel']

    if opts.logFile:
        conf['logFile'] = opts.logFile
    logFile = conf.get('logFile')
    if opts.verbose:
        print(f"Logging to: {logFile}")
    if logFile:
        logging.basicConfig(filename=logFile, level=logLevel)
    else:
        logging.basicConfig(level=logLevel)

    if opts.apiKey:
        conf['apiKey'] = opts.apiKey
    elif 'apiKey' not in conf:
        apiKey = os.environ.get("ENPHASE_API_KEY")
        if not apiKey:
            logging.error("Must provide API Key")
            sys.exit(1)
        conf['apiKey'] = apiKey

    if opts.uid:
        conf['uid'] = opts.uid
    elif 'uid' not in conf:
        uid = os.environ.get("ENPHASE_UID")
        if not uid:
            logging.error("Must provide User Id")
            sys.exit(1)
        conf['uid'] = uid

    if opts.sysId:
        conf['sysId'] = opts.sysId
    elif 'sysId' not in conf or not conf['sysId']:
        conf['sysId'] = os.environ.get("ENPHASE_SYSID")
    else:
        conf['sysId'] = None

    if 'apiKey' not in conf:
        logging.Error("Must supply API Key")
        sys.exit(1)

    if 'uid' not in conf:
        logging.Error("Must supply User Id")
        sys.exit(1)

    options = vars(opts)
    options.update(conf)
    return(options)


if __name__ == '__main__':
    opts = getOps()
    run(opts)
