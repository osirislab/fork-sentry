FROM python:3.9

# Get clamav daemon
RUN apt-get update &&
    apt-get install clamav-daemon clamav-freshclam clamav-unofficial-sigs -y && \
    freshclam && \
    echo "TCPSocket 3310" >> /etc/clamav/clamd.conf && \
    echo "TCPAddr 127.0.0.1" >> /etc/clamav/clamd.conf

# Run daemon in background
RUN service clamav-daemon force-reload \
    service clamav-freshclam force-reload

# Allow statements and log messages to immediately appear in the Cloud Run logs
ENV PYTHONUNBUFFERED True

# Install dependencies
COPY requirements.txt ./
RUN pip3 install -r requirements.txt

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app