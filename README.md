# PLC Module

This is an interface class for the Insteon PowerLinc Controller (v2, USB). The implementation consists of commincating with the SALad App via the IBOIS HID USB interface and transacting with Insteon devices (direct command sending and network event processing). The example webserver code is designed to be compatible with the `homebridge-http-dimmer` module from `https://www.npmjs.com/package/homebridge-http-dimmer`. This project is not associated with `homebridge-http-dimmer`, the `homebridge` project, or Insteon.

The PLC is documented here: `http://cache.insteon.com/pdf/INSTEON_Developers_Guide_20070816a.pdf`

## Purpose

This code was written as a weekend project to connect some LampLinc dimmers with Homekit (which really means connect the dimmers to an http server, the http-to-homekit part was pre-existing). I had an old PowerLinc v2 USB 2414U as an interface and decided to try to revive it. The tech was around 10 years old at the time of this writing, so there are some alternative implementations, but the spec is fairly simple and is well documented.

## License

See LICENSE (CC0)

## Installation

I recommend you run this from the checkout directory (see usage). In that case, `pip install -r requirements.txt` first.

## Usage (Example)

From this directory run `PASSWORD=guessme python3 ./webserver.py`

In the homebridge configuration, add the following for each dimmer (replace 0a1b2c with the 3-byte Insteon address and the provide the password if you set one):
```
    "accessories": [
        {
            "accessory": "HTTP-DIMMER",
            "name":"Lamp Name",
            "onUrl": "http://localhost:5000/dimmer/0a1b2c/set?pass=guessme&level=100",
            "offUrl": "http://localhost:5000/dimmer/0a1b2c/set?pass=guessme&level=0",
            "statusUrl": "http://localhost:5000/dimmer/0a1b2c/status?pass=guessme",
            "setBrightnessUrl": "http://localhost:5000/dimmer/0a1b2c/set?pass=guessme&level=",
            "getBrightnessUrl": "http://localhost:5000/dimmer/0a1b2c/get?pass=guessme",
        },
```
