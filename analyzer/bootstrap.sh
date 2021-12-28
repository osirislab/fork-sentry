# Log commands, and exit on error.
set -x -o errexit

# Reload Services
freshclam
service clamav-daemon force-reload
service clamav-freshclam force-reload

# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app