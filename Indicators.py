"""
Library for using the Blink1() device as a status indicator for the Enlighten
 system.
"""
from blink1.blink1 import Blink1


DEF_WATCHDOG_INTERVAL = 60 * 1000 # 1min

MAX_PATTERN_LINES = 16


#### FIXME
def pattern1(iters, ramp, duration, onColor, offColor="black", led=1):
    """????
    """
    up = f"{onColor}, {ramp}, {led}"
    hold = f"{onColor}, {duration}, {led}"
    down = f"{offColor}, {ramp}, {led}"
    return f"{int(iters)}, {up}, {hold}, {down}"


#### FIXME
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
        led: integer that selects which of the LEDs to which the pattern is applied
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


#### TODO think about making indicator colors/patterns configurable via the initialization
class Indicators():
    """Object to encapsulate the Blink1 device.

      Each visual state of the device is selected by one of this object's methods.
    """
    def __init__(self, watchdogInterval=DEF_WATCHDOG_INTERVAL):
        self.watchdogInterval = watchdogInterval
        self.blink = Blink1()
        self.fadeTime = 100
        self.startPos = 0
        self.endPos = len(self.blink.read_pattern())
        self.blink.fade_to_color(self.fadeTime, 'gray')  # startup state

        self.blink.write_pattern_line(100, )

    def __del__(self):
        self.blink.server_tickle(enable=False)
        self.blink.off()  # exit/off state
        self.blink.close()

    def setWatchdogPattern(self, pattern):
        """Set the pattern to use when the device's watchdog isn't reset in
            time.

          The max pattern size is MAX_PATTERN_LINES - 2 (two lines are used
           for the flashing red pattern).

          N.B. This does not write the pattern to flash.

          Parameters:
            pattern: list of four-tuples that represent (r, g, b, msec) and
                      alternate between LED 0 and 1
        """
        if len(pattern) > MAX_PATTERN_LINES - 2:
            raise ValueError(f"Pattern too long, must be <= {MAX_PATTERN_LINES - 2}")
        self.startPos = 0
        self.endPos = len(pattern) - 1
        for i, p in enumerate(pattern):
            self.blink.write_pattern_line(p[3], p[0:3], i, i % 2)

    def pokeWatchdog(self):
        self.blink.server_tickle(enable=True,
                                 timeout_millis=self.watchdogInterval,
                                 start_pos=self.startPos,
                                 end_pos=self.endPos)

    def staleData(self):
        """Indicate that the summary read from the Enlighten server is stale.
            I.e., older than the update rate
        """
        self.blink.fade_to_color(self.fadeTime, 'orange', ledn=1)
        self.blink.fade_to_color(self.fadeTime, 'black', ledn=2)

    def lateReport(self):
        """Indicate that the stats read from the Enlighten server are older than the update rate
        """
        self.blink.fade_to_color(self.fadeTime, 'black', ledn=1)
        self.blink.fade_to_color(self.fadeTime, 'orange', ledn=2)

    def currentData(self, normal):
        """Indicate that the summary is current, and further indicate whether it indicates normal operation.
        """
        color = 'black' if normal else 'red'
        self.blink.fade_to_color(self.fadeTime, color, ledn=1)
        self.blink.fade_to_color(self.fadeTime, 'black', ledn=2)


    def abnormalData(self):
        """Indicate that something went wrong.
          E.g., stats metadata indicates other than "normal" status
        """
        self.blink.fade_to_color(self.fadeTime, 'black', ledn=1)
        self.blink.fade_to_color(self.fadeTime, 'red', ledn=2)


#
# TEST
#
if __name__ == '__main__':
    raise NotImplementedError("TBD")
