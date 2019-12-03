#!/usr/bin/python3

import time
import struct
import threading
import queue
import logging
from base64 import b16decode


logger = logging.getLogger(__name__)


class PLC:
    def __init__(self, hid):
        self.hid = hid
        self.running = True
        self.cts = True
        self.sendq = queue.Queue()
        self.read_thread = threading.Thread(target=self.read_fn)
        self.read_thread.daemon = True
        self.write_thread = threading.Thread(target=self.write_fn)
        self.write_thread.daemon = True
        self.usb_timeout = 100
        self.message_filters = []  # callback functions to recv msg data
        self.filter_lock = threading.Lock()
        self.read_thread.start()
        self.write_thread.start()

    def register_filter(self, cb_func):
        with self.filter_lock:
            self.message_filters.append(cb_func)

    def unregister_filter(self, cb_func):
        with self.filter_lock:
            self.message_filters.remove(cb_func)

    def read_fn(self):
        msg_buffer = b''
        while self.running:
            data = self.hid.read(8, self.usb_timeout)
            if len(data) == 0:
                self.cts = True
                continue
            dlen = data[0]
            self.cts = (dlen & 0x80) == 0x80
            mlen = dlen & 0x1f
            msg_buffer += data[1:mlen+1]
            try:
                msg_buffer = self.process_ibios(msg_buffer)
            except Exception as e:
                logger.error(f"Error processing buffer: {self.message}")
                logger.exception(f"Exception: {e}")
                msg_buffer = b''

    def process_ibios(self, msg_buffer):
        if len(msg_buffer) < 2:
            return msg_buffer
        if msg_buffer[0] != 0x02 or msg_buffer[1] & 0xF0 != 0x40:
            logger.error("Lost sync. Discarding message buffer.")
            return b''
        rv = msg_buffer  # default return entire message
        msg_len = 0
        msg_type = msg_buffer[1] & 0x0F
        if msg_type == 0 and len(msg_buffer) >= 7:
            msg_len = 7
        elif msg_type == 1 and len(msg_buffer) >= 3:
            msg_len = msg_buffer[2] + 3
        elif msg_type == 2 and len(msg_buffer) >= 9:
            msg_len = struct.unpack('>H', msg_buffer[4:6])[0] + 9
        elif msg_type == 3 and msg_buffer.find(b'\x03'):
            msg_len = msg_buffer.find(b'\x03')+1
        elif msg_type == 4 and len(msg_buffer) >= 9:
            msg_len = 9
        elif msg_type == 5 and len(msg_buffer) >= 3:
            msg_len = 3
        elif msg_type == 6 and len(msg_buffer) >= 7:
            msg_len = 7
        elif msg_type == 7 and len(msg_buffer) >= 5:
            msg_len = 5
        elif msg_type == 8 and len(msg_buffer) >= 9:
            msg_len = 9
        elif msg_type == 9 and len(msg_buffer) >= 4:
            msg_len = 4
        elif msg_type == 0xA and len(msg_buffer) >= 4:
            msg_len = 4
        elif msg_type == 0xF and len(msg_buffer) >= 3:
            if msg_buffer[2] == 5:  # NAK (\x04 for ACK)
                msg_len = 3
            elif len(msg_buffer) >= 12:
                ext_flag = msg_buffer[9] & 0x10
                if ext_flag and len(msg_buffer) >= 26:
                    msg_len = 26
                elif not ext_flag:
                    msg_len = 12
        elif (msg_type == 0xB or msg_type == 0xC or
              msg_type == 0xD or msg_type == 0xE):
            logger.error("Unknown message. Discarding buffer.")
            # undocumented type of unknown length, discard all
            return b''

        if msg_len and len(msg_buffer) >= msg_len:
            message = msg_buffer[:msg_len]
            rv = msg_buffer[msg_len:]
            with self.filter_lock:
                for mf in self.message_filters:
                    # message filters may modify the message
                    message = mf(message)
                    if not message:
                        break
        return rv

    def write_fn(self):
        while self.running:
            data = self.sendq.get()
            while len(data) > 0:
                out = data[:7]
                data = data[7:]
                out = bytes([len(out)])+out
                if len(out) < 7:
                    out = out + b'\x00'*(7-len(out))
                while self.cts is not True:
                    time.sleep(self.usb_timeout/1000.)
                self.cts = False
                self.hid.write(out)

    def write_mem(self, loc, val):
        cmd = b'\x02\x40'
        header = struct.pack('>HH', loc, len(val))
        checksum = struct.pack('>h', -sum([x for x in header+val]))
        message = cmd+header+checksum+val
        self.sendq.put(message)


class ICommand:
    def __init__(self, plc, address):
        self.plc = plc
        self.address = address
        if type(self.address) == str:
            self.address = b16decode(address.upper())
        self.timeout = 5  # seconds
        self.recvq = queue.Queue()

    def plc_filter_recv(self, msg):
        # Called in the recv thread, of the plc, so queue the message data
        # for consumption by the _recv_reply processor
        self.recvq.put(msg)
        return msg  # don't change the contents for other listeners

    def _send_raw(self, cmd):
        self.plc.write_mem(0x01a4, cmd)  # ibios flat memory map
        self.plc.sendq.put(b'\x02\x46\x01\x42\x10\xff')  # mask transmit RTS

    def _recv_ack(self):
        started = time.time()
        remaining = self.timeout
        while remaining >= 0:
            try:
                msg = self.recvq.get(timeout=remaining)
                if msg[0:3] == b'\x02\x4f\x04' and msg[3:6] == self.address:
                    # message, insteaon message, event type ack
                    return msg[3:]  # return Insteon portion only
            except queue.Empty:
                pass
            remaining = self.timeout - (time.time() - started)
        raise TimeoutError('The device did not ack prior to timeout.')

    def send(self, cmd1, cmd2=b'\x00', extra=b'',
             flag=b'\x0f'):
        # flag default: 000 (direct) 0 (9-byte) 11 (3 hops) 11 (3 max)
        try:
            self.plc.register_filter(self.plc_filter_recv)
            self._send_raw(self.address + flag + cmd1 + cmd2 + extra)
            reply = self._recv_ack()
        finally:
            self.plc.unregister_filter(self.plc_filter_recv)
        return reply


class Dimmer(ICommand):
    def set_level(self, level):
        result = self.send(b'\x11', bytes([level]))
        if result:
            return int(result[-1])

    def get_level(self):
        result = self.send(b'\x19')
        if result:
            return int(result[-1])
