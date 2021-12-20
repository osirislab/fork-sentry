FROM python:3.9

# Allow statements and log messages to immediately appear in the Cloud Run logs
ENV PYTHONUNBUFFERED True

# Install clamav
RUN apt-get update && \
    apt-get install -y \
        git libgit2-dev clamav-daemon clamav-freshclam clamav-unofficial-sigs \
        ssdeep && \
    freshclam && \
    echo "TCPSocket 3310" >> /etc/clamav/clamd.conf && \
    echo "TCPAddr 127.0.0.1" >> /etc/clamav/clamd.conf

# Install dependencies
COPY requirements.txt ./
RUN pip3 install -r requirements.txt

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# get updates, reload services and boot server
CMD ["sh", "bootstrap.sh"]
