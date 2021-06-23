import paho.mqtt.client as mqtt
from sds011 import SDS011
import aqi
from threading import Thread
import json
import bme680
import time


MQTT = "192.168.1.128"

MQTT_TOPIC_CONFIG_STATE = "homeassistant/sensor/{}/availability"
MQTT_TOPIC_CONFIG       = "homeassistant/sensor/{}/{}/config"
MQTT_TOPIC_STATE        = "homeassistant/sensor/{}/state"

DEVICE = "/dev/ttyUSB0"
WORKING_PERIOD = 5


def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT with result code {str(rc)}")


def on_message(client, userdata, msg):
    print(f"{msg.topic} {str(msg.payload)}")


def run_voc(client: mqtt.Client, bme680_sensor_id: str):
    try:
        sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
    except (RuntimeError, IOError):
        sensor = bme680.BME680(bme680.I2C_ADDR_SECONDARY)

    # These oversampling settings can be tweaked to
    # change the balance between accuracy and noise in
    # the data.

    sensor.set_humidity_oversample(bme680.OS_2X)
    sensor.set_pressure_oversample(bme680.OS_4X)
    sensor.set_temperature_oversample(bme680.OS_8X)
    sensor.set_filter(bme680.FILTER_SIZE_3)
    sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)

    sensor.set_gas_heater_temperature(320)
    sensor.set_gas_heater_duration(150)
    sensor.select_gas_heater_profile(0)

    # start_time and curr_time ensure that the
    # burn_in_time (in seconds) is kept track of.

    start_time = time.time()
    curr_time = time.time()
    burn_in_time = 300

    print('Collecting gas resistance burn-in data for 5 mins')

    while curr_time - start_time < burn_in_time:
        curr_time = time.time()
        if sensor.get_sensor_data() and sensor.data.heat_stable:
            gas = sensor.data.gas_resistance
            print('Gas: {0} Ohms'.format(gas))
            time.sleep(1)

    print('Collecting actual gas data')

    count = 0
    data = 0

    while True:
        if sensor.get_sensor_data():
            if sensor.data.heat_stable:
                data += sensor.data.gas_resistance
                count += 1

                if count > 60:
                    voc = data / count
                    count = 0
                    data = 0

                    client.publish(MQTT_TOPIC_STATE.format(bme680_sensor_id), json.dumps({
                        "voc": float(voc) }))

        time.sleep(1)


def main():
    client = mqtt.Client(#client_id="",
                         #clean_session=True,
                         userdata=None,
                         # protocol=mqtt.MQTTv311,
                         transport="tcp")

    client.connect(MQTT)
    client.on_connect = on_connect
    client.on_message = on_message

    mqtt_loop = Thread(target=client.loop_forever)
    mqtt_loop.daemon = True
    mqtt_loop.start()

    sds011_sensor_id = "workplace_aqi"
    sds011_device = {
        "identifiers": [ sds011_sensor_id ],
        "manufacturer": "Nova Fitness",
        "model": "SDS011",
        "name": "Nova Fitness SDS011",
    }

    aqi_sensor_id = "workplace_aqi_calc"
    aqi_device = {
        "identifiers": [ aqi_sensor_id ],
        "manufacturer": "None",
        "model": "None",
        "name": "AQI Calculator",
    }

    bme680_sensor_id = "workplace_voc"
    bme680_device = {
        "identifiers": [ bme680_sensor_id ],
        "manufacturer": "BME680",
        "model": "Adafruit",
        "name": "Adafruit BME680",
    }

    def publish_config(device, name, value_id, unit, value_template, icon):
        device_id = device['identifiers'][0]

        config_topic = MQTT_TOPIC_CONFIG.format(device_id, value_id)
        config_state_topic = MQTT_TOPIC_CONFIG_STATE.format(device_id)
        state_topic = MQTT_TOPIC_STATE.format(device_id)

        client.publish(config_topic, json.dumps({
            "availability": [ { "topic": config_state_topic } ],
            "device": device,
            "unique_id": f"{device_id}_{value_id}",
            "icon": icon,
            "name": name,
            "value_template": value_template,
            "unit_of_measurement": unit,
            "state_topic": state_topic }),
            qos=1,
            retain=True)

        client.publish(config_state_topic, "online", qos=1, retain=True)

    publish_config(sds011_device, "Workplace PM₂.₅", "pm25", "μg/m³", "{{ value_json.pm25 }}", "mdi:gas-cylinder")
    publish_config(sds011_device, "Workplace 10₁₀ ", "pm10", "μg/m³", "{{ value_json.pm10 }}", "mdi:gas-cylinder")
    publish_config(aqi_device,    "Workplace AQI",   "aqi",  "aqi",   "{{ value_json.aqi }}",  "mdi:grass")
    publish_config(bme680_device, "Workplace VOC",   "voc",  "Ω",     "{{ value_json.voc }}",  "mdi:spa")

    voc_runner = Thread(target=run_voc, args=(client, bme680_sensor_id))
    voc_runner.daemon = True
    voc_runner.start()

    sensor = SDS011(DEVICE)
    sensor.set_working_period(rate=WORKING_PERIOD)

    print(sensor)

    while True:
        results = sensor.read_measurement()
        # results = { "pm2.5": 2, "pm10": 2 }
        pm25 = results["pm2.5"]
        pm10 = results["pm10"]

        print(results)

        aqi_value = aqi.to_aqi([
            (aqi.POLLUTANT_PM25, str(pm25)),
            (aqi.POLLUTANT_PM10, str(pm10)),
        ])

        print(f"AQI = {aqi_value}")

        client.publish(MQTT_TOPIC_STATE.format(sds011_sensor_id), json.dumps({
            "pm25": pm25,
            "pm10": pm10 }))

        client.publish(MQTT_TOPIC_STATE.format(aqi_sensor_id), json.dumps({
            "aqi": float(aqi_value) }))


if __name__ == "__main__":
    main()
