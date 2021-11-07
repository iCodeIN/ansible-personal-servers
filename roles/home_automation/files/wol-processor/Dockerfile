FROM python:3

RUN useradd -ms /bin/bash app \
      && mkdir -p /usr/src/app \
      && chown -R app /usr/src/app

USER app

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "./main.py" ]
