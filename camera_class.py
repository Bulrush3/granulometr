from arena_api.system import system
from arena_api.buffer import *

import ctypes
import numpy as np
import cv2
import time
from datetime import datetime, timedelta
from typing import List, Any


class Camera:
    def __init__(
        
            self: 'Camera'
    ):
        self.frame_count = 0
        self.frames: List[Any] = []
        self.every_nth = 20
        self.exposure_time = 500.0
        self.threshold = 127
        # self.queue_frame

    def get_current_frame(
            self: 'Camera'
    ):
        current_time = datetime.now() + timedelta(seconds=0.1)
        while True:
            while len(self.frames) == 0:
                time.sleep(0.01)
            frame = self.frames.pop(0)
            if current_time < datetime.now():
                while len(self.frames) == 0:
                    time.sleep(0.01)
                frame = self.frames.pop(0)
                return frame

    def set_exposure_time(
            self: 'Camera',
            threshold,
            brightness, 
            nodes
    ):  
        if brightness < threshold:
            nodes['ExposureTime'].value += 8
            print("ExposureTime:", nodes['ExposureTime'].value)
            print("Average brightness:", brightness)
            time.sleep(0.1)

        elif brightness > threshold:
            nodes['ExposureTime'].value -= 8
            print("ExposureTime:", nodes['ExposureTime'].value)
            print("Average brightness:", brightness)
            time.sleep(0.1)
        
    def create_devices_with_tries(self:  'Camera'):
        '''
        This function waits for the user to connect a device before raising
            an exception
        '''

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
                print(f'Created {len(devices)} device(s)')
                return devices
        else:
            raise Exception(f'No device found! Please connect a device and run '
                            f'the example again.')
        
    def setup(self, device):

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

        return num_channels, nodemap
    
    def store_initial(self, nodemap):

        nodes = nodemap.get_node(['ExposureAuto', 'ExposureTime'])

        exposure_auto_initial = nodes['ExposureAuto'].value
        exposure_time_initial = nodes['ExposureTime'].value
        return nodes, [exposure_auto_initial, exposure_time_initial]
    
    def configure_exposure_acquire_images(self, device, nodes, initial_vals):

        
        print("Disable automatic exposure")
        nodes['ExposureAuto'].value = 'Off'
        
        print("Get exposure time node")
        if nodes['ExposureTime'] is None:
             raise Exception("Exposure Time node not found")
        
        if nodes['ExposureTime'].is_writable is False:
            raise Exception("Exposure Time node not writeable")
        
        
        if self.exposure_time > nodes['ExposureTime'].max:
            nodes['ExposureTime'].value = nodes['ExposureTime'].max
        elif self.exposure_time < nodes['ExposureTime'].min:
            nodes['ExposureTime'].value = nodes['ExposureTime'].min
        else:
            nodes['ExposureTime'].value = self.exposure_time

        current_expo_time = self.exposure_time
            
        print(f"Set expsoure time to {nodes['ExposureTime'].value}")
    

    def start_camera(self):

        devices = self.create_devices_with_tries()
        device = devices[0]

        # Setup
        num_channels, nodemap = self.setup(device)

        nodes, initial_vals = self.store_initial(nodemap)

        self.configure_exposure_acquire_images(device, nodes, initial_vals)
        
        threshold = 127.0

        with device.start_stream():
            """
            Infinitely fetch and display buffer data until esc is pressed
            """
            while True:
                # Used to display FPS on stream
                # curr_frame_time = time.time()

                buffer = device.get_buffer()

                item = BufferFactory.copy(buffer)
                device.requeue_buffer(buffer)

                buffer_bytes_per_pixel = int(len(item.data)/(item.width * item.height))

                array = (ctypes.c_ubyte * num_channels * item.width * item.height).from_address(ctypes.addressof(item.pbytes))

                npndarray = np.ndarray(buffer=array, dtype=np.uint8, shape=(item.height, item.width, buffer_bytes_per_pixel))

                brightness = np.average(npndarray)

                # предполагается что в момент включения - камера смотрит на серую карту и 
                # запускается метод выставления оптимального времени экспозиции
                # для более точной настройки регулируется баланс серого 

                while abs(brightness - threshold) > 5:
                    self.set_exposure_time(threshold, brightness, nodes)
                    break
                while (abs(brightness - threshold) < 5) and (abs(brightness - threshold) > 2.5):
                    if brightness > threshold:
                        npndarray -= 1
                        print('Изменено средняя яркость', brightness)
                    elif brightness < threshold:
                        npndarray += 1
                        print('Изменено средняя яркость', brightness)
                    break
                
                # if 10 < len(self.frames):
                #     self.frames.pop(0)
                #     print(self.frames)

                # self.frames.append(npndarray)
                
                # frame_count += 1
                # if frame_count % every_nth == 0: 
                #     cv2.imwrite(f"images\image{frame_count}.jpeg", npndarray)
                # npndarray = cv2.cvtColor(npndarray, cv2.COLOR_BGR2GRAY)

                cv2.imshow('Lucid', npndarray)
                # print(np.average(npndarray))
                # print(npndarray[0, 0])
                BufferFactory.destroy(item)
                # prev_frame_time = curr_frame_time
                """
                Break if esc key is pressed
                """
                key = cv2.waitKey(1)
                if key == 27:
                    break
                print(brightness)
            device.stop_stream()
            cv2.destroyAllWindows()
        
        system.destroy_device()

        

        

print('\nWARNING:\nTHIS EXAMPLE MIGHT CHANGE THE DEVICE(S) SETTINGS!')
print('\nExample started\n')
lucid = Camera()
lucid.start_camera()
print('\nExample finished successfully')      