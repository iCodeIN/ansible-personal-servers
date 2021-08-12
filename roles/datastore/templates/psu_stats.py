#!/usr/bin/env python3

import sys
import subprocess
from dataclasses import dataclass, field
from typing import Dict
import requests
import time


units = ['rpm', 'volts', 'watts', 'amps']


@dataclass
class Model:
  name: str = ''
  vendor: str = ''
  product: str = ''
  powered: int = 0
  uptime: int = 0
  temp1: float = 0.0
  temp2: float = 0.0
  fan: float = 0.0
  supply: float = 0.0
  total: float = 0.0
  output0: Dict[str, float] = field(default_factory=dict)
  output1: Dict[str, float] = field(default_factory=dict)
  output2: Dict[str, float] = field(default_factory=dict)


def send(line: str) -> None:
  headers = {
    'Content-Type': 'application/octet-stream'
  }

  requests.post('http://localhost:8186/write',
                data=line.encode('utf-8'), headers=headers)


def run(binary: str) -> None:
  result = subprocess.run(binary, stdout=subprocess.PIPE)
  stats = result.stdout.decode('utf-8')

  model = Model()

  for stat in stats.splitlines():
    parts = stat.split(':')

    key = parts[0].strip()
    value = parts[1].strip().replace('\'', '')

    if key == 'powered' or key == 'uptime':
      value = value.split(' ')[0]

    try:
      value = float(value)
    except:
      pass

    if any(x in key for x in units):
      parts = key.split(' ')

      key = parts[0].strip()
      unit_str = parts[1].strip()

      if "output" in key:
        outputs = getattr(model, key)
        outputs[unit_str] = value
      else:
        setattr(model, key, value)
    else:
      setattr(model, key, value)

  tags = f"component=psu,name={model.name},vendor={model.vendor},product={model.product}"

  send(f"system,{tags} powered={int(model.powered)}i,uptime={int(model.uptime)}i,temp1={model.temp1},temp2={model.temp2}")
  send(f"system,{tags},unit=rpm fan={model.fan}")
  send(f"system,{tags},unit=amps output0={model.output1['amps']},output1={model.output1['amps']},output2={model.output2['amps']}")
  send(f"system,{tags},unit=volts supply={model.supply},output0={model.output1['volts']},output1={model.output1['volts']},output2={model.output2['volts']}")
  send(f"system,{tags},unit=watts total={model.total},output0={model.output1['watts']},output1={model.output1['watts']},output2={model.output2['watts']}")


def main():
  binary = sys.argv[1]
  intervalSeconds = sys.argv[2]

  while True:
    run(binary)
    time.sleep(int(intervalSeconds))


if __name__ == "__main__":
  main()
