#!/usr/bin/env python

import io
import signal
import sys
import avro
import avro.schema
import avro.io

from gps3 import gps3
from kafka import KafkaProducer
from datetime import datetime

TOPIC = "gps"
SERVER_ADDR = "vip4.ecn.purdue.edu"

if __name__ == "__main__":

    # create gpsd socket and listens for new data
    gps_socket = gps3.GPSDSocket()
    data_stream = gps3.DataStream()
    gps_socket.connect()
    gps_socket.watch()

    # create kafka producer
    producer = KafkaProducer(bootstrap_servers=SERVER_ADDR)

    # load avro schema and setup encoder
    fp = open("/opt/isoblue2/kafka_gps_log/gps.avsc").read()
    schema = avro.schema.parse(fp)
    writer = avro.io.DatumWriter(schema)
    bytes_writer = io.BytesIO()
    encoder = avro.io.BinaryEncoder(bytes_writer)

    def sigterm_handler(signal, frame):
        producer.flush()
        sys.exit(0)

    while True:
        for new_data in gps_socket:
            if new_data:
                data_stream.unpack(new_data)
                for key in data_stream.TPV:
                    # if any key value is empty, set it to None
                    # so that it fits into the avro schema
                    if data_stream.TPV[key] == 'n/a':
                        data_stream.TPV[key] = None

                if data_stream.TPV['time']:
                    # convert ISO8601 date and time to unix epoch time
                    utc_dt = datetime.strptime(data_stream.TPV['time'], \
                            '%Y-%m-%dT%H:%M:%S.%fZ')
                    data_stream.TPV['time'] = (utc_dt - datetime(1970, 1, 1)).total_seconds()

                writer.write({
                    "time":data_stream.TPV['time'],
                    "lat":data_stream.TPV["lat"],
                    "lon":data_stream.TPV["lon"],
                    "alt":data_stream.TPV["alt"],
                    "epx":data_stream.TPV["epx"],
                    "epy":data_stream.TPV["epy"],
                    "epv":data_stream.TPV["epv"],
                    "track":data_stream.TPV["track"],
                    "speed":data_stream.TPV["speed"],
                    "climb":data_stream.TPV["climb"],
                    "epd":data_stream.TPV["epd"],
                    "eps":data_stream.TPV["eps"],
                    "epc":data_stream.TPV["epc"]
                    },
                    encoder)

                bytes_msg = bytes_writer.getvalue()
                producer.send(TOPIC, bytes_msg)
                signal.signal(signal.SIGTERM, sigterm_handler)
