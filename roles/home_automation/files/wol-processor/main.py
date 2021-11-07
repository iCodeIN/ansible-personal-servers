import json
import random
from paho.mqtt import client as mqtt_client
from wakeonlan import send_magic_packet


broker = '192.168.1.128'
port = 1883
topic = "wol"
client_id = f'python-mqtt-{random.randint(0, 1000)}'


if __name__ == "__main__":
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    # Set Connecting Client ID
    client = mqtt_client.Client(client_id)
    client.on_connect = on_connect
    client.connect(broker, port)

    def on_message(client, userdata, msg):
        payload = msg.payload.decode()
        topic = msg.topic

        print(f"Received `{payload}` from `{topic}` topic")

        data = json.loads(payload)

        send_magic_packet(data['mac'],
                          interface=data['interface'])

    client.subscribe(topic)
    client.on_message = on_message

    client.loop_forever()
