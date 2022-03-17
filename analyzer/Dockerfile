FROM python:3.9

# Allow statements and log messages to immediately appear in the Cloud Run logs
ENV PYTHONUNBUFFERED True

# Install analysis dependencies
RUN apt-get update && \
    apt-get install -y \
        git libgit2-dev clamav-daemon clamav-freshclam clamav-unofficial-sigs \
        ssdeep libfuzzy-dev && \
    freshclam && \
    echo "TCPSocket 3310" >> /etc/clamav/clamd.conf && \
    echo "TCPAddr 127.0.0.1" >> /etc/clamav/clamd.conf

RUN wget https://github.com/mandiant/capa/releases/download/v3.2.0/capa-v3.2.0-linux.zip && \
    unzip capa-v3.2.0-linux.zip 

# Reload services
RUN service clamav-daemon force-reload
RUN service clamav-freshclam force-reload

# Install analyzer dependencies
COPY requirements.txt ./
RUN pip3 install -r requirements.txt

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
CMD ["sh", "bootstrap.sh"]