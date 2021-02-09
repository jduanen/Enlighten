#!/usr/bin/env python3
"""
Tool for interacting with the Enphase Enlighten Systems API

This needs three values to access the Enphase API -- an API key, a user ID,
 and (for some, but not all commands) a system ID.
These values can be obtained from a configuration (YAML) file, and the values
 contained within this file can be overriden with command-line options.
If any of these values is not found in the configuration file, or given on the
 command line, then and attempt will be made to obtain it from one of these
 environment variables: ENPHASE_API_KEY, ENPHASE_UID, and ENPHASE_SYSID.

If sysId not given, the ID of the first system found will be used.

This was derived from the excellent API documentation provided by Enphase at:
 https://developer.enphase.com/docs

The "Watt" plan allows 10 hits/min and 10,000 hits/month for free.
"""

'''
TODO
* Commands
  - consumption_lifetime
  - consumption_stats
  - energy_lifetime
#  - envoys
X  - index
#  - inventory
  - inverters_summary_by_envoy_or_site
X  - monthly_production
#  - production_meter_readings
#  - rgm_stats
#  - stats
#  - summary
X  - search_system_id
'''


import argparse
from datetime import datetime
import json
import logging
import os
import requests
import sys
import time

import yaml

from Enlighten import Enlighten, API_CMDS


DEF_CONF_FILE = "./.enphase.yml"
DEF_LOG_LEVEL = "WARNING"
DEF_CMDS = ["systems"]

TIME_FORMAT = "%d-%m-%Y %H:%M"  # e.g., "08-02-2021 17:30"
ESC_TIME_FORMAT = TIME_FORMAT.replace('%', '%%')


#### TODO document this

def run(options):
    if options['verbose'] > 1:
        json.dump(options, sys.stdout, indent=4)
        print("")
    nliten = Enlighten(options['uid'], options['apiKey'], options['sysId'])
    results = {}
    if 'consumptionStats' in options['commands']:
        results['consumptionsStats'] = nliten.consumptionStats(options['start'], options['end'], options['isoFormat'])
    if 'envoys' in options['commands']:
        results['envoys'] = nliten.envoys(options['isoFormat'])
    if 'inventory' in options['commands']:
        results['inventory'] = nliten.inventory(options['isoFormat'])
    if 'productionMeters' in options['commands']:
        results['productionMeters'] = nliten.productionMeters(options['day'], options['isoFormat'])
    if 'rgmStats' in options['commands']:
        results['rgmStats'] = nliten.rgmStats(options['start'], options['end'], options['isoFormat'])
    if 'stats' in options['commands']:
        results['stats'] = nliten.stats(options['start'], options['end'], options['isoFormat'])
    if 'summary' in options['commands']:
        results['summary'] = nliten.summary(options['day'], options['isoFormat'])
    if 'systems' in options['commands']:
        results['systems'] = nliten.systems(options['isoFormat'])
    json.dump(results, sys.stdout, indent=4)
    print("")


def getOps():
    usage = f"Usage: {sys.argv[0]} [-v] " + \
             "[-c <confFile>] [-L <logLevel>] [-l <logFile>] " + \
             "[-i] [-b <time>] [-e <time>] [-d <time>]" + \
             "[-a <apiKey>] [-u <uid>] [-s <sysId>] [-C <cmd>{,<cmd'>}*]"
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-a", "--apiKey", action="store", type=str,
        help="Enphase Enlighten Systems API key")
    ap.add_argument(
        "-b", "--beginTime", action="store", type=str,
        help=f"Start of time interval of interest (format={ESC_TIME_FORMAT})")
    ap.add_argument(
        "-C", "--cmdsList", action="store", type=str, nargs="+",
        choices=API_CMDS, default=DEF_CMDS,
        help="Path to YAML file with configuration information")
    ap.add_argument(
        "-c", "--confFile", action="store", type=str,
        default=DEF_CONF_FILE, help="Path to YAML file with configuration information")
    ap.add_argument(
        "-d", "--dayTime", action="store", type=str,
        help=f"Day of interest (format={ESC_TIME_FORMAT})")
    ap.add_argument(
        "-e", "--endTime", action="store", type=str,
        help=f"End of time interval of interest (format={ESC_TIME_FORMAT})")
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
        "-s", "--sysId", action="store", type=str,
        help="Enphase Enlighten System Id")
    ap.add_argument(
        "-u", "--uid", action="store", type=str,
        help="Enphase Enlighten User Id")
    ap.add_argument(
        "-v", "--verbose", action="count", default=0, help="Print debug info")
    #### read list of calls to make
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
        logging.error("Must supply API Key")
        sys.exit(1)

    if 'uid' not in conf:
        logging.error("Must supply User Id")
        sys.exit(1)

    day = int(datetime.strptime(opts.dayTime, TIME_FORMAT).timestamp()) if opts.dayTime else None
    start = int(datetime.strptime(opts.beginTime, TIME_FORMAT).timestamp()) if opts.beginTime else None
    end = int(datetime.strptime(opts.endTime, TIME_FORMAT).timestamp()) if opts.endTime else None
    if start and end and start > end:
        logging.error(f"Begin time ({opts.beginTime}) must be before End time ({opts.endTime})")
        sys.exit(1)

    options = vars(opts)
    options['day'] = day
    options['start'] = start
    options['end'] = end
    options['commands'] = opts.cmdsList
    options.update(conf)
    return(options)


if __name__ == '__main__':
    opts = getOps()
    run(opts)
