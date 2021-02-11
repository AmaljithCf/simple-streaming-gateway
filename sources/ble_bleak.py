import asyncio
from bleak import BleakScanner
import struct
import sys
import json
import copy
from sources.base import BaseReader
import time


uuidOfConfigChar = "16480001-0525-4ad5-b4fb-6dd83f49546b"
uuidOfDataChar = "16480002-0525-4ad5-b4fb-6dd83f49546b"
RecognitionClassUUID = "42421101-5A22-46DD-90F7-7AF26F723159"


async def runScanner():

    devices = await BleakScanner.discover()

    return devices


def handleNotificationCallback(sender: int, data: bytearray):
    print(f"{sender}: {data}")


client.start_notify(char_uuid, callback)


class BLEReader(BaseReader):
    """ Base Reader Object, describes the methods that must be implemented for each data source"""

    def __init__(self, config, device_id, connect=True, **kwargs):

        self.new_data = False
        self.data = []
        self.streaming = False
        self.subscribed = False
        self.device_id = device_id
        self.peripheral = None

        if self.device_id and connect:
            self.peripheral = None

        super(BLEReader, self).__init__(config, **kwargs)

    def disconnect(self):
        self.streaming = False
        self.subscribed = True

        if self.peripheral:
            self.peripheral.disconnect()

    def list_available_devices(self):

        loop = asyncio.get_event_loop()
        loop.run_until_complete(runScanner())

        device_list = []

        for index, dev in enumerate(devices):
            device_list.append(
                {"id": index, "device_id": dev.address, "name": dev.name}
            )

        return device_list

    def send_connect(self):

        if not self.subscribed:
            setup_data = b"\x01\x00"
            notify_handle = (
                self.peripheral.getCharacteristics(uuid=uuidOfDataChar)[0].getHandle()
                + 1
            )
            self.peripheral.writeCharacteristic(
                notify_handle, setup_data, withResponse=True
            )
            self.subscribed = True

    def read_config(self):

        if self.peripheral is None:
            raise Exception("BLE Device ID Not Configured.")

        source_config = self.peripheral.getCharacteristics(uuid=uuidOfConfigChar)[
            0
        ].read()

        return self._validate_config(
            json.loads(source_config.decode("ascii").rstrip("\x00"))
        )

    def read_data(self):

        self.send_connect()
        time.sleep(1)

        self.streaming = True

        while self.streaming:
            try:
                if self.peripheral.waitForNotifications(0.01):
                    continue
                if self.delegate.new_data:
                    tmp = copy.deepcopy(self.delegate.data)
                    if len(tmp) >= self.packet_buffer_size:
                        self.delegate.new_data = False
                        self.delegate.data = self.delegate.data[
                            self.packet_buffer_size :
                        ]

                        yield tmp[: self.packet_buffer_size]
            except:
                self.streaming = False

    def set_config(self, config):

        source_config = self.read_config()

        if not source_config:
            raise Exception("Invalid Source Configuration")

        self.data_width = len(source_config["column_location"])

        config["CONFIG_COLUMNS"] = source_config["column_location"]
        config["CONFIG_SAMPLE_RATE"] = source_config["sample_rate"]
        config["DATA_SOURCE"] = "BLE"
        config["BLE_DEVICE_ID"] = self.device_id


class BLEResultReader(BLEReader):
    """ Base Reader Object, describes the methods that must be implemented for each data source"""

    def __init__(self, config, device_id, connect=True, **kwargs):

        self.delegate = ResultDelegate(None)
        self.new_data = False
        self.data = []
        self.streaming = False
        self.subscribed = False
        self.device_id = device_id

        if self.device_id and connect:
            self.peripheral = btle.Peripheral(self.device_id)
            self.peripheral.setDelegate(self.delegate)

        super(BLEReader, self).__init__(config, **kwargs)

    def set_config(self, config):
        config["DATA_SOURCE"] = "BLE"
        config["BLE_DEVICE_ID"] = self.device_id

    def send_connect(self):

        print("sending connect")
        if not self.subscribed:
            print("subscring")
            setup_data = b"\x01\x00"
            notify_handle = (
                self.peripheral.getCharacteristics(uuid=RecognitionClassUUID)[
                    0
                ].getHandle()
                + 1
            )
            self.peripheral.writeCharacteristic(
                notify_handle, setup_data, withResponse=True
            )
            self.subscribed = True
            print("subscribed")

    def read_data(self):

        self.send_connect()
        time.sleep(1)

        self.streaming = True

        while self.streaming:
            if self.peripheral.waitForNotifications(0.1):
                continue
            if self.delegate.new_data:
                tmp = struct.unpack("h" * 2, self.delegate.data)
                self.delegate.new_data = False
                self.delegate.data = ""
                print(json.dumps({"model": tmp[0], "classification": tmp[1]}))
                yield json.dumps({"model": tmp[0], "classification": tmp[1]}) + "\n"


if __name__ == "__main__":

    config = {"CONFIG_COLUMNS": [], "CONFIG_SAMPLE_RATE": [], "DATA_SOURCE": "BLE"}

    ble = BLEReader({})
    ble.set_config(config)
    ble.send_connect()

    for i in ble.read_data():
        print(i)
