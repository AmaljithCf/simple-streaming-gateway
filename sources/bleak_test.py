import asyncio
from bleak import BleakScanner, BleakClient


async def scan():
    devices = await BleakScanner.discover()

    print(devices)
    return devices


def callback(sender, data):
    print(sender, data)


async def connect_to_device(address, charUUID):
    async with BleakClient(address, timeout=1.0) as client:
        print("connect to", address)
        try:
            await client.start_notify(charUUID, callback)
            await asyncio.sleep(10.0)
            await client.stop_notify(charUUID)
        except Exception as e:
            print(e)

    print("disconnect from", address)


async def read_gat(address, charUUID):
    print("Reading Gat")
    async with BleakClient(address) as client:
        x = await client.is_connected()
        print("here")
        resp = await client.read_gatt_char(charUUID)
        print(resp)


address = "E28AB79E-5D42-4E82-BCA7-55856287CD64"
uuidOfConfigChar = "16480001-0525-4ad5-b4fb-6dd83f49546b"


loop = asyncio.get_event_loop()
loop.run_until_complete(read_gat(address, uuidOfConfigChar))

loop.run_until_complete(connect_to_device(address, uuidOfConfigChar))


devices = loop.run_until_complete(scan())

