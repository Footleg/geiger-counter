# Geiger Counter

This is a hobby science project and not a calibrated scientific instrument. It will typically record a natural background radiation level between 15-30 counts per minute. Interactions with beta and gamma radiation are counted over 15 second intervals and the count per minute extrapolated from these counts. The displayed CPM readings are averaged over the last minute, but updated every 15 seconds (so the last 4 periods of 15 seconds are used for each update of the displayed reading). Higher levels of radiation can be measured in the proximity of Uranium Glass, Thoriated Tungsten welding electrodes and antique radium painted dials. Potassium Chloride (Lo Salt) should measure higher than general background levels too. 

The code is written in MicroPython and deployed onto an ESP32 touchscreen display. If you want to access or update the code on the device, you can connect to it from the Thonny code editor as an ESP32 device.

Credentials for WiFi are read from a secrets.py file. You can add multiple Wi-Fi access points to this file, and the device will check available Wi-Fi networks on boot up and connect to the first one which matches credentials found in the secrets file. Wi-Fi is only used to set the device clock on boot. Just add a comma separated list of SIDS and Passwords for the Wi-Fi network credentials you want your device to be able to connect to in the array variables defined in the secrets.py file.

The device has a touch screen but the UI is not using it at this stage of the code development.

The code will be published in the repo https://github.com/Footleg/geiger-counter/ so check for updates there. You can also access the source code directly on the device and extend and enhance the code yourself. This is a fully hackable project!

The Micropython firmware with LVGL graphics library was built from the repo at https://github.com/de-dh/ESP32-Cheap-Yellow-Display-Micropython-LVGL/
Be aware that different variants of the CYD boards use different display driver chips, so you will need to build the firmware with the correct settings for your particular hardware if you want to update the MicroPython firmware. The code to set up the display is also specific to the display driver on the board, so make sure you use the version that matches the one on your board if you update with newer code from github.
