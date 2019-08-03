import os
import sys
import subprocess
import string
import random

bashfile=''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
bashfile='/tmp/'+bashfile+'.sh'

f = open(bashfile, 'w')
s = """export APP_NAME="main.py"
export WORKSPACE=`pwd`
# Create/Activate virtualenv
virtualenv -p /usr/bin/python3 venv
source "$WORKSPACE/venv/bin/activate"
# Install Requirements
pip3 install -r requirements.txt
"""
f.write(s)
f.close()
os.chmod(bashfile, 0o755)
bashcmd=bashfile
for arg in sys.argv[1:]:
  bashcmd += ' '+arg
subprocess.call(bashcmd, shell=True)
