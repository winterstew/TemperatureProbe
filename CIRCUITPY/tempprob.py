# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""
Initializes the sensor, gets and prints readings every two seconds.
"""
import time
import board
import adafruit_si7021
import adafruit_tca9548a
import adafruit_sht4x
import adafruit_hdc302x
import os
import ssl
import time
import socketpool
import wifi
import supervisor

import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_io.adafruit_io import IO_MQTT

debug = 1

# Add settings.toml to your filesystem CIRCUITPY_WIFI_SSID and CIRCUITPY_WIFI_PASSWORD keys
# with your WiFi credentials. DO NOT share that file or commit it into Git or other
# source control.

# Set your Adafruit IO Username, Key and Port in settings.toml
# (visit io.adafruit.com if you need to create an account,
# or if you need your Adafruit IO key.)
aio_username = os.getenv("ADAFRUIT_AIO_USERNAME")
aio_key = os.getenv("ADAFRUIT_AIO_KEY")

while (not wifi.radio.connected):
    print(f"Connecting to {os.getenv('CIRCUITPY_WIFI_SSID')}")
    wifi.radio.connect(os.getenv("CIRCUITPY_WIFI_SSID"),
                   os.getenv("CIRCUITPY_WIFI_PASSWORD"))

print(f"Connected as {wifi.radio.addresses[0]}")

# Create library object using our Bus I2C port
i2c = board.I2C()  # uses board.SCL and board.SDA	i2c.unlock()
# need to have a multiplex to use multiple sensors with the same address
tca = adafruit_tca9548a.TCA9548A(i2c)

sensors = []

def getsensor(myi2c, myaddr):
    mysensor = None
    try:
        mysensor = adafruit_sht4x.SHT4x(myi2c, myaddr)
        mysensor.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION
        myserial = mysensor.serial_number
        if debug > 0: print(f"Found SHT4x with serial number {myserial} at {hex(myaddr)}")
    except:
        try:
            mysensor = adafruit_hdc302x.HDC302x(myi2c, myaddr)
            myauto = mysensor.auto_mode
            mysensor.heater = mysensor.HEATER_POWERS['OFF']
            myserial = mysensor.manufacturer_id
            if debug > 0: print(f"Found HDC302x with serial number {myserial} at {hex(myaddr)}")
        except:
            try:
                mysensor = adafruit_si7021.SI7021(myi2c, myaddr)
                #mysensor.heater_level = 0; # can be 0 (3.09mA) to 15 (94.2mA)
                mysensor.heater_enable = False
                myserial = mysensor.serial_number
                if debug > 0: print(f"Found SI7021 with serial number {myserial} at {hex(myaddr)}")
            except:
                if debug > 0: print("No Sensors Found!")
    return mysensor

addresses = []
if i2c.try_lock():
    addresses = i2c.scan()
    i2c.unlock()

# Find all the termperature/humidity sensors
for addr in addresses:
    if debug > 0: print("I2C address found:", hex(addr))
    if addr >= 0x70:
        if debug > 0: print(" Multiplex found:")
        for channel in range(8):
            maddresses = []
            if tca[channel].try_lock():
                if debug > 0: print("  channel {}:".format(channel), end="")
                maddresses = tca[channel].scan()
                tca[channel].unlock()
            for maddr in maddresses:
                if maddr < 0x70:
                    if debug > 0: print("  I2C address found:", hex(maddr))
                    try:
                        sensors.append(getsensor(tca[channel], maddr))
                    except:
                        pass
    else:
        try:
            sensors.append(getsensor(i2c, addr))
        except:
            pass

dir(sensors)

# i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller
sensor = adafruit_si7021.SI7021(i2c)

# If you'd like to use the heater, you can uncomment the code below
# and pick a heater level that works for your purposes
#
# sensor.heater_enable = True
# sensor.heater_level = 0  # Use any level from 0 to 15 inclusive

### Feeds ###
temperature_feed = 'temperature-probe.temperature'
humidity_feed = 'temperature-probe.humidity'

### Code ###

# Define callback functions which will be called when certain events happen.
# pylint: disable=unused-argument
def connected(client):
    # Connected function will be called when the client is connected to Adafruit IO.
    # This is a good place to subscribe to feed changes.  The client parameter
    # passed to this function is the Adafruit IO MQTT client so you can make
    # calls against it easily.
    #if debug > 1: print("                           Listening for {onoff_feed} changes...")
    # Subscribe to changes on a feed named DemoFeed.
    #client.subscribe(onoff_feed)
    pass

def subscribe(client, userdata, topic, granted_qos):
    # This method is called when the client subscribes to a new feed.
    if debug > 1: print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))

def unsubscribe(client, userdata, topic, pid):
    # This method is called when the client unsubscribes from a feed.
    if debug > 1: print("Unsubscribed from {0} with PID {1}".format(topic, pid))

# pylint: disable=unused-argument
def disconnected(client):
    # Disconnected function will be called when the client disconnects.
    if debug > 1: print("Disconnected from Adafruit IO!")

# pylint: disable=unused-argument
def publish(client, userdata, topic, pid):
    """This method is called when the client publishes data to a feed."""
    if debug > 0:
        print(f"Published to {topic} with PID {pid}")
        if userdata is not None:
            print("Published User data: ", end="")
            print(userdata)

# pylint: disable=unused-argument
def message(client, feed_id, payload):
    # Message function will be called when a subscribed feed has a new value.
    # The feed_id parameter identifies the feed, and the payload parameter has
    # the new value.
    if debug > 0: print("Feed {0} received new value: {1}".format(feed_id, payload))

# Create a socket pool
pool = socketpool.SocketPool(wifi.radio)
ssl_context = ssl.create_default_context()

# If you need to use certificate/key pair authentication (e.g. X.509), you can load them in the
# ssl context by uncommenting the lines below and adding the following keys to your settings.toml:
# "device_cert_path" - Path to the Device Certificate
# "device_key_path" - Path to the RSA Private Key
# ssl_context.load_cert_chain(
#     certfile=os.getenv("device_cert_path"), keyfile=os.getenv("device_key_path")
# )

# Set up a MiniMQTT Client
mqtt_client = MQTT.MQTT(
    broker="io.adafruit.com",
    port=1883,
    username=aio_username,
    password=aio_key,
    socket_pool=pool,
    ssl_context=ssl_context,
)

# Initialize an Adafruit IO MQTT Client
io = IO_MQTT(mqtt_client)

# Setup the callback methods above
io.on_connect = connected
io.on_disconnect = disconnected
io.on_subscribe = subscribe
io.on_unsubscribe = unsubscribe
io.on_message = message
io.on_publish = publish

# Connect the client to the MQTT broker.
print("Connecting to Adafruit IO...")
io.connect()

publish_rate = 60000
lastpublish = 0
measure_rate = 2000
lastmeasure = 0
temperature = 0
humidity = 0

#io.publish(onoff_feed, "Off")

while True:
    if (supervisor.ticks_ms() - lastmeasure >= measure_rate):
        temperature = sensor.temperature
        humidity = sensor.relative_humidity

        # Poll the message queue
        io.loop(timeout=1)

        if debug > 0: print("\nTemperature: %0.1f C" % temperature)
        if debug > 0: print("Humidity: %0.1f %%" % humidity)

        lastmeasure = supervisor.ticks_ms()

    if (supervisor.ticks_ms() - lastpublish >= publish_rate):
        io.publish(temperature_feed, temperature)
        io.publish(humidity_feed, humidity)

        lastpublish = supervisor.ticks_ms()