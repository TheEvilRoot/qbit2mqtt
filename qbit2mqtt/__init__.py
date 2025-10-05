import datetime
import json
import logging
import os
import sys
import time

import paho.mqtt.client as mqtt
import qbittorrent
import urllib3

from qbit2mqtt.discovery import DiscoveryConfig


def from_env(key: str, default: str) -> str:
    val = os.environ.get(key, '')
    if val is None or len(val) == 0:
        return default
    return val

def int_from_env(key: str, default: int) -> int:
    val = from_env(key, '')
    if val is None or len(val) == 0:
        return default
    try:
        return int(val)
    except ValueError:
        raise Exception(f'Environment variable {key} has invalid valid: {val}, expected int')


QBIT_NAME = from_env('QBIT2MQTT_NAME', 'qbit2mqtt')
MONITOR_INTERVAL = int_from_env('QBIT2MQTT_INTERVAL', 5)
DISCOVERY_INTERVAL = int_from_env('QBIT2MQTT_DISCOVERY_INTERVAL', 30)

QBIT_URL = from_env('QBIT2MQTT_QBIT_URL', 'http://127.0.0.1:8080/')
QBIT_USER = from_env('QBIT2MQTT_QBIT_USER', 'admin')
QBIT_PASSWORD = from_env('QBIT2MQTT_QBIT_PASSWORD', '')

MQTT_HOST = from_env('QBIT2MQTT_MQTT_HOST', 'localhost')
MQTT_PORT = int_from_env('QBIT2MQTT_MQTT_PORT', 1883)
MQTT_USER = from_env('QBIT2MQTT_MQTT_USER', '')
MQTT_PASSWORD = from_env('QBIT2MQTT_MQTT_PASSWORD', '')

def create_mqtt_client():
    def on_connect(*args, **kwargs):
        logging.info('Connected to MQTT broker')

    def on_connect_fail(*args, **kwargs):
        logging.info('Connection failed to MQTT broker')

    def on_disconnect(*args, **kwargs):
        logging.info(f'Disconnected from MQTT broker: {args} {kwargs}')

    def on_login(*args, **kwargs):
        logging.info('Connected to MQTT broker')

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if len(MQTT_USER) > 0:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_login = on_login
    client.on_connect = on_connect
    client.on_connect_fail = on_connect_fail
    client.on_disconnect = on_disconnect
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()
    return client

def create_discovery_config(qbit: qbittorrent.Client):
    discovery_config = DiscoveryConfig(QBIT_NAME, 'qbit2mqtt')
    discovery_config.device(QBIT_NAME, qbit.api_version, f'qbittorrent_{qbit.api_version}')
    discovery_config.origin('qbit2mqtt', '1.0', 'https://github.com/theevilroot/qbit2mqtt')

    discovery_config.switch('Alternative Speed', sensor_id='alternative_speed')
    discovery_config.sensor(name='Total downloaded',
                            device_class='data_size',
                            unit_of_measurement='GB',
                            value_template='{{ value | round(2) }}',
                            precision=2,
                            state_class='measurement',
                            sensor_id='total_downloaded')
    discovery_config.sensor(name='Total uploaded',
                            device_class='data_size',
                            unit_of_measurement='GB',
                            value_template='{{ value | round(2) }}',
                            precision=2,
                            state_class='measurement',
                            sensor_id='total_uploaded')
    discovery_config.sensor(name='Download speed',
                            device_class='data_rate',
                            unit_of_measurement='Mbit/s',
                            value_template='{{ value | round(2) }}',
                            precision=2,
                            state_class='measurement',
                            sensor_id='download_speed')
    discovery_config.sensor(name='Upload speed',
                            device_class='data_rate',
                            unit_of_measurement='Mbit/s',
                            value_template='{{ value | round(2) }}',
                            precision=2,
                            state_class='measurement',
                            sensor_id='upload_speed')
    discovery_config.sensor(name='Download limit',
                            device_class='data_rate',
                            unit_of_measurement='Mbit/s',
                            value_template='{{ value | round(2) }}',
                            precision=2,
                            state_class='measurement',
                            sensor_id='download_limit')
    discovery_config.sensor(name='Upload limit',
                            device_class='data_rate',
                            unit_of_measurement='Mbit/s',
                            value_template='{{ value | round(2) }}',
                            precision=2,
                            state_class='measurement',
                            sensor_id='upload_limit')
    discovery_config.sensor(name='DHT nodes',
                            device_class=None,
                            unit_of_measurement='nodes',
                            value_template='{{ value }}',
                            precision=0,
                            state_class='measurement',
                            sensor_id='dht_nodes')
    discovery_config.sensor(name='Total torrents',
                            device_class=None,
                            unit_of_measurement='torrents',
                            value_template='{{ value }}',
                            precision=0,
                            state_class='measurement',
                            sensor_id='total_torrents')
    discovery_config.sensor(name='Active torrents',
                            device_class=None,
                            unit_of_measurement='torrents',
                            value_template='{{ value }}',
                            precision=0,
                            state_class='measurement',
                            sensor_id='active_torrents')
    discovery_config.sensor(name='Global ratio',
                            device_class=None,
                            unit_of_measurement='',
                            value_template='{{ value }}',
                            precision=2,
                            state_class='measurement',
                            sensor_id='global_ratio')
    return discovery_config

def monitor(qbit: qbittorrent.Client, client: mqtt.Client, discovery_config: DiscoveryConfig):
    def send_message(topic: str, message):
        if topic is not None:
            if isinstance(message, dict):
                message = json.dumps(message)
            if isinstance(message, float):
                message = f'{message:.2f}'
            if not isinstance(message, str):
                message = str(message)
            logging.debug(f'{topic} <- {message}')
            client.publish(topic, message)

    def on_message(c: mqtt.Client, x, message: mqtt.MQTTMessage):
        sensor = discovery_config.sensor_for_command_topic(message.topic)
        if sensor == 'alternative_speed':
            state = message.payload.decode()
            current_state = qbit.alternative_speed_status
            if current_state == 1 and state == 'off':
                qbit.toggle_alternative_speed()
            elif current_state == 0 and state == 'on':
                qbit.toggle_alternative_speed()
            new_state = qbit.alternative_speed_status
            logging.info(f'trigger alternative speed {current_state} -> {state} -> {new_state}')
            send_message(discovery_config.state_topic_of('alternative_speed'), 'on' if new_state == 1 else 'off')


    client.on_message = on_message
    client.subscribe(discovery_config.command_topic_of('alternative_speed'))

    send_message(discovery_config.topic, discovery_config.build())
    discovery_date = datetime.datetime.now()
    while True:
        if datetime.datetime.now() - discovery_date > datetime.timedelta(seconds=DISCOVERY_INTERVAL):
            send_message(discovery_config.topic, discovery_config.build())
            discovery_date = datetime.datetime.now()
            logging.info('Discovery message published')
        info = qbit.sync_main_data()
        srv_state = info['server_state']
        alternative_state = qbit.alternative_speed_status
        torrents = info['torrents'].values()
        total_torrents = len(torrents)
        active_torrents = len([torrent for torrent in torrents if torrent['state'] in ['downloading', 'uploading']])
        send_message(discovery_config.state_topic_of('dht_nodes'), srv_state.get('dht_nodes', 0))
        send_message(discovery_config.state_topic_of('upload_limit'), srv_state.get('up_rate_limit', 0) * 8 / 1024 / 1024)
        send_message(discovery_config.state_topic_of('download_limit'), srv_state.get('dl_rate_limit', 0) * 8 / 1024 / 1024)
        send_message(discovery_config.state_topic_of('upload_speed'), srv_state.get('up_info_speed', 0) * 8 / 1024 / 1024)
        send_message(discovery_config.state_topic_of('download_speed'), srv_state.get('dl_info_speed', 0) * 8 / 1024 / 1024)
        send_message(discovery_config.state_topic_of('total_uploaded'), srv_state.get('alltime_ul', 0) / 1024 / 1024 / 1024)
        send_message(discovery_config.state_topic_of('total_downloaded'), srv_state.get('alltime_dl', 0) / 1024 / 1024 / 1024)
        send_message(discovery_config.state_topic_of('alternative_speed'), 'on' if alternative_state == 1 else 'off')
        send_message(discovery_config.state_topic_of('total_torrents'), total_torrents)
        send_message(discovery_config.state_topic_of('active_torrents'), active_torrents)
        send_message(discovery_config.state_topic_of('global_ratio'), srv_state.get('global_ratio', 0))

        time.sleep(MONITOR_INTERVAL)

def main():
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s', stream=sys.stdout)

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    qbit = qbittorrent.Client(QBIT_URL, verify=False, timeout=2)
    qbit.login(QBIT_USER, QBIT_PASSWORD)
    client = create_mqtt_client()
    discovery_config = create_discovery_config(qbit)
    monitor(qbit, client, discovery_config)

if __name__ == '__main__':
    main()