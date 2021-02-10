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


DEF_CONF_FILE = "./.enphase.yml"
DEF_LOG_LEVEL = "WARNING"
DEF_RATE = 4    # default: poll every 15 mins

CELLULAR_INTERVAL = 6 * 60 * 60  # Envoy updates server every six hours on Cellular
WIFI_INTERVAL = 15 * 60          # Envoy updates server every 15 mins on WiFi
UPDATE_INTERVAL = WIFI_INTERVAL  # using WiFi
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


def pattern1(iters, ramp, duration, onColor, offColor="black", led=1):
    """????
    """
    up = f"{onColor}, {ramp}, {led}"
    hold = f"{onColor}, {duration}, {led}"
    down = f"{offColor}, {ramp}, {led}"
    return f"{int(iters)}, {up}, {hold}, {down}"


def pattern2(iters, dutyCycle, period, onColor, offColor="black", ramp=0.25, led=1):
    """Generate a pattern that alternates between the on and off colors with
        the given duty cycle.

      N.B. this applies the pattern to a single LED

      The Blink1 pattern is: "<iterations>, {<color>, <rampTime>, <led>}+"
      This ramps up to the on color, holds at the on color, ramps down to the
       off color, holds at the off color, and repeats the selected number of
       times.

      Inputs:
        iters: integer number of cycles of the pattern to repeat
        dutyCycle: float between 0.0 and 1.0 that indicates fraction of the
                    period that should be the on and off colors.  0.0 means
                    always the min on color, 1.0 is max on color.
        onColor: string that defines the on color
        offColor: string that defines the off color
        ramp: optional float that defines the ramp between colors
        led: integer that selects which of the two LEDs to which the pattern is applied
      Returns: string in the Blink1 pattern format
    """
    assert dutyCycle >= 0.0 and dutyCycle <= 1.0, f"dutyCycle not between 0.0 and 1.0: {dutyCycle}"
    t = (dutyCycle * period) - ramp
    onTime = t if t > 0 else 0.0
    on = f"{onColor}, {ramp}, {led}, {onColor}, {onTime}, {led}"
    t = ((1.0 - dutyCycle) * period) - ramp
    offTime = t if t > 0 else 0.0
    off = f"{offColor}, {ramp}, {led}, {offColor}, {offTime}, {led}"
    return f"{int(iters)}, {on}, {off}"


class Indicators():
    """Object to encapsulate the Blink1 device.
      Each visual state of the device is selected by one of this object's methods.
    """
    def __init__(self):
        self.blink = Blink1()
        self.fadeTime = 100
        self.blink.fade_to_color(self.fadeTime, 'white')  # startup state

    def __del__(self):
        self.blink.off()
        self.blink.close()

    def staleData(self):
        """Indicate that the summary read from the Enlighten server is stale.
            I.e., older than the update rate
        """
        self.blink.fade_to_color(self.fadeTime, 'black', ledn=1)
        self.blink.fade_to_color(self.fadeTime, 'red', ledn=2)

    def currentData(self, normal):
        """Indicate that the summary is current, and further indicate whether it indicates normal operation.
        """
        self.blink.fade_to_color(self.fadeTime, 'black', ledn=1)
        if normal:
            self.blink.fade_to_color(self.fadeTime, 'green', ledn=2)
        else:
            self.blink.fade_to_color(self.fadeTime, 'orange', ledn=2)

    def data(self, output):
        """Indicate the amount of power currently being generated.
        """
        #### FIXME make this run a green pattern that indicates power output
        self.blink.fade_to_color(self.fadeTime, 'blue', ledn=2)

    def error(self):
        """Indicate that something went wrong.
          E.g., stats metadata indicates other than "normal" status
        """
        self.blink.fade_to_color(self.fadeTime, 'red', ledn=1)


def run(options):
    for s in CATCH_SIGNALS:
        signal.signal(getattr(signal, f"SIG{s}"), signalHandler)

    leds = Indicators()
    nliten = Enlighten(options['uid'], options['apiKey'], options['sysId'])
    if options['verbose']:
        json.dump(nliten.allSystems, sys.stdout, indent=4)

    pollInterval = (60 * 60) / options['rate']
    pollInterval = 3    #### TMP TMP TMP
    logging.info(f"Start polling: polling interval={pollInterval} secs")
    while not exitLoop.is_set():
        current = False
        normal = False
        while not (current and normal):
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
        logging.debug(f"Stats: {stats['meta']}")  #### TODO add summary of the data in intervals -- min/max/avg, reporting devices, etc.
        now = time.time()
        if stats['meta']['last_report_at'] < now - UPDATE_INTERVAL:
            logging.info(f"Reporting Late: last report={stats['meta']['last_report_at']}, now={now}")
            leds.error()
        elif stats['meta']['status'] != "normal":
            logging.info(f"Abnormal Report: {stats['meta']}")
            leds.error()
            continue
        else:
            powerOutput = 0  #### FIXME provide power output summary
            logging.info(f"Power Output: {powerOutput}")
            leds.data(powerOutput)
        exitLoop.wait(pollInterval)
    logging.info("Shutting down")


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
