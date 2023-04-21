from arena_api.system import system
from arena_api.buffer import *

import ctypes
import numpy as np
import cv2
import time
from datetime import datetime, timedelta
from multiprocessing import Queue, Process
from typing import List, Any


class Camera:
    def __init__(
        
            self: 'Camera'
    ):
        self.frame_count = 0
        self.frames: List[Any] = []
        self.every_nth = 5
        self.exposure_time = 20000.0
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
    
    def process_frame(self: 'Camera', image):
        processed_frame = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return processed_frame

    def set_exposure_time(
            self: 'Camera',
            threshold,
            brightness, 
            nodes
    ):  
        if threshold - brightness > 5:
            nodes['ExposureTime'].value += 200
            print("ExposureTime:", nodes['ExposureTime'].value)
            print("Average brightness:", brightness)

        elif threshold - brightness < -5:
            nodes['ExposureTime'].value -= 200
            print("ExposureTime:", nodes['ExposureTime'].value)
            print("Average brightness:", brightness)
        
        else:
            pass 

        
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

        nodes['Width'].value = 1936
        nodes['Height'].value = 1464
        nodes['PixelFormat'].value = 'BGR8'
        # в разрешении 1280х720 - максимальное время экспозиции ~25к
        # изображение/стрим в разрешении 1936х1464 сильно лагает

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
        return nodes
    
    def configure_exposure_acquire_images(self, nodes):

        
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
    
    def get_images(self, queue):

        devices = self.create_devices_with_tries()
        device = devices[0]
        num_channels, nodemap = self.setup(device)
        nodes = self.store_initial(nodemap)
        self.configure_exposure_acquire_images(nodes)   
        with device.start_stream():
            while True:
                        
                buffer = device.get_buffer()
                        
                item = BufferFactory.copy(buffer)
                device.requeue_buffer(buffer)
                        
                buffer_bytes_per_pixel = int(len(item.data)/(item.width * item.height))
                        
                array = (ctypes.c_ubyte * num_channels * item.width * item.height).from_address(ctypes.addressof(item.pbytes))
                        
                npndarray = np.ndarray(buffer=array, dtype=np.uint8, shape=(item.height, item.width, buffer_bytes_per_pixel))
                brightness = np.average(npndarray)
                cv2.imshow('Processed Frame', npndarray)
                while abs(brightness - self.threshold) > 5:
                    cv2.putText(npndarray, str(nodes['ExposureTime'].value), (7, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (100, 255, 0), 3, cv2.LINE_AA)
                    self.set_exposure_time(self.threshold, brightness, nodes)
                    break
                        # добавляем кадр в очередь
                queue.put(npndarray.copy())
                BufferFactory.destroy(item)
                    
                key = cv2.waitKey(1)
                if key == 27:
                    print('process1_ended')
                    break
            device.stop_stream()
            cv2.destroyAllWindows()
        system.destroy_device()

    def save_image_buffers(self, queue,):        
	    while True:
		    if not queue.empty():
                        self.frame_count += 1
                        image = queue.get()
                        processed_frame = self.process_frame(image)
                        # записывается каждый n-ый кадр (здесь every_nth = 5) 
                        if self.frame_count % self.every_nth == 0:
                            cv2.imwrite(f'images/{int(time.time() * 1000)}.png', processed_frame)

    def start_camera(self):
        queue = Queue()
        
        putting_process = Process(
		    target=self.get_images,
	 	    args=(queue, )
        )
        
        putting_process.start()
        

        getting_process = Process(
            target=self.save_image_buffers,
            args=(queue, )
        )

        getting_process.start()
        
        putting_process.join()
        time.sleep(0.1)
        if not putting_process.is_alive():
            print('Putting process stopped, terminating getting p.')
            getting_process.terminate()
            print('process2_ended')


if __name__ == '__main__':
    print('\nWARNING:\nTHIS EXAMPLE MIGHT CHANGE THE DEVICE(S) SETTINGS!')
    print('\nExample started\n')
    lucid = Camera()
    lucid.start_camera()
    print('\nExample finished successfully')  

        # putting_process.join()
        # devices = self.create_devices_with_tries()
        # device = devices[0]
        # num_channels = self.setup(device)

        # nodes, initial_vals = self.store_initial(nodemap)

        # self.configure_exposure_acquire_images(device, nodes, initial_vals)
        # self.get_images(queue)

        # with device.start_stream():

        #     while True:

        #         buffer = device.get_buffer()

        #         item = BufferFactory.copy(buffer)
        #         device.requeue_buffer(buffer)

        #         buffer_bytes_per_pixel = int(len(item.data)/(item.width * item.height))

        #         array = (ctypes.c_ubyte * num_channels * item.width * item.height).from_address(ctypes.addressof(item.pbytes))

        #         npndarray = np.ndarray(buffer=array, dtype=np.uint8, shape=(item.height, item.width, buffer_bytes_per_pixel))
        #         brightness = np.average(npndarray)

        #         # предполагается что в момент включения - камера смотрит на серую карту и 
        #         # запускается метод выставления оптимального времени экспозиции
        #         # для более точной настройки регулируется баланс серого 

        #         while abs(brightness - threshold) > 5:
        #             cv2.putText(npndarray, str(nodes['ExposureTime'].value), (7, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (100, 255, 0), 3, cv2.LINE_AA)
        #             self.set_exposure_time(threshold, brightness, nodes)
        #             break
        #         while (abs(brightness - threshold) < 5):
        #             if brightness > threshold:
        #                 npndarray -= 1
        #                 brightness = np.average(npndarray)
        #                 print('Изменено средняя яркость', brightness)
        #             elif brightness < threshold:
        #                 npndarray += 1
        #                 brightness = np.average(npndarray)
        #                 print('Изменено средняя яркость', brightness)
        #             cv2.putText(npndarray, 'The optimal exposure value is set', (7, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (100, 255, 0), 3, cv2.LINE_AA)

        #             break
                
                

        #         cv2.imshow('Lucid', npndarray)

        #         BufferFactory.destroy(item)

        #         key = cv2.waitKey(1)
        #         if key == 27:
        #             break
        #         print(brightness)
        #     device.stop_stream()
        #     cv2.destroyAllWindows()
        
        # system.destroy_device()


        
    