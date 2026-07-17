"""
Geiger Counter Data Management
- CircularBuffer: stores up to 30 CPM values
- SPIFFSLogger: persists CPM data to CSV on SPIFFS
"""

import os
import time
from machine import RTC


class CircularBuffer:
    """Fixed-size circular buffer for storing 30 CPM values."""
    
    def __init__(self, size=30):
        self.size = size
        self.buffer = [0] * size
        self.index = 0
        self.count = 0  # tracks how many values have been added (useful for startup)
    
    def append(self, value):
        """Add value to buffer, overwriting oldest if full."""
        self.buffer[self.index] = value
        self.index = (self.index + 1) % self.size
        if self.count < self.size:
            self.count += 1
    
    def get_all(self):
        """Return all values in chronological order (oldest first)."""
        if self.count < self.size:
            # Buffer not full yet; return only filled portion
            return self.buffer[:self.count]
        else:
            # Buffer full; rotate to show chronological order
            return self.buffer[self.index:] + self.buffer[:self.index]
    
    def get_last(self, n=1):
        """Get the last n values (most recent first)."""
        if n > self.count:
            n = self.count
        return [self.buffer[(self.index - i - 1) % self.size] for i in range(n)]
    
    def get_max(self):
        """Return maximum value in buffer."""
        if self.count == 0:
            return 0
        return max(self.get_all())
    
    def get_sum(self):
        """Return sum of all values in buffer."""
        return sum(self.get_all())
    
    def get_count(self):
        """Return number of data points."""
        return self.count
    
    def clear(self):
        """Clear all data."""
        self.buffer = [0] * self.size
        self.index = 0
        self.count = 0


class SPIFFSLogger:
    """Handles SPIFFS CSV logging and recovery of CPM data."""
    
    LOG_FILE = "/cpm_log.csv"
    TIMESTAMP_FORMAT = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}"
    
    def __init__(self):
        self.ensure_spiffs_mounted()
    
    @staticmethod
    def ensure_spiffs_mounted():
        """Mount SPIFFS if not already mounted."""
        try:
            os.stat("/")
        except:
            import vfs
            vfs.mount(vfs.VfsSPIFFS(0), "/")
    
    def get_timestamp(self, offset=0):
        """Get current timestamp as string (YYYY-MM-DD HH:MM:SS)."""
        try:
            #rtc = RTC()
            #dt = rtc.datetime()
            # dt format: (year, month, day, weekday, hour, minute, second, subsecond)
            # time.localtime returns: (year, month, day, hour, minute, second, weekday, yearday)
            localdt = time.localtime(time.time() + int(3600 * offset))
            return self.TIMESTAMP_FORMAT.format(localdt[0], localdt[1], localdt[2], localdt[3], localdt[4], localdt[5])
        except Exception as e:
            print("Failed to get timestamp:", e)
            return "1970-01-01 00:00:00"
    
    def save_cpm(self, cpm_value):
        """Append a CPM value with timestamp to CSV file."""
        try:
            timestamp = self.get_timestamp()
            with open(self.LOG_FILE, "a") as f:
                f.write(f"{timestamp},{cpm_value}\n")
        except Exception as e:
            print(f"Error saving CPM to SPIFFS: {e}")
    
    def load_history(self, buffer_obj, minutes=30):
        """
        Load CPM history from CSV and populate circular buffer.
        Reads the last `minutes` entries (or fewer if file has less data).
        """
        try:
            os.stat(self.LOG_FILE)
        except:
            print(f"Log file {self.LOG_FILE} not found; starting fresh")
            return
        
        try:
            lines = []
            with open(self.LOG_FILE, "r") as f:
                lines = f.readlines()
            
            # Take the last `minutes` lines (or all if fewer)
            start_idx = max(0, len(lines) - minutes)
            for line in lines[start_idx:]:
                line = line.strip()
                if line:
                    try:
                        parts = line.split(",")
                        if len(parts) == 2:
                            cpm_value = int(parts[1])
                            buffer_obj.append(cpm_value)
                    except:
                        pass  # Skip malformed lines
            
            print(f"Loaded {buffer_obj.get_count()} CPM data points from {self.LOG_FILE}")
        except Exception as e:
            print(f"Error loading CPM history: {e}")
    
    def clear_log(self):
        """Delete the CSV log file (for reset functionality)."""
        try:
            try:
                os.stat(self.LOG_FILE)
            except:
                return  # File doesn't exist, nothing to clear
            
            os.remove(self.LOG_FILE)
            print(f"Cleared log file {self.LOG_FILE}")
        except Exception as e:
            print(f"Error clearing log: {e}")
