import time
import ctypes
import numpy as np
from arena_api.system import system
from arena_api.buffer import *
from multiprocessing import Queue, Process
import cv2
import traceback
'''
Acquiring and Saving Images on Seperate Threads: Introduction
	Saving images can sometimes create a bottleneck in the image acquisition
	pipeline. By sperating saving onto a separate thread, this bottle neck can be
	avoided. This example is programmed as a simple producer-consumer problem.
'''


def create_device_with_tries():
	'''
	This function waits for the user to connect a device before raising
		an exception
	'''+
	tries = 0
	tries_max = 6
	sleep_time_secs = 10
	while tries < tries_max:  # Wait for device for 60 seconds
		devices = system.create_device()
		if not devices:
			print(
				f'Try {tries+1} of {tries_max}: waiting for {sleep_time_secs} '
				f'secs for a device to be connected!')
			for sec_count in range(sleep_time_secs):
				time.sleep(1)
				print(f'{sec_count + 1 } seconds passed ',
					'.' * sec_count, end='\r')
			tries += 1
		else:
			print(f'Created {len(devices)} device(s)\n')
			return devices
	else:
		raise Exception(f'No device found! Please connect a device and run '
						f'the example again.')


def setup(device):
    """
    Setup stream dimensions and stream nodemap
        num_channels changes based on the PixelFormat
        Mono 8 would has 1 channel, RGB8 has 3 channels

    """
    nodemap = device.nodemap
    nodes = nodemap.get_node(['Width', 'Height', 'PixelFormat'])

    nodes['Width'].value = 1280
    nodes['Height'].value = 720
    nodes['PixelFormat'].value = 'BGR8'

    num_channels = 3

    # Stream nodemap
    tl_stream_nodemap = device.tl_stream_nodemap

    tl_stream_nodemap["StreamBufferHandlingMode"].value = "NewestOnly"
    tl_stream_nodemap['StreamAutoNegotiatePacketSize'].value = True
    tl_stream_nodemap['StreamPacketResendEnable'].value = True

    return num_channels

def process_frame(image):
	processed_frame = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
	return processed_frame

def get_multiple_images(queue):
	devices = create_device_with_tries()  
	device = devices[0]
	num_channels = setup(device)
	try:
		with device.start_stream():
			while True:
				buffer = device.get_buffer()

				item = BufferFactory.copy(buffer)
				device.requeue_buffer(buffer)

				buffer_bytes_per_pixel = int(len(item.data)/(item.width * item.height))
				
				array = (ctypes.c_ubyte * num_channels * item.width * item.height).from_address(ctypes.addressof(item.pbytes))
				
				npndarray = np.ndarray(buffer=array, dtype=np.uint8, shape=(item.height, item.width, buffer_bytes_per_pixel))
				# npndarray = process_frame(npndarray)
				# cv2.imshow('Lucid', npndarray)
				queue.put(npndarray.copy())
				BufferFactory.destroy(item)
				
				# добавляем кадр в очередь
				# 
				# key = cv2.waitKey(1)
				# if key == 27:
				# 	break
	except:
		traceback.print_exc()	
	# device.stop_stream()
	# system.destroy_device()

	print(f'Stream stopped')



def save_image_buffers(queue, i):
	
	while True:
		if not queue.empty():
			image = queue.get()
			processed_frame = process_frame(image)
			cv2.imwrite(f'images/{i}_{int(time.time() * 1000)}.png', processed_frame)
		# 	cv2.imshow('Processed Frame', processed_frame)
		# if cv2.waitKey(1) & 0xFF == ord('q'):
		# 	break


def example_entry_point():
	queue = Queue()
	# get_multiple_images(queue)
	
	putting_process = Process(
		target=get_multiple_images,
	 	args=(queue, )
	)
	putting_process.start()

	for i in range(2):
		putting_process = Process(
			target=save_image_buffers,
			args=(queue, i,)
		)
		putting_process.start()

	# ERROR: ctypes objects containing pointers cannot be pickled
	while True:
		frame = queue.get()
		print(type(frame))
		cv2.imshow('frame', frame)
		cv2.waitKey(1)
	putting_process.join()
	



if __name__ == '__main__':
	print('\nWARNING:\nTHIS EXAMPLE MIGHT CHANGE THE DEVICE(S) SETTINGS!')
	print('\nExample started\n')
	example_entry_point()
	print('\nExample finished successfully')