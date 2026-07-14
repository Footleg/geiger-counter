# Geiger Counter

A Geiger Counter maker project by Footleg. This is a hobby science project and not a calibrated scientific instrument. It will typically record a natural background radiation level between 15-30 counts per minute. Interactions with beta and gamma radiation are counted over 15 second intervals and the count per minute extrapolated from these counts. The displayed CPM readings are averaged over the last minute, but updated every 15 seconds (so the last 4 periods of 15 seconds are used for each update of the displayed reading).

The code is written in MicroPython and deployed onto an ESP32 touchscreen display. If you want to access or update the code on the device, you can connect to it from the Thonny code editor as an ESP32 device.

Credentials for WiFi are read from a secrets.py file. You can add multiple Wi-Fi access points to this file, and the device will check available Wi-Fi networks on boot up and connect to the first one which matches credentials found in the secrets file. Wi-Fi is only used to set the device clock on boot.

The device has a touch screen but the UI is not using it at this stage of the code development.

The Micropython firmware with LVGL graphics library was built from the repo at https://github.com/de-dh/ESP32-Cheap-Yellow-Display-Micropython-LVGL/
Be aware that different variants of the CYD boards use different display driver chips, so you may need to build the firmware with the correct settings for your particular hardware. The code to set up the display is also specific to the display driver on the board.
