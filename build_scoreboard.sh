#! /bin/bash

cd /home/andrew/code/picks2021/

source .venv/bin/activate

python driver.py
aws s3 mv /tmp/sb-index.html s3://picks.apawl.com/index.html

deactivate
