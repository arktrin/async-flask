#!/usr/bin/env python

from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit
from multiprocessing import Process, Array
import numpy as np
import ctypes as c 
import sys, random, os, timeit, struct, spidev, smbus
import RPi.GPIO as GPIO


# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = None # gevent only works actually

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None

n, m = 2, 7
mp_arr = Array(c.c_double, n*m)
arr = np.frombuffer(mp_arr.get_obj())
main_data = arr.reshape((n,m))

# main_data = [(T0+T1)/2, T0, T1, T_ambient, T_to_stab, T_error, DAC_value]

i2c_bus_list = [smbus.SMBus(3), smbus.SMBus(4)] # , smbus.SMBus(5)
temp_addrs = [0x48, 0x49, 0x4A] # , 0x4B]

# set 16-bit mode in all ADT7420
for bus in i2c_bus_list:
	for addr in temp_addrs:
		bus.write_byte_data(addr, 0x03, 0x80)

dac_spi = spidev.SpiDev(0, 1)
dac_spi.mode = 2
GPIO.setmode(GPIO.BOARD)
DAC_nCS = [29, 31, 32] #, 33
for nCS in DAC_nCS:
	GPIO.setup(nCS, GPIO.OUT)
i = 0
default_stab_temps = [28.0, 28.0, 28.0]
default_dac_vals = [6500, 6500, 6500]

for i in xrange(n):
	main_data[i,4] = default_stab_temps[i] 
	main_data[i,6] = default_dac_vals[i]

def read_all_temp():
	Ts = np.zeros((n, 4))
	for k in xrange(12):
		for i in xrange(len(i2c_bus_list)):
			for j in xrange(len(temp_addrs)):
				T_raw = i2c_bus_list[i].read_i2c_block_data(temp_addrs[j], 0, 2)
				Ts[i,j+1] += ((T_raw[0]<<8) + T_raw[1])/1536.0
			Ts[i,0] = (Ts[i,1] + Ts[i,2])/2.0
		socketio.sleep(0.25)
	return Ts

def write_dac(value, nCS_pin):
	value = int(value)
	if value > 65535:
		value = 65535
	elif value < 0:
		value = 0
	GPIO.output(nCS_pin, 0)  # select AD5683 
	value = value << 4
	packet = list(struct.unpack('4B', struct.pack('>I', value)))
	packet.pop(0)
	packet[0] += 48
	dac_spi.xfer2(packet)
	GPIO.output(nCS_pin, 1)  # deselect AD5683
	
# list_of_csv = os.listdir('static')

def data_logger(main_data):
	global i, n
	while True:
	# this loop is spawed twice if in debug mode
	# tic = timeit.default_timer()
		main_data[:,:4] = read_all_temp()
		for j in xrange(n):
			main_data[j,5] = main_data[j,4] - main_data[j,0]
			if i % 4 == 0:
				if main_data[j,5] > 0:
					main_data[j,6] += 1 + int(round(10*main_data[j,5], 0))
				elif main_data[j,5] < 0:
					main_data[j,6] -= 1 - int(round(10*main_data[j,5], 0))
				write_dac(main_data[j,6], DAC_nCS[j])
		# print main_data, '\n'	
		i += 1
	# print timeit.default_timer() - tic

def background_thread():
	global main_data
	count = 0
	while True:
		socketio.sleep(3)
		count += 1
		socketio.emit('my_response', {'data': main_data.tolist(), 'count': count}, namespace='/test')

@app.route('/')
def index():
	return render_template('index.html', async_mode=socketio.async_mode) #, list_of_csv=list_of_csv, schedule_list=schedule_list)

@socketio.on('my_event', namespace='/test')
def test_message(message):
	global main_data
	# print message['data']
	if message['data'][0][:4] == 'temp':
		chamber_num = int(message['data'][0][4])
		main_data[chamber_num,4] = float(message['data'][1])
	elif message['data'][0][:3] == 'dac':
		chamber_num = int(message['data'][0][3])
		main_data[chamber_num,6] = float(message['data'][1])
	session['receive_count'] = session.get('receive_count', 0) + 1
	# emit('my_response',{'data': message['data'], 'count': session['receive_count']})

@socketio.on('my_ping', namespace='/test')
def ping_pong():
	emit('my_pong')

@socketio.on('connect', namespace='/test')
def test_connect():
	global thread
	if thread is None:
		thread = socketio.start_background_task(target=background_thread)
	emit('my_response', {'data': 'Connected!', 'count': 0})

@socketio.on('disconnect', namespace='/test')
def test_disconnect():
	print('Client disconnected', request.sid)

if __name__ == '__main__':
	process0 = Process( target=data_logger, args=(main_data,) )
	process0.start()
	# process0.join()
	# socketio.run(app, host="192.168.199.14", port=80) #, debug=True)
	socketio.run(app, host="192.168.2.123", port=80) #, debug=True)
