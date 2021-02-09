"""
Library for interacting with the Enphase Enlighten Systems API

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


import logging
import os
import requests
import sys
import time


URL_PREFIX = "https://api.enphaseenergy.com/api/v2/systems"

API_CMDS = ('consumptionStats',
            'envoys',
            'inventory',
            'productionMeters',
            'rgmStats',
            'stats',
            'summary',
            'systems')

#### TODO document this

class Enlighten():
    """An object that encapsulates the Enphase Enlighten service's REST API.
    """
    @staticmethod
    def _rest(url):
        r = requests.get(url)
        if r.status_code == 200:
            response = r.json()
        else:
            logging.error(f"Failed REST call: {r.json()}")
            response = None
        logging.info(response)
        return response

    def __init__(self, uid, apiKey, sysId=None, hitsPerMin=10):
        """An object that encapsulates the Enphase Enlighten service's REST API.

          Parameters
            uid: string user Id from Enphase account
            apiKey: string API key from Enphase Enlighten
            sysId: optional string that identifies a specific system
        """
        self.uid = uid
        self.apiKey = apiKey
        self.hitsPerMin = hitsPerMin
        self.secsBetweenHits = 60 / self.hitsPerMin
        self.lastHit = None
        self.allSystems = self.systems()
        if sysId:
            self.sysId = sysId
        else:
            self.sysId = self.allSystems['systems'][0]['system_id']
            logging.warning("System Id not given, using first system found")
        self.urlPrefix = f"{URL_PREFIX}/{self.sysId}/"
        self.urlArgs = f"?key={self.apiKey}&user_id={self.uid}"

    #### FIXME try to run back-to-back calls faster, but stay under minute-granularity rates
    def rateLimitedREST(self, url):
        """Make a rate-limited call on the Enlighten server with the given URL

          Waits until at least the specified amount of time has elapsed since
           the last call.

          Parameters
            url: string with the url to use to call the Enlighten server
          Returns: JSON object with result of the REST invocation
        """
        if self.lastHit:
            delta = time.time() - self.lastHit
            if delta < self.secsBetweenHits:
                time.sleep(self.secsBetweenHits - delta)
        self.lastHit = time.time()
        return Enlighten._rest(url)

    def systems(self, isoFmt=False):
        """Returns information on all systems assoicated with the given user

          N.B.  This gets called during init so has to be handled differently

          Parameters
            isoFmt: optional boolean that returns datetimes in iso8601 format
                     if True, otherwise times are in seconds since Unix epoch
          Returns: JSON object containing data about the systems associated
                    with the user
        """
        fmt = "&datetime_format=iso8601" if isoFmt else ""
        url = f"{URL_PREFIX}?key={self.apiKey}&user_id={self.uid}"
        return self.rateLimitedREST(url)

    def consumptionStats(self, startAt=None, endAt=None, isoFmt=False):
        """Return performance statistics from a system's consumption meter

          If more than one month's worth of interfals are requested, then this
           returns a single month's worth of intervals.
          Intervals are 15 minutes long and start at the top of the hour.
          Requested times are rounded down to the nearest preceding interval.
          Returned data are tagged with the interval's end time -- therefore
           the first interval will have a timestamp that is up to five minutes
          Empty interval array is returned if no consumption meters are installed.

          Parameters
            startAt: optional starting interval time in Unix epoch seconds
            endAt: optional starting interval time in Unix epoch seconds
            isoFmt: optional boolean that returns datetimes in iso8601 format
                     if True, otherwise times are in seconds since Unix epoch
          Returns: JSON object that contains summary of consumption meter ????
        """
        fmt = "&datetime_format=iso8601" if isoFmt else ""
        start = f"&start_at={startAt}" if startAt else ""
        end = f"&end_at={endAt}" if endAt else ""
        url = f"{self.urlPrefix}consumption_stats{self.urlArgs}{start}{end}{fmt}"
        return self.rateLimitedREST(url)

    #### TODO DRY up these methods
    def envoys(self, isoFmt=False):
        """Returns information about all Envoy devices in the system

          Parameters
            isoFmt: optional boolean that returns datetimes in iso8601 format
                     if True, otherwise times are in seconds since Unix epoch
          Returns: JSON object with list of objects with details about each of
                    the Envoys in the system
        """
        fmt = "&datetime_format=iso8601" if isoFmt else ""
        return self.rateLimitedREST(f"{self.urlPrefix}envoys{self.urlArgs}{fmt}")

    def inventory(self, isoFmt=False):
        """Returns information about all devices in the system

          Parameters
            isoFmt: optional boolean that returns datetimes in iso8601 format
                     if True, otherwise times are in seconds since Unix epoch
          Returns: JSON object with lists of objects with details about each of
                    the intervers and meters in the system
        """
        fmt = "&datetime_format=iso8601" if isoFmt else ""
        return self.rateLimitedREST(f"{self.urlPrefix}inventory{self.urlArgs}{fmt}")

    def productionMeters(self, readAt=None, isoFmt=False):
        """Return the last reading of each production meter in the system

          Parameters
            readAt: optional time to read meter in seconds from Unix epoch
            isoFmt: optional boolean that returns datetimes in iso8601 format
                     if True, otherwise times are in seconds since Unix epoch
          Returns: JSON object with list of objects containing data for each
                    production meter -- serial number, value in Wh, time when
                    reading was taken (before or at the given readAt time), and
                    metadata -- status, last report, laster energy, operational
        """
        fmt = "&datetime_format=iso8601" if isoFmt else ""
        day = f"&end_at={readAt}" if readAt else ""
        url = f"{self.urlPrefix}production_meter_readings{self.urlArgs}{fmt}{day}"
        return self.rateLimitedREST(url)

    def rgmStats(self, startAt=None, endAt=None, isoFmt=False):
        """Return performance statistics from a system's Revenue-Grade Meters (RGMs)

          If more than one month's worth of interfals are requested, then this
           returns a single month's worth of intervals.
          Intervals are 15 minutes long and start at the top of the hour.
          Requested times are rounded down to the nearest preceding interval.
          Returned data are tagged with the interval's end time -- therefore
           the first interval will have a timestamp that is up to five minutes
          Empty interval array is returned if no RGMs are installed.

          Parameters
            startAt: optional starting interval time in Unix epoch seconds
            endAt: optional starting interval time in Unix epoch seconds
            isoFmt: optional boolean that returns datetimes in iso8601 format
                     if True, otherwise times are in seconds since Unix epoch
          Returns: JSON object that contains summary of production from all
                    RGMs in the system
        """
        fmt = "&datetime_format=iso8601" if isoFmt else ""
        start = f"&start_at={startAt}" if startAt else ""
        end = f"&end_at={endAt}" if endAt else ""
        url = f"{self.urlPrefix}rgm_stats{self.urlArgs}{start}{end}{fmt}"
        return self.rateLimitedREST(url)

    def stats(self, startAt=None, endAt=None, isoFmt=False):
        """Return performance statistics as reported by microinverters

          If more than one day of interfals are requested, then this returns
           a single day's worth of intervals.
          Intervals are five minutes long and start at the top of the hour.
          Requested times are rounded down to the nearest preceding interval.
          Returned data are tagged with the interval's end time -- therefore
           the first interval will have a timestamp that is up to five minutes

          Parameters
            startAt: optional starting interval time in Unix epoch seconds
            endAt: optional starting interval time in Unix epoch seconds
            isoFmt: optional boolean that returns datetimes in iso8601 format
                     if True, otherwise times are in seconds since Unix epoch
          Returns: JSON object that contains summary of production from all
                    reporting microinverters during each requested interval
        """
        fmt = "&datetime_format=iso8601" if isoFmt else ""
        start = f"&start_at={startAt}" if startAt else ""
        end = f"&end_at={endAt}" if endAt else ""
        url = f"{self.urlPrefix}stats{self.urlArgs}{start}{end}{fmt}"
        return self.rateLimitedREST(url)

    def summary(self, summaryDate=None, isoFmt=False):
        """Returns summary information for a system

          If no date is provided, then the current day at minight site-local
           time is used.

          Parameters
            summaryDate: optional string indicating the day for which a summary
                   is requested, given in "YYYY-mm-dd" format in the system's
                   timezone
            isoFmt: optional boolean that returns datetimes in iso8601 format
                     if True, otherwise times are in seconds since Unix epoch
          Returns: JSON object containing system-level summary of the system at
                    the requested date
        """
        fmt = "&datetime_format=iso8601" if isoFmt else ""
        date = f"&summary_date={summaryDate}" if summaryDate else ""
        url = f"{self.urlPrefix}summary{self.urlArgs}{date}{fmt}"
        return self.rateLimitedREST(url)

#
# TEST
#
if __name__ == '__main__':
    raise NotImplementedError("TBD")

