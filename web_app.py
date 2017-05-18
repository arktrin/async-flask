#!/usr/bin/env python

from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit
from multiprocessing import Process, Value, Array
import numpy as np 
import sys, random, os, timeit, struct, math, spidev, smbus
import RPi.GPIO as GPIO

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = None # gevent only works actually

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None

bus3 = smbus.SMBus(3)
addrs = [0x48, 0x4A, 0x4B, 0x49]
n = len(addrs)
# temp_addr0 = 0x48
# temp_addr3 = 0x49
# temp_addr1 = 0x4A
# temp_addr2 = 0x4B

for i in xrange(n):
	bus3.write_byte_data(addrs[i], 0x03, 0x80)

def read_temp(bus):
	Ts = n*[0]
	for i in xrange(4):
		for i in xrange(n):
			T_raw = bus.read_i2c_block_data(addrs[i], 0, 2)
			Ts[i] += ((T_raw[0]<<8) + T_raw[1])/512.0
		socketio.sleep(0.25)
	return Ts
	
list_of_csv = os.listdir('static')

temps = Array( 'f', range(n) )

def data_logger(temps):
	while True:
	# this loop is spawed twice if in debug mode
	# tic = timeit.default_timer()
		temps[0:4] = read_temp(bus3)
		print temps[:]
		# socketio.sleep(0.25)
	# print timeit.default_timer() - tic

def background_thread():
	global temps
	count = 0
	while True:
		socketio.sleep(1)
		count += 1
		socketio.emit('my_response',
			  {'data': temps[:], 'count': count},
			  namespace='/test')

@app.route('/')
def index():
	return render_template('index.html', async_mode=socketio.async_mode, list_of_csv=list_of_csv) # , schedule_list=schedule_list)

@socketio.on('my_event', namespace='/test')
def test_message(message):
	# if len(message['data']) == 3:
	#	for i in xrange(len(schedule_list)):
	#	if schedule_list[i][0] ==  message['data'][0]:
	#		schedule_list[i] = [message['data'][0], message['data'][1], message['data'][2]]
	#		with open('static/schedule.txt', 'w') as f:
	#		for row in schedule_list:
	#			f.write(row[0]+','+row[1]+','+row[2]+'\n')
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
	process0 = Process( target=data_logger, args=(temps,) )
	process0.start()
	# process0.join()
	socketio.run(app, host="192.168.2.123", port=80) #, debug=True)
