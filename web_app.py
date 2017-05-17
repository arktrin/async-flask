#!/usr/bin/env python

from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit
from multiprocessing import Process, Value
import random, os, timeit

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = None # gevent only works actually

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None

list_of_csv = os.listdir('static')

val = Value('f', 0)

def scheduled_data_logger(val):
	while True:
		# this loop is spawed twice if in debug mode
		# tic = timeit.default_timer()
		val.value = random.random()
		print val.value
		socketio.sleep(1)
		# print timeit.default_timer() - tic
		# for row in schedule_list:
		#	print row[2]


def background_thread():
	global val
	count = 0
	while True:
		socketio.sleep(1)
		count += 1
		socketio.emit('my_response',
					  {'data': 100*val.value, 'count': count},
					  namespace='/test')

@app.route('/')
def index():
	return render_template('index.html', async_mode=socketio.async_mode, list_of_csv=list_of_csv) # , schedule_list=schedule_list)

@socketio.on('my_event', namespace='/test')
def test_message(message):
	# if len(message['data']) == 3:
	#	for i in xrange(len(schedule_list)):
	#		if schedule_list[i][0] ==  message['data'][0]:
	#			schedule_list[i] = [message['data'][0], message['data'][1], message['data'][2]]
	#			with open('static/schedule.txt', 'w') as f:
	#				for row in schedule_list:
	#					f.write(row[0]+','+row[1]+','+row[2]+'\n')
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
	process0 = Process( target=scheduled_data_logger, args=(val,) )
	process0.start()
	# process0.join()
	socketio.run(app, host="localhost", #  "192.168.199.14"
					  port=80) #, debug=True)
