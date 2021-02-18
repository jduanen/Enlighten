#!/usr/bin/env python3
"""
Tool for monitoring solar array using Blink(1) USB device

This starts off with the device in the "initializing" display state.
This polls the Enlighten Server every POLL_INTERVAL mins and generates the
 "stale data" display if the 
The device will generate the stored blinking pattern if this code does not
 poke the device every WATCHDOG_INTERVAL msec.


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

The Blink1() device uses css3 color names.
"""

#### TODO document this


import argparse
import json
import logging
import os
import signal
import sys
from threading import Event
import time

import yaml

from blink1.blink1 import Blink1
from Enlighten import Enlighten
from Indicators import Indicators


WATCHDOG_INTERVAL = 60 * 1000  # poke watchdog every minute

DEF_CONF_FILE = "./.enphase.yml"
DEF_LOG_LEVEL = "WARNING"
DEF_INTERVAL = 6    # default: poll every 6 hours

#### TODO move this to the library

FACTORY_BLINK_PATTERN = [(255, 0, 0, 500), (255, 0, 0, 500), (0, 0, 0, 500),
                         (0, 255, 0, 500), (0, 255, 0, 500), (0, 0, 0, 500),
                         (0, 0, 255, 500), (0, 0, 255, 500), (0, 0, 0, 500),
                         (128, 128, 128, 1000), (0, 0, 0, 1000),
                         (255, 255, 255, 500), (0, 0, 0, 500),
                         (255, 255, 255, 500), (0, 0, 0, 1000), (0, 0, 0, 1000)]
DEF_WATCHDOG_PATTERN = FACTORY_BLINK_PATTERN  #### FIXME make a better default watchdog pattern

CELLULAR_INTERVAL = 6 * 60 * 60  # Envoy updates server every six hours on Cellular
WIFI_INTERVAL = 15 * 60          # Envoy updates server every 15 mins on WiFi
UPDATE_INTERVAL = CELLULAR_INTERVAL  # using Cellular
STATS_RATE = 5 * 60              # stats are sampled in 5 min intervals

RETRY_DELAY = 60 * 5             # retry every 5 mins

#CATCH_SIGNALS = ("INT", "HUP", "ILL", "TRAP", "ABRT", "KILL")
CATCH_SIGNALS = ("INT",)


exitLoop = Event()


def signalHandler(sig, frame):
    ''' Catch SIGINT and clean up before exiting
    '''
    if sig == signal.SIGINT:
        logging.info("SIGINT")
    else:
        logging.debug("Signal:", sig)
    exitLoop.set()


def run(options):
    for s in CATCH_SIGNALS:
        signal.signal(getattr(signal, f"SIG{s}"), signalHandler)

    leds = Indicators(WATCHDOG_INTERVAL)
    nliten = Enlighten(options['uid'], options['apiKey'], options['sysId'])
    if options['verbose']:
        json.dump(nliten.allSystems, sys.stdout, indent=4)

    pollInterval = (60 * 60) * options['rate']  # number of seconds between polls
    pollInterval = 3    #### TMP TMP TMP
    logging.info(f"Start polling: polling interval={pollInterval} secs")
    while not exitLoop.is_set():
        current = False
        normal = False
        while not (current and normal) and not exitLoop.is_set():
            summary = nliten.summary()
            logging.info(f"Summary: power={summary['current_power']}, status={summary['status']}, lastReport={summary['last_report_at']}, lastInterval={summary['last_interval_end_at']}")
            current = summary['last_report_at'] < time.time() - UPDATE_INTERVAL
            normal = summary['status'] == "normal"
            if not current:
                leds.staleData()
                logging.debug("Stale Data")
                continue
            else:
                leds.currentData(normal)
                if normal:
                    logging.debug("Good Data")
                    break
                else:
                    logging.debug("Abnormal Data")
            time.sleep(RETRY_DELAY)

        stats = nliten.stats()
        logging.debug(f"Stats: {stats['meta']}")
        now = time.time()
        if stats['meta']['last_report_at'] < now - UPDATE_INTERVAL:
            logging.info(f"Reporting Late: last report={stats['meta']['last_report_at']}, now={now}")
            leds.staleData()
        elif stats['meta']['status'] != "normal":
            logging.info(f"Abnormal Report: {stats['meta']}")
            leds.abnormalData()
            continue
        exitLoop.wait(pollInterval)
    logging.info("Shutting down")

#### TODO add flag to set watchdog pattern, and take it from the config file

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
        "-r", "--rate", action="store", type=int, choices=range(1, 13),
        default=DEF_INTERVAL,
        help="Interval at which to poll the Enlighten server (number of hours per call)")
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
