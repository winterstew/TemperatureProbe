import board
import adafruit_tca9548a

i2c=board.I2C()
tca = adafruit_tca9548a.TCA9548A(i2c)
addresses = []
if i2c.try_lock():
	addresses = i2c.scan()
	i2c.unlock()

for addr in addresses:
	print("I2C address found:", hex(addr))
	if addr >= 0x70:
		print (" Multiplex found:")
		for channel in range(8):
			maddresses=[]
			if tca[channel].try_lock():
				print("  channel {}:".format(channel), end="")
				maddresses = tca[channel].scan()
				print("  I2C address found:",[hex(maddr) for maddr in maddresses if maddr != 0x70])
				tca[channel].unlock()

i2c.deinit()
