#!/usr/bin/python3
#
# Webserver for the PLC Dimmer class

import hid
import os
import logging
from flask import Flask, request, abort
from plc import PLC, Dimmer

logger = logging.getLogger(__name__)
app = Flask(__name__)


PASSWORD = os.getenv('PASSWORD')
VID = 0x10bf
PID = 0x0004


@app.route('/dimmer/<address>/<cmd>')
def dimmer(address, cmd):
    password = request.args.get('pass')
    level = request.args.get('level', None)
    if password != PASSWORD:
        abort(403)
    d = Dimmer(p, address)
    try:
        if cmd == 'set':
            rv = d.set_level(round(255*int(level)/100.))
        elif cmd == 'get':
            rv = round(100*d.get_level()/255.)
        elif cmd == 'status':
            if d.get_level() == 0:
                rv = 0
            else:
                rv = 1
        return f"{rv}"
    except TimeoutError as e:
        logger.exception(f"{e}")
        abort(504)
    abort(404)


h = hid.Device(VID, PID)
logger.info(f'Device manufacturer: {h.manufacturer}')
logger.info(f'Product: {h.product}')
p = PLC(h)
if not PASSWORD:
    logger.warning("No password is set.")

if __name__ == '__main__':
    app.run()
