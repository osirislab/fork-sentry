set -x -o errexit

# Pull new rules
freshclam

grep -vE "^(StreamMaxLength|MaxScanSize|MaxFileSize|MaxRecursion|MaxFiles)" /etc/clamav/clamd.conf  > /etc/clamav/clamd.conf.new
cat >> /etc/clamav/clamd.conf.new << EOF
# This option allows you to specify the upper limit for data size that will be transfered to remote daemon when scanning a single file.
StreamMaxLength 521M
# Sets the maximum amount of data to be scanned for each input file.
# Archives and other containers are recursively extracted and scanned up to this value.
MaxScanSize 512M
# Files larger than this limit won't be scanned.
# Affects the input file itself as well as files contained inside it (when the input file is an archive, a document or some other kind of container).
MaxFileSize 512M
# Nested archives are scanned recursively, e.g. if a Zip archive contains a RAR file, all files within it will also be scanned.
# This options specifies how deeply the process should be continued.
MaxRecursion 16
# Number of files to be scanned within an archive, a document, or any other kind of container.
MaxFiles 10000
EOF
mv -f /etc/clamav/clamd.conf.new /etc/clamav/clamd.conf

rm /var/log/clamav/freshclam.log


# Report options to log
clamconf

# Reload Services
service clamav-daemon force-reload
service clamav-freshclam force-reload

# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app