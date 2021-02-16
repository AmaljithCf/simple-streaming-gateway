import json
import copy
import threading
import array
import struct
import time
import csv
import os

try:
    from sources.buffers import CircularBufferQueue, CircularResultsBufferQueue
except:
    from buffers import CircularBufferQueue, CircularResultsBufferQueue
SHORT = 2


class BaseReader(object):
    """ Base Reader Object, describes the methods that must be implemented for each data source"""

    def __init__(self, config, device_id=None, **kwargs):
        self.samples_per_packet = config["CONFIG_SAMPLES_PER_PACKET"]
        self.sample_rate = config["CONFIG_SAMPLE_RATE"]
        self.config_columns = config.get("CONFIG_COLUMNS")

        self.class_map = config.get("CLASS_MAP", None)
        self.device_id = device_id
        self.source_samples_per_packet = config.get("SOURCE_SAMPLES_PER_PACKET")
        self.recording = False

        self.streaming = False

        self._thread = None
        self._record_thread = None
        self._lock = threading.Lock()

        self.buffer = CircularBufferQueue(
            self._lock, buffer_size=self.packet_buffer_size
        )
        self.rbuffer = CircularResultsBufferQueue(self._lock, buffer_size=1)

    def __delete__(self):
        print("Deleting DataSource")
        self.disconnect()
        self.streaming = False
        self.recording = False
        self._thread = None
        self._record_thread = None

    @property
    def data_width(self):
        return len(self.config_columns)

    @property
    def packet_buffer_size(self):
        return self.samples_per_packet * self.source_buffer_size

    @property
    def source_buffer_size(self):
        return self.source_samples_per_packet * self.data_width * SHORT

    def is_recording(self):
        return self.recording

    def is_streaming(self):
        return self.streaming

    def _validate_config(self, config):

        if not isinstance(config, dict):
            raise Exception("Invalid Configuration")

        if config.get("column_location", None) is None:
            raise Exception("Invalid Configuration: no column_location")
        if config.get("sample_rate", None) is None:
            raise Exception("Invalid Configuration: no sample_rate")
        if config.get("samples_per_packet", None) is None:
            raise Exception("Invalid Configuration: no samples_per_packet")

        return config

    def _validate_results_data(self, data):
        try:
            tmp = json.loads(data)
            if isinstance(tmp, dict) and tmp:
                return True
        except Exception as e:
            print(e)

        return False

    def _map_classification(self, results):

        if self.class_map:
            results["Classification"] = self.class_map.get(
                results["Classification"], results["Classification"]
            )

        return results

    def send_connect(self):

        if self._thread is None:
            "Assume if there is a thread, we are already connected"

            self.send_subscribe()

            time.sleep(1)

            self.buffer.reset_buffer()

            self._thread = threading.Thread(target=self._read_source)
            self._thread.start()

            time.sleep(1)

        else:
            print("Thread Already Started!")

    def disconnect(self):
        self.streaming = False
        self._thread = None
        self._record_thread = None
        self.recording = False

        self.buffer.reset_buffer()
        self.rbuffer.reset_buffer()

    def record_start(self, filename):

        if not self.streaming:
            raise Exception("Must start streaming before begging to record!")

        if self.recording:
            raise Exception("Only a single recording can occur at one time")

        self.recording = True
        self._record_thread = threading.Thread(
            target=self._record_data, kwargs={"filename": filename}
        )
        self._record_thread.start()

    def record_stop(self, filename=None):
        if self.recording != True:
            raise Exception("Not currently recording")

        self._record_thread = None
        self.recording = False

        return True

    def _record_data(self, filename):

        print("recording data to {}".format(filename))

        if filename is None:
            raise Exception("Invalid Filename")

        index = self.buffer.get_latest_buffer()

        if not os.path.exists(os.path.dirname(filename)):
            print(
                "File directory does not exist,  recording to data directory in gateway location."
            )
            if not os.path.exists("./data"):
                os.mkdir("./data")

            filename = os.path.join("./data", os.path.basename(filename))

        with open(filename + ".csv", "w", newline="") as csvfile:
            datawriter = csv.writer(csvfile, delimiter=",")

            datawriter.writerow(self.config_columns)
            struct_info = "h" * self.data_width
            while self.recording:

                if index is None:
                    index = self.buffer.get_latest_buffer()
                    time.sleep(0.1)
                    continue

                if self.buffer.is_buffer_full(index):
                    data = self.buffer.read_buffer(index)
                    index = self.buffer.get_next_index(index)

                    if data:
                        for row_index in range(len(data) // (self.data_width * 2)):
                            buff_index = row_index * self.data_width * 2
                            datawriter.writerow(
                                struct.unpack(
                                    struct_info,
                                    data[buff_index : buff_index + self.data_width * 2],
                                )
                            )

                else:
                    time.sleep(0.001)

        print("recording thread finished")

    def read_config(self):
        pass

    def list_available_devices(self):
        return []

    def _read_source(self):
        pass

    def set_config(self, config):
        pass

    def send_subscribe(self):
        pass


class BaseStreamReaderMixin(object):
    def read_data(self):

        print("starting read")

        if self._thread:
            pass
        else:
            print("sent connect")
            self.send_connect()
            self.streaming = True

        index = self.buffer.get_latest_buffer()

        while self.streaming:

            if index is None:
                index = self.buffer.get_latest_buffer()
                time.sleep(0.1)
                continue

            if self.buffer.is_buffer_full(index):
                data = self.buffer.read_buffer(index)
                index = self.buffer.get_next_index(index)

                if data:
                    yield data

            time.sleep(0.001)

        print("stream ended")


class BaseResultReaderMixin(object):
    def read_data(self):

        print("starting result read")

        if self._thread:
            pass
        else:
            print("sent connect")
            self.send_connect()

        index = self.buffer.get_latest_buffer()

        while self.streaming:

            if index is None:
                index = self.rbuffer.get_latest_buffer()
                time.sleep(0.1)
                continue

            if self.rbuffer.is_buffer_full(index):
                data = self.rbuffer.read_buffer(index)
                index = self.rbuffer.get_next_index(index)

                for result in data:
                    if self._validate_results_data(result):
                        result = self._map_classification(json.loads(result))
                        yield json.dumps(result) + "\n"

            else:
                time.sleep(0.1)

        print("result stream ended")
