#!/usr/bin/env python3
"""Execute to start the server in testing mode"""

import os
import site
import time
site.addsitedir(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import klipper_cura_connection

module = klipper_cura_connection.load_config(None)
module.handle_ready()
while True:
    try:
        time.sleep(0.1)
    except KeyboardInterrupt:
        module.stop()
        break
