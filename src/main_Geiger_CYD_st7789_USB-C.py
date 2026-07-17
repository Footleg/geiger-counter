"""
# Geiger Counter with Touchscreen Display using LVGL GUI
#
# Displays counts per minute on a bar chart, updated every 15 seconds.
# 
# This version is for the CYD board variant using the st7798 graphcis chip.
# The boards I bought in June 2026 with the USB-C and Micro USB connectors
# use this graphics chip. You need to use the Micropython firmware with
# st7789 in the filename for this variant of the CYD board.
#
# Save this file as 'main.py' so that it auto-runs on power on. Make sure you
# also copy the geiger_data.py and secrets.py files to the CYD board.
#
# Copyright (C) 2026 Paul Fretwell - aka 'Footleg'
# 
# Released under the [GPL-3.0 License](https://opensource.org/license/gpl-3.0).
    
"""

from micropython import const
import lvgl as lv
from time import sleep_ms, sleep_us, ticks_diff, ticks_us, sleep
from machine import Timer, Pin, SPI, RTC
import network
import ntptime
import secrets 
import lcd_bus
import st7789 # Replace  import ili9341
import xpt2046
import touch_cal_data
import task_handler
from geiger_data import CircularBuffer, SPIFFSLogger

# Microcontroller pins
_DETECTION_PIN = const(22) # Using GPIO 22 on the CYD

# ============== Customize settings ============== #
# The following values need to be customized.

# Switch width and height for portrait mode (original).
_DISPLAY_WIDTH = const(320)
_DISPLAY_HEIGHT = const(240)
# Try different values from rotation table, see below.
_DISPLAY_ROT = const(0xA0)
# Set to True if red and blue are switched.
_DISPLAY_BGR = const(1)
# May have to be set to 0 if both RGB / BGR mode give bad results.
_DISPLAY_RGB565_BYTE_SWAP = const(1)
# Allow touch calibration. Set to True when display works correctly.
_ALLOW_TOUCH_CAL = const(1)
# Show marker at current touch coordinates.
_DISPLAY_SHOW_TOUCH_INDICATOR = const(1)


# ============== Display / Indev initialization ============== #
# no need to change anything below here
_SPI_BUS_HOST = const(1)
_SPI_BUS_MOSI = const(13)
_SPI_BUS_MISO = const(12)
_SPI_BUS_SCK = const(14)
_INDEV_BUS_HOST = const(2)
_INDEV_BUS_MOSI = const(32)
_INDEV_BUS_MISO = const(39)
_INDEV_BUS_SCK = const(25)
_INDEV_DEVICE_FREQ = const(2000000)
_INDEV_DEVICE_CS = const(33)
_DISPLAY_BUS_FREQ = const(24000000)
_DISPLAY_BUS_DC = const(2)
_DISPLAY_BUS_CS = const(15)
_DISPLAY_BACKLIGHT_PIN = const(21)

spi_bus = None
try:
    spi_bus = SPI.Bus(
        host=_SPI_BUS_HOST,
        mosi=_SPI_BUS_MOSI,
        miso=_SPI_BUS_MISO,
        sck=_SPI_BUS_SCK
    )
except:
    # Micropython with LVGL appears to rewrite SPI class interface in memory,
    # so this fails after a soft reset (i.e. When stopped and re-run from code editor)
    import machine
    machine.reset() # A hard reset fixes it so you can run it again from code editor
    
indev_bus = SPI.Bus(
    host=_INDEV_BUS_HOST,
    mosi=_INDEV_BUS_MOSI,
    miso=_INDEV_BUS_MISO,
    sck=_INDEV_BUS_SCK
)

indev_device = SPI.Device(
    spi_bus=indev_bus,
    freq=_INDEV_DEVICE_FREQ,
    cs=_INDEV_DEVICE_CS
)

display_bus = lcd_bus.SPIBus(
    spi_bus=spi_bus,
    freq=_DISPLAY_BUS_FREQ,
    dc=_DISPLAY_BUS_DC,
    cs=_DISPLAY_BUS_CS
)

display = st7789.ST7789(
    data_bus=display_bus,
    display_width=_DISPLAY_WIDTH,
    display_height=_DISPLAY_HEIGHT,
    backlight_pin=_DISPLAY_BACKLIGHT_PIN,
    backlight_on_state=st7789.STATE_PWM,
    color_space=lv.COLOR_FORMAT.RGB565,
    color_byte_order=st7789.BYTE_ORDER_BGR if _DISPLAY_BGR else st7789.BYTE_ORDER_RGB,
    rgb565_byte_swap=_DISPLAY_RGB565_BYTE_SWAP
)

# The rotation table MUST be defined
display._ORIENTATION_TABLE = (
    _DISPLAY_ROT, # this value sets the rotation
    0x0, # placeholder
    0x0, # placeholder
    0x0 # placeholder
)

# lv.DISPLAY_ROTATION._0 uses the first value from the
# display._ORIENTATION_TABLE to set display rotation
display.set_rotation(lv.DISPLAY_ROTATION._0)
display.set_power(True)
display.init() #For ili9341 use: display.init(1)
display_bus.tx_param(0x20, bytearray([]))
display.set_backlight(100)

indev = xpt2046.XPT2046(device=indev_device)

# Calibration data is stored in the non-volatile storage (NVS) of the Esp32
if not indev.is_calibrated and _ALLOW_TOUCH_CAL:
    indev.calibrate()
    indev._cal.save()

task_handler.TaskHandler()

timezone_offset = 0 # Default to 0 for case where clock is set over USB from code editor

# ============== Wi-Fi Connection and Time Setting ========== #
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Scanning for Wi-Fi networks...")
        networks = wlan.scan()
        
        if len(networks):
            for net in networks:
                ssid = net[0].decode('utf-8')  # Decode binary bytes to readable text
                rssi = net[3]                  # Signal strength indicator (dBm)
    
                # Ignore empty/hidden hidden networks
                try_sidd = ssid.strip()
                if try_sidd:
                    
                    # Check SID against secrets
                    for i in range(len(secrets.WIFI_SSID)):
                        print(f"Checking {try_sidd} against secrets SIDD {secrets.WIFI_SSID[i]}")
                        if try_sidd == secrets.WIFI_SSID[i]:
                            print(f"Connecting to {secrets.WIFI_SSID[i]}...")
                            wlan.connect(secrets.WIFI_SSID[i], secrets.WIFI_PASS[i])
                            
                            # Wait up to 10 seconds for connection
                            timeout = 10
                            while not wlan.isconnected() and timeout > 0:
                                sleep_ms(1000)
                                timeout -= 1
                             
                            if wlan.isconnected():
                                print("Wi-Fi connected successfully!")
                                print("IP Address:", wlan.ifconfig()[0])
                                return True
        else:
            print("No Wi-Fi networks detected.")
        
    if wlan.isconnected():
        print("Wi-Fi already connected.")
        return True
    else:
        print("Wi-Fi connection failed.")
        return False

def sync_time():
    global timezone_offset
    
    tries = 0
    while tries < 5:
        try:
            print("Fetching time from NTP server...")
            # ntptime.settime() fetches UTC time and updates the ESP32's internal RTC
            ntptime.settime()
            print("Time synced successfully!")
            timezone_offset = secrets.timezone_offset
            return
        except Exception as e:
            print("Failed to fetch time from NTP:", e)
        sleep_ms(200)
        tries += 1

# ============== Geiger Counter Initialization ============== #
class GeigerCounter:
    """Manages geiger counter pulse detection and per-minute CPM calculation."""
    
    def __init__(self, pin_num, buffer, logger):
        self.pin = Pin(pin_num, Pin.IN) # Do not pull_up as geiger counter holds the pin high and 
                                        # a pullup overwhelms the brief active low so it is not detected.
        self.update_period = 15_000 # How many ms to calculate the counts per minute over
        self.buffer = buffer
        self.logger = logger
        self.pulse_count = 0
        self.alltime_pulse_count = 0
        self.last_pulse_count = 0
        self.callbacks = []  # List of functions to call on CPM update
        self.ticks_last_cpm_calc = ticks_us()
        self.pulse_counts_buffer = [] # Buffer to hold the most recent counts per time interval to be averaged
        self.total_readings_to_Average = 60_000 // self.update_period # Number of time intervals in a minute
        self.readings_buffered = 0
        
        # Attach interrupt for falling edge (active low pulse)
        self.pin.irq(trigger=Pin.IRQ_FALLING, handler=self._pulse_handler)
        
        # Timer for screen updates (fires every 0.5 seconds)
        self.timer = Timer(0)
        self.timer.init(period=250, mode=Timer.PERIODIC, callback=self._timer_handler)
        
        print(f"Geiger Counter initialized on GPIO {pin_num}")
    
    def _pulse_handler(self, pin):
        """Interrupt callback for each geiger pulse."""
        self.pulse_count += 1
        self.alltime_pulse_count += 1
        #print(f"Pulses {self.pulse_count}")
    
    def _timer_handler(self, timer):
        """Timer callback fired every second to check if 15 seconds elapsed."""
        mean_cpm = -1 # Indicates this is not a cpm update cycle
        ticks_now = ticks_us()
        ticks_since = ticks_diff(ticks_now, self.ticks_last_cpm_calc)
        #print(f"Ticks: Now={ticks_now} Since last calc.={ticks_since}")
        if self.last_pulse_count != self.pulse_count or ticks_since >= self.update_period * 1000:
            # Trigger a screen update
            self.last_pulse_count = self.pulse_count

            if ticks_since >= self.update_period * 1000:
                # Calculate CPM and reset counter
                print(f"Count: {self.pulse_count}; ticks since: {ticks_since}")
                self.ticks_last_cpm_calc = ticks_now
                
                # Update local buffer which we use to calculate a rolling average cpm
                if len(self.pulse_counts_buffer) < self.total_readings_to_Average:
                    self.pulse_counts_buffer.append((self.pulse_count,ticks_since))
                else:
                    # Move readings down one position and add latest
                    for i in range(self.total_readings_to_Average - 1):
                        self.pulse_counts_buffer[i] = self.pulse_counts_buffer[i + 1]
                    self.pulse_counts_buffer[self.total_readings_to_Average - 1] = (self.pulse_count,ticks_since)
                self.readings_buffered += 1
                print(f"Readings: {self.pulse_counts_buffer}")
                total_pulses = 0
                total_ticks = 0
                for value in self.pulse_counts_buffer:
                    total_pulses += value[0]
                    total_ticks += value[1]
                mean_cpm = total_pulses * 60_000_000 // total_ticks
                self.pulse_count = 0

                if self.readings_buffered >= self.total_readings_to_Average:
                    self.readings_buffered = 0
                    # Update cpm longterm buffer and log
                    self.buffer.append(mean_cpm)
                    self.logger.save_cpm(mean_cpm)
            
            # Fire callbacks to update UI
            for callback in self.callbacks:
                try:
                    callback(mean_cpm, self.alltime_pulse_count, self.buffer)
                except Exception as e:
                    print(f"Error in CPM callback: {e}")
    
    def add_callback(self, func):
        """Register a callback function to be called when CPM updates."""
        self.callbacks.append(func)
    
    def get_pulse_count(self):
        """Get current pulse count in this minute (live, not final)."""
        return self.pulse_count
    
    def reset(self):
        """Reset all counters and clear data."""
        self.pulse_count = 0
        self.seconds_elapsed = 0
        self.buffer.clear()
        self.pulse_counts_buffer = []
        self.logger.clear_log()
        print("Geiger Counter reset")

# ============== End of display / touch (indev) setup ============== #

def palette_color(c, shade = 0):
    '''
    Returns a color from LVGL's main palette and
    lightens or darkens the color by a specified shade.
    
    Palette Colors:
    RED, PINK, PURPLE, DEEP_PURPLE, INDIGO, BLUE,
    LIGHT_BLUE, CYAN, TEAL, GREEN, LIGHT_GREEN, LIME, 
    YELLOW, AMBER, ORANGE, DEEP_ORANGE, BROWN, BLUE_GREY, GREY
    '''
    attr = getattr(lv.PALETTE, c.upper(), 'Undefined')
    if attr != 'Undefined':
        if not (shade in range(-4, 6)): return lv.color_black()
        if shade == 0:
            return lv.palette_main(attr)
        elif shade > 0:
            return lv.palette_lighten(attr, shade)
        elif shade < 0:
            return lv.palette_darken(attr, abs(shade))
    else:
        return lv.color_black()

class RectStyle(lv.style_t):
    def __init__(self, bg_color=lv.color_black()):
        super().__init__()
        self.set_bg_opa(lv.OPA._100)
        self.set_bg_color(bg_color)
        self.set_text_opa(lv.OPA._100)
        self.set_text_color(lv.color_black())

class Rect():
    def __init__(self, align, color, parent):
        self.align = align
        self.color = palette_color(color)
        self.parent = parent
        
        self.lvalign = getattr(lv.ALIGN, self.align, 'Undefined')
        
        s = self.align.split('_') # Remove undersore from align value and
        self.text = s[0][0] + s[1][0] # converts e.g. TOP_LEFT to TL as shortcut
        
        self.rect = lv.obj(parent)
        self.rect.remove_style_all()
        self.rect.set_size(35, 35)
        self.rect.align(self.lvalign, 0, 0)
        self.rect.add_style(RectStyle(bg_color = self.color), lv.PART.MAIN)
        self.rect.add_style(RectStyle(bg_color = lv.color_white()), lv.PART.MAIN | lv.STATE.PRESSED)
        self.rect.add_event_cb(lambda e: self._cb(), lv.EVENT.CLICKED, None)
        
        self.lbl = lv.label(self.rect)
        self.lbl.remove_style_all()
        self.lbl.set_text(self.text)
        self.lbl.center()
        
    def _cb(self):
        # Get touch coordinates
        point = lv.point_t()
        indev.get_point(point)

        status_lbl.set_text(f'{self.align.replace("_", " ")} obj clicked!\n(x: {point.x}, y: {point.y})')
        status_lbl.set_style_text_color(self.color, 0)
        
class FlexRowStyle(lv.style_t):
    def __init__(self):
        super().__init__()
        
        self.set_text_align(lv.TEXT_ALIGN.CENTER)
        
        self.set_flex_flow(lv.FLEX_FLOW.ROW_WRAP)
        self.set_flex_main_place(lv.FLEX_ALIGN.SPACE_EVENLY)
        self.set_layout(lv.LAYOUT.FLEX)

# ============== Touch Indicator Setup ============== #
class CircleStyle(lv.style_t):
    def __init__(self):
        super().__init__()

        self.set_bg_opa(lv.OPA._40)
        self.set_bg_color(lv.color_hex3(0x0F0))
        self.set_radius(lv.RADIUS_CIRCLE)
        self.set_border_opa(lv.OPA._100)
        self.set_border_width(2)
        self.set_border_color(lv.color_hex3(0x0F0))

class TouchIndicator():
    def __init__(self, position_x, position_y):
        
        _size = 10
        self.circle = lv.obj(lv.screen_active())
        self.circle.remove_style_all()
        self.circle.set_size(_size, _size)
        self.circle.set_pos(int(position_x - _size / 2), int(position_y - _size / 2))
        self.circle.add_style(CircleStyle(), lv.PART.MAIN)
    
    def delete(self):
        self.circle.delete()

ti = None # Store TouchIndicator object between calls of touch_cb
def touch_cb(e = None):
    global ti
    code = e.get_code()
    
    if code == lv.EVENT.CLICKED:
        if ti is not None:
            ti.delete()
        
        point = lv.point_t()
        indev.get_point(point)
        
        ti = TouchIndicator(point.x, point.y)
        print(f"Touch at {point.x}, {point.y}")
    else:
        pass

if _DISPLAY_SHOW_TOUCH_INDICATOR:
    indev.add_event_cb(touch_cb, lv.EVENT.ALL, None)

# ========== Geiger Counter UI ========== #

print("DEBUG: Starting UI initialization...")

# Create main screen
scr = lv.screen_active()
scr.set_style_bg_color(lv.color_black(), lv.PART.MAIN)
scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

print("DEBUG: Screen created and configured")

# --------- Title Bar ---------
title_lbl = lv.label(scr)
title_lbl.set_text("Geiger Counter")
title_lbl.set_style_text_font(lv.font_montserrat_16, 0)
title_lbl.set_style_text_color(lv.palette_main(lv.PALETTE.YELLOW), 0)
title_lbl.align(lv.ALIGN.TOP_MID, 0, 2)

print("DEBUG: Title label created")

# --------- Chart Widget ---------
# 1. Define Chart and Axis Parameters
chart_min_y = 0
chart_max_y = 200
scale_width = 30
chart_width = 286
chart_height = 170

# 2. Create a Flex Container to hold the Scale and Chart horizontally
container = lv.obj(scr)
container.remove_style_all() # Remove default borders/padding for alignment
container.set_size(lv.SIZE_CONTENT, lv.SIZE_CONTENT)
container.set_flex_flow(lv.FLEX_FLOW.ROW)
container.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.START)
container.align(lv.ALIGN.TOP_MID, 0, 20)
# This extends the container height to accommodate the label overflow.
container.set_style_pad_top(6, 0)     # Adjust based on your font size
container.set_style_pad_bottom(6, 0)  # Adjust based on your font size

# 3. Create the Y-Axis Scale (Placed on the left side)
y_scale = lv.scale(container)
y_scale.set_size(scale_width, chart_height) # Width provides space for labels
y_scale.set_mode(lv.scale.MODE.VERTICAL_LEFT)
y_scale.set_range(chart_min_y, chart_max_y)

# Configure Ticks: 5 major divisions (0, 25, 50, 75, 100)
y_scale.set_total_tick_count(21)     # Total ticks (major + minor marks)
y_scale.set_major_tick_every(5)      # Major tick interval
y_scale.set_label_show(True)         # Enable numeric labels

# Apply standard font to the labels (PART_INDICATOR handles text elements)
y_scale.set_style_text_font(lv.font_montserrat_12, lv.PART.INDICATOR)

# 4. Create the Bar Chart (Placed on the right side)
chart = lv.chart(container)
chart.set_size(chart_width, chart_height)
chart.set_type(lv.chart.TYPE.BAR)
chart.set_style_pad_column(2, lv.PART.MAIN) # 2 pixels of spacing between bars
chart.set_point_count(30) # Number of bars
chart.set_div_line_count(5, 0) # Number of horizontal grid lines
# Range MUST match the scale's range perfectly
chart.set_axis_range(lv.chart.AXIS.PRIMARY_Y, chart_min_y, chart_max_y)


# Add minor top/bottom padding to align the chart lines to the ticks
chart.set_style_pad_top(5, 0)
chart.set_style_pad_bottom(5, 0)

# 5. Add a Data Series and inject values

# Add a series for CPM data
series_cpm = chart.add_series(lv.palette_main(lv.PALETTE.GREEN), lv.chart.AXIS.PRIMARY_Y)

# --------- Stats Labels ---------
# Current CPM in center-right
cpm_lbl = lv.label(scr)
cpm_lbl.set_text("CPM: -")
cpm_lbl.set_style_text_font(lv.font_montserrat_16, 0)
cpm_lbl.set_style_text_color(lv.palette_main(lv.PALETTE.YELLOW), 0)
cpm_lbl.align(lv.ALIGN.BOTTOM_MID, 0, -24)

# Pulses at bottom
pulse_lbl = lv.label(scr)
pulse_lbl.set_text("Fetching network time...")
pulse_lbl.set_style_text_font(lv.font_montserrat_14, 0)
pulse_lbl.set_style_text_color(lv.color_white(), 0)
pulse_lbl.align(lv.ALIGN.BOTTOM_LEFT, 2, -2)

# Date Time
dt_lbl = lv.label(scr)
dt_lbl.set_text("(date time)")
dt_lbl.set_style_text_font(lv.font_montserrat_14, 0)
dt_lbl.set_style_text_color(lv.color_white(), 0)
dt_lbl.align(lv.ALIGN.BOTTOM_RIGHT, -6, -2)

# Connect to wifi to set clock if possible
if connect_wifi():
    sync_time()
    
# Queued update mechanism (for timer callback context)
pending_update = {'cpm': None, 'pulses': None, 'needs_redraw': False, 'is_cpm_update': False}

# Simple callback to update labels
def simple_update(cpm, pulses, buffer):
    # Queue the update instead of directly modifying LVGL
    pending_update['cpm'] = cpm
    pending_update['pulses'] = pulses
    pending_update['is_cpm_update'] = (cpm > 0)  # Only a CPM update if cpm is valid (60-second boundary)
    pending_update['needs_redraw'] = True
    
    #print(f"DEBUG: Update queued. CPM={cpm}, Total={pulses}, Buffer Sum={buffer.get_sum()}")

print('Geiger Counter UI loaded. Waiting for pulses...')

# Initialize geiger counter AFTER UI (moved here to avoid blocking)
print("DEBUG: Creating readings data buffer")
geiger_buffer = CircularBuffer(size=30)
print("DEBUG: Logger")
geiger_logger = SPIFFSLogger()
print("DEBUG: Loading history from file")
geiger_logger.load_history(geiger_buffer, minutes=30)
print("DEBUG: Creating Geiger Counter")
geiger_counter = GeigerCounter(pin_num=_DETECTION_PIN, buffer=geiger_buffer, logger=geiger_logger)
geiger_counter.add_callback(simple_update)

print("DEBUG: Geiger counter initialized successfully")

while True:
    # Process queued UI updates in main loop context
    if pending_update['needs_redraw']:
        if pending_update['cpm'] > 0:
            cpm_lbl.set_text(f"CPM: {pending_update['cpm']}")
        if pending_update['pulses'] is not None:
            pulse_lbl.set_text(f"Pulses: {pending_update['pulses']}")
        print(geiger_logger.get_timestamp(timezone_offset))
        dt_lbl.set_text(geiger_logger.get_timestamp(timezone_offset))

        if pending_update['is_cpm_update']:
            cpm = pending_update['cpm']
                
            if cpm > 120:
                chart.set_series_color(series_cpm, lv.palette_main(lv.PALETTE.RED))
            elif cpm > 100:
                chart.set_series_color(series_cpm, lv.palette_main(lv.PALETTE.ORANGE))
            elif cpm > 50:
                chart.set_series_color(series_cpm, lv.palette_main(lv.PALETTE.YELLOW))
            else:
                chart.set_series_color(series_cpm, lv.palette_main(lv.PALETTE.GREEN))
                
            chart.set_next_value(series_cpm, pending_update['cpm'])

            # Check for maximum on chart
            max_cpm = cpm
            c_array = lv.chart.get_series_y_array(chart, series_cpm)
            point_count = chart.get_point_count()
            for i in range(point_count):
                value = c_array[i]
                if value < 2147483647 and value > max_cpm:
                    max_cpm = value

            # Set scale increment base on size
            if max_cpm < 100:
                new_max = 100
            elif max_cpm < 1000:
                new_max = ((max_cpm // 100) + 1) * 100
            else:
                new_max = ((max_cpm // 500) + 1) * 500

            # Adjust chart scale if too small for max reading, or if more than double max reading
            if new_max > chart_max_y or new_max <= chart_max_y // 2:
                chart_max_y = new_max
                if new_max > 1000:
                    scale_width = 40
                    chart_width = 275
                elif new_max > 100:
                    scale_width = 34
                    chart_width = 282
                else:
                    scale_width = 26
                    chart_width = 290
                y_scale.set_range(chart_min_y, chart_max_y)
                y_scale.set_size(scale_width, chart_height) # Width provides space for labels
                chart.set_size(chart_width, chart_height)
                chart.set_axis_range(lv.chart.AXIS.PRIMARY_Y, chart_min_y, chart_max_y)
        
        # Invalidate screen to trigger redraw
        scr.invalidate()
        lv.refr_now(lv.display_get_default())
        pending_update['needs_redraw'] = False
        #print(f"DEBUG: Display updated - CPM label and Pulses label refreshed")
    
    sleep_ms(50)

