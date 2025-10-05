from typing import Optional


def sanitize_name(name: str):
    return name.lower().replace('-', '_').replace(' ', '_').replace('.', '_')

class DiscoveryConfig:
    def __init__(self, device_id: str, base_topic: str):
        self.device_id = sanitize_name(device_id)
        self.base_topic = base_topic
        self.topic =  f'homeassistant/device/{self.device_id}/config'
        self.origin_config = None
        self.device_config = None
        self.components = {}

    def build(self) -> dict:
        assert self.device_config is not None
        assert self.origin_config is not None
        return {
            'dev': self.device_config,
            'o': self.origin_config,
            'cmps': self.components
        }

    def state_topic_of(self, sensor_id: str) -> Optional[str]:
        component = self.components.get(sensor_id)
        if component is None:
            return None
        return component.get('state_topic', None)

    def command_topic_of(self, sensor_id: str) -> Optional[str]:
        component = self.components.get(sensor_id)
        if component is None:
            return None
        return component.get('command_topic', None)

    def sensor_for_command_topic(self, command_topic: str) -> Optional[str]:
        for sensor_id, sensor in self.components.items():
            if sensor.get('command_topic') == command_topic:
                return sensor_id
        return None

    def switch(self, name: str, sensor_id: str = None, state_topic: str = None, cmd_topic: str = None, unique_id: str = None):
        if sensor_id is None:
            sensor_id = sanitize_name(name)
        if state_topic is None:
            state_topic = f'{self.base_topic}/{self.device_id}/{sensor_id}/state'
        if cmd_topic is None:
            cmd_topic = f'{self.base_topic}/{self.device_id}/{sensor_id}/set'
        if unique_id is None:
            unique_id = f'{self.device_id}_{sensor_id}'
        self.components[sensor_id] = {
            'name': name,
            'platform': 'switch',
            'payload_on': 'on',
            'payload_off': 'off',
            'state_on': 'on',
            'state_off': 'off',
            'state_topic': state_topic,
            'command_topic': cmd_topic,
            'unique_id': unique_id
        }
        return self

    def sensor(self, name: str, device_class: Optional[str], unit_of_measurement: str, value_template: str, sensor_id: str = None, precision: int = 1, state_topic: str = None, unique_id = None, state_class: str = 'measurement'):
        if sensor_id is None:
            sensor_id = sanitize_name(name)
        if unique_id is None:
            unique_id = f'{self.device_id}_{sensor_id}'
        if state_topic is None:
            state_topic = f'{self.base_topic}/{self.device_id}/{sensor_id}'
        self.components[sensor_id] = {
            'name': name,
            'platform': 'sensor',
            'state_class': state_class,
            'device_class': device_class,
            'state_topic': state_topic,
            'suggested_display_precision': precision,
            'unit_of_measurement': unit_of_measurement,
            'value_template': value_template,
            'unique_id': unique_id,
        }
        return self

    def origin(self, name: str, version: str, url: str):
        self.origin_config = {
            'name': name,
            'sw': version,
            'url': url
        }
        return self

    def device(self, name: str, model: str, model_id: str):
        self.device_config = {
            'name': name,
            'model': model,
            'model_id': model_id,
            'identifiers': [sanitize_name(self.device_id)]
        }
        return self