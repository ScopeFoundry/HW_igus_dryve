"""
Edward Barnard
2022-09-12
esbarnard@lbl.gov
"""

import socket
import time
import struct
import threading


class IgusDryveD1(object):
    
    def __init__(self, ip_address, port=502, initialize=True, debug=False):
        self.debug=debug 
        self.ip_address=ip_address 
        self.port=port
        
        self.lock = threading.Lock()
        
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error:
            print ('failed to create socket')         
        self.s.connect((self.ip_address, self.port))
        if self.debug==True:
            print ('Socket created')

        if initialize:
            self.initialize()

        # self.read_mode()
        # self.write_mode_and_wait(6)
        # self.read_mode()
        #self.run_home_and_wait(speed=1000, acc=10000, timeout=20)
        #time.sleep(0.5)
        #self.go_abs_pos_and_wait(pos=10000, speed=1000, acc=10000, timeout=10)
        return
    
    def close(self):
        self.s.close()
        del self.s

    def initialize(self):
        self.write_status_reset()
        # Make sure enable switch is on
        assert self.read_status()['rm'] == 1

        # clear Faults and halt motion
        self.write_controlword(so=0, ev=0, qs=0, eo=0, oms=0, fr=1, h=1)
        
        self.write_and_wait_shutdown(timeout=1)
        self.write_and_wait_switch_on()
        self.write_and_wait_operation_enable()
        
        # print(self.read_status())
        # print("homing method:", self.ask(write=False, sdo_obj=0x6098, sub_index=0, datatype='B'))
        # print("Feed_constant_Feed:", self.ask(write=False, sdo_obj=0x6092, sub_index=1, datatype='I'))
        # print("write Feed_constant_Feed:", self.ask(write=True, sdo_obj=0x6092, sub_index=1, datatype='I', data=6000))
        # print("Feed_constant_Feed:", self.ask(write=False, sdo_obj=0x6092, sub_index=1, datatype='I'))
        # print("Feed_constant_Shaft_revolutions:", self.ask(write=False, sdo_obj=0x6092, sub_index=2, datatype='I'))
        # print("write Feed_constant_Shaft_revolutions:", self.ask(write=True, sdo_obj=0x6092, sub_index=2, datatype='I', data=1))
        # print("Feed_constant_Shaft_revolutions:", self.ask(write=False, sdo_obj=0x6092, sub_index=2, datatype='I'))


    def ask_telegram(self, telegram):
        with self.lock:
            self.s.send(telegram)
            resp = self.s.recv(24)
        if self.debug:
            print(f"ask -->{telegram.hex()}")
            print(f"    <--{resp.hex()}")
        return resp
    
    
    def ask(self, write=False, sdo_obj=0x6041, sub_index=0, datatype='H', data=None ):
        
        """datatype follows python struct naming conventions:
        
        B unsigned char (1 byte) --> python int
        H unsigned short (2 byte) --> python int
        I unsigned int (4 byte) --> python int
        """
        
        
        byte_count = {'H':2, 'B': 1, 'I': 4, 'i':4}[datatype]
        
        if data is not None:
            data_bytes = struct.pack(f'<{datatype}', data) # little endian (<)
            data_len = len(data_bytes)
        else:
            data_bytes = bytearray([])
            data_len = 0

        sdo_obj_MSB = sdo_obj >> 8
        sdo_obj_LSB = sdo_obj & 0x00FF
        
        telegram = bytearray([
            0,0, # 0,1 # transaction identifier (leave at zero for a single controller on the bus
            0,0, # 2,3 # Protocol Identifier (0,0) = Modbus
            0,data_len+13, # 4,5 # Length of rest of telegram 
            0, # 6 # Unit Identifier (not used)
            0x2B, # Function Code Modbus TCPO Gateway (CANopen) = 0x2B (43)
            0x0D, # MEI type
            (0,1)[bool(write)], 0, # Protocol option fields / Protocol control Read = 0, Write=1
            0, # Node Id
            sdo_obj_MSB, sdo_obj_LSB, # SDO Object (ex statusword=0x6041, controlword=0x6042)
            sub_index, # SDO Objects Sub Index
            0, 0, # Starting address (Don't user)
            0, # SDO object ( Don't use)
            byte_count, # 1-4 Byte count detail depending the SDO object in byte 12 and 13. 
            ])
        telegram =  telegram + data_bytes

        resp = self.ask_telegram(telegram)
        
        assert resp[0:3] == telegram[0:3] # id and a protocol should match
        
        if resp[7] != telegram[7]:
            # Data Telegram Error
            print(f"Data Telegram Error {resp[7]=:02X} {telegram[7]=:02X}")
            print(f"{resp[8]=:02X}")
            
        
        resp_data = resp[19:]
        x = None
        if len(resp_data)>0:
            x = struct.unpack(f'<{datatype}', resp_data)[0]       
        return x


    def read_status(self):
        
        x = self.ask(write=False, sdo_obj=0x6041, sub_index=0,datatype='H')
        
        status = {
            'ms':  (x >>14) & 0b11, # Manufacturer Specific
            'oms': (x >>12) & 0b11, # Operating mode specific
            'ila': (x >>11) & 0b01, # Internal Limit Active
            'tr':  (x >>10) & 0b01, # Target Reached
            'rm':  (x >> 9) & 0b01, # Remote (Enable switch DI7)
            'ms8': (x >> 8) & 0b01, # Manufacturer Specific
            'w' :  (x >> 7) & 0b01, # Warning
            'sod': (x >> 6) & 0b01, # Switch on Disabled
            'qs':  (x >> 5) & 0b01, # Quick Stop
            've':  (x >> 4) & 0b01, # Voltage Enable
            'f':   (x >> 3) & 0b01, # Fault
            'oe':  (x >> 2) & 0b01, # Operation Enabled
            'so':  (x >> 1) & 0b01, # Switched On
            'rtso':(x >> 0) & 0b01, # Ready to Switch On
            }
        #print(status)
        return status
    
    def write_controlword(self, so,ev,qs, eo, oms=0, fr=0, h=0, oms9=0, r=0, ms=0):
        data_word = (
            (so  << 0) +  # Switch On
            (ev  << 1) +  # Enable Voltage
            (qs  << 2) +  # Quick Stop
            (eo  << 3) +  # Enable Operation
            (oms << 4) +  # Operating Mode Specific (3 bits)
            (fr  << 7) +  # Fault Reset
            (h   << 8) +  # Halt
            (oms9<< 9) +  # Operating Mode Specific (profile position only)
            (r   <<10) +  # Reserved
            (ms  <<11)  ) # Manufacturer Specific (5 bits)
        return self.ask(write=True, sdo_obj=0x6040, sub_index=0, datatype='H', data=data_word)    
    
    def write_status_reset(self):
        resp = self.write_controlword(so=0, ev=0, qs=0, eo=0, oms=0, fr=0, h=1, oms9=0)
        return resp
    
    def write_and_wait_shutdown(self, timeout=1.0):
        self.write_controlword(so=0, ev=1, qs=1, eo=0)
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            status = self.read_status()
            print(status)
            # Make sure switch on disabled off
            # wait until Ready to Switch On
            if status['rtso'] and (not status['sod']): 
                print("shutdown success")
                return
        raise IOError("timeout occurred in write_and_wait_shutdown")
    
    def write_and_wait_switch_on(self, timeout=1.0):
        self.write_controlword(so=1, ev=1, qs=1, eo=0)
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            status = self.read_status()
            # Make sure switch on disabled off
            # wait until Ready to Switch On
            if status['so']: 
                print("switch on success")
                return
        raise IOError("timeout occurred in write_and_wait_switch_on")
    
    def write_and_wait_operation_enable(self, timeout=1.0):
        self.write_controlword(so=1, ev=1, qs=1, eo=1)
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            status = self.read_status()
            # Make sure switch on disabled off
            # wait until Ready to Switch On
            if status['oe']: 
                print("op enable success")
                return
        raise IOError("timeout occurred in write_and_wait_operation_enable")

    def read_SI_unit(self):
        # TODO Does not work with current 2020 firmware
        print(self.SI_unit_array.hex())
        x = self.ask(write=False, sdo_obj=0x60A8, sub_index=1, datatype="I")
        print("read_SI_unit", hex(x))
        


    def read_mode(self):
        # Mode of operation read 0x6061
        """
        0        No mode change / no mode assigned
        1        Profile Position mode
        2        Not implemented
        3        Profile Velocity mode
        4        Not implemented
        5        reserved
        6        homing mode
        7        Not implemented
        8        Cyclic Synchronous Position mode
        """
        x = self.ask(write=False, sdo_obj=0x6061, sub_index=0, datatype='B')
        #print('read_mode', hex(x))
        return x
    
    def write_mode(self, mode):
        x = self.ask(write=True, sdo_obj=0x6060, sub_index=0, datatype='B', data=mode)
        print('write_mode', mode, x)

    def write_mode_and_wait(self, mode, timeout=1.0):
        x = self.ask(write=True, sdo_obj=0x6060, sub_index=0, datatype='B', data=mode)
        t0 = time.monotonic()
        while (time.monotonic() - t0) < timeout:
            current_mode = self.read_mode()
            print(f"{current_mode=} vs {mode=}")
            if current_mode == mode:
                print("mode change success")
                return
        raise IOError("timeout occurred during write_mode_and_wait")
    
    def read_feed_constant(self):
        "Feed_constant_Feed:"
        return self.ask(write=False, sdo_obj=0x6092, sub_index=1, datatype='I')
    
    def write_feed_constant(self, fc):
        """
        Feed_constant_Feed
        rate in units / feed_revs ?
        """
        self.ask(write=True, sdo_obj=0x6092, sub_index=1, datatype='I', data=fc)
    
    def read_feed_revs(self):
        "Feed_constant_Shaft_revolutions"
        return self.ask(write=False, sdo_obj=0x6092, sub_index=2, datatype='I')

    def write_feed_revs(self, revs=1):
        "Feed_constant_Shaft_revolutions"
        self.ask(write=True, sdo_obj=0x6092, sub_index=2, datatype='I', data=revs)
        #
        # print("Feed_constant_Feed:", self.ask(write=False, sdo_obj=0x6092, sub_index=1, datatype='I'))
        # print("write Feed_constant_Feed:", self.ask(write=True, sdo_obj=0x6092, sub_index=1, datatype='I', data=6000))
        # print("Feed_constant_Feed:", self.ask(write=False, sdo_obj=0x6092, sub_index=1, datatype='I'))
        # print("Feed_constant_Shaft_revolutions:", self.ask(write=False, sdo_obj=0x6092, sub_index=2, datatype='I'))
        # print("write Feed_constant_Shaft_revolutions:", self.ask(write=True, sdo_obj=0x6092, sub_index=2, datatype='I', data=1))
        # print("Feed_constant_Shaft_revolutions:", self.ask(write=False, sdo_obj=0x6092, sub_index=2, datatype='I'))


    def read_target_position(self):
        """Target Position 607Ah"""
        resp = self.ask(write=False, sdo_obj=0x607A, sub_index=0, datatype='i')
        print("read_target_position", resp)
        return resp
    def write_target_position(self, pos):
        """Target Position 607Ah"""
        return self.ask(write=True, sdo_obj=0x607A, sub_index=0, datatype='i', data=pos)

    def read_actual_position(self):
        """Actual Position 6064h"""
        return self.ask(write=False, sdo_obj=0x6064, sub_index=0, datatype='i')
    
    
    def read_profile_velocity(self):
        # 6081h Profile Velocity
        return self.ask(write=False, sdo_obj=0x6081, sub_index=0, datatype='I')
    def write_profile_velocity(self, vel):
        # 6081h Profile Velocity
        return self.ask(write=True, sdo_obj=0x6081, sub_index=0, datatype='I', data=vel)

    def read_profile_acc(self):
        # 6083h Profile Acceleration
        return self.ask(write=False, sdo_obj=0x6083, sub_index=0, datatype='I')
    def write_profile_acc(self, acc):
        # 6083h Profile Acceleration
        return self.ask(write=True, sdo_obj=0x6083, sub_index=0, datatype='I', data=acc)

    def read_home_velocity(self):
        # 6099h_01h Search Velocity for Switch
        return self.ask(write=False, sdo_obj=0x6099, sub_index=1, datatype='I')
    def write_home_velocity(self, speed):
        # 6099h_01h Search Velocity for Switch
        return self.ask(write=True, sdo_obj=0x6099, sub_index=1, datatype='I', data=speed)

    def read_home_velocity2(self):
        # 6099h_01h Search Velocity for Switch
        return self.ask(write=False, sdo_obj=0x6099, sub_index=2, datatype='I')
    def write_home_velocity2(self, speed2):
        # 6099h_01h Search Velocity for Switch
        return self.ask(write=True, sdo_obj=0x6099, sub_index=2, datatype='I', data=speed2)

    def read_home_acc(self):
        # 609Ah Homing Acceleration
        return self.ask(write=False, sdo_obj=0x609A, sub_index=0, datatype='I')
    def write_home_acc(self, acc):
        # 609Ah Homing Acceleration
        return self.ask(write=True, sdo_obj=0x609A, sub_index=0, datatype='I', data=acc)

    def trigger_move(self):
        # Enable Operation to set bit 4 of the controlword to low again; see manual chapter "Controlword"
        self.write_controlword(so=1, ev=1, qs=1, eo=1, oms=0)
        # Send Telegram(TX) Write Controlword 6040h Command: Start Movement; rising edge of bit 4 (oms)
        self.write_controlword(so=1, ev=1, qs=1, eo=1, oms=1)
        
        
    def halt_motion(self):
        self.write_controlword(so=1, ev=1,qs=1, eo=1, h=1)
        
    def start_home(self):
        self.write_mode_and_wait(mode=6, timeout=0.5)
        self.trigger_move()

        
    def run_home_and_wait(self, speed, acc, speed2=None, timeout=10.0):
        print("======run_home_and_wait")
        if speed2 is None:
            speed2 = speed
        self.write_mode_and_wait(mode=6, timeout=0.5)
        # 6099h_01h Search Velocity for Switch
        self.ask(write=True, sdo_obj=0x6099, sub_index=1, datatype='I', data=speed)
        # sub_index 2 defines the maximum velocity that is used when the limit switch was 
        # found and the reference point is set. Subindex 2 is not used when the encoder index 
        # is used to determine the zero-position.
        self.ask(write=True, sdo_obj=0x6099, sub_index=2, datatype='I', data=speed2)
        # 609Ah Homing Acceleration
        self.ask(write=True, sdo_obj=0x609A, sub_index=0, datatype='I', data=acc)
        
        time.sleep(0.1)
        
        self.trigger_move()

        time.sleep(0.2)

        # Check Statusword for signal referenced 
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            status = self.read_status()
            if status['oms'] == 0b00 and status['tr'] == 0:
                print("homing is being executed")

            if status['oms'] == 0b00 and status['tr'] == 1:
                print("homing is interrupted or not yet started")
            
            if status['oms'] == 0b10:
                if status['tr']:
                    print('homing error, vel = 0')
                else:
                    print('homing error, vel != 0')
                return
            
            if status['oms'] == 0b01 and status['tr'] ==1: # Homing Attained and Target Reached
                print("homing success")
                return
        raise IOError("timeout occurred in run_home_and_wait")





    def go_abs_pos_and_wait(self, pos, speed, acc, timeout=10.0):
        # Set mode to Profile Position Mode (1)
        self.write_mode_and_wait(mode=1, timeout=0.1)

        # 6081h Profile Velocity
        self.ask(write=True, sdo_obj=0x6081, sub_index=0, datatype='I', data=speed)
        
        # 6083h Profile Acceleration
        self.ask(write=True, sdo_obj=0x6083, sub_index=0, datatype='I', data=acc)
        
        # Send Telegram(TX) Write Target Position 607Ah "Write Value"
        self.ask(write=True, sdo_obj=0x607A, sub_index=0, datatype='i', data=pos)
        
        self.trigger_move()

        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            status = self.read_status()
            if status['tr']:
                print("go_abs_pos_and_wait success")
                return
        raise IOError("timeout occurred in go_abs_pos_and_wait")


if __name__ == '__main__':
                        
    #IgusDryveD1.read_status(None)
    d1 = IgusDryveD1("192.168.0.10", 502, initialize=True, debug=True)
    d1.write_feed_constant(12500)
    d1.write_feed_revs(1)
    d1.run_home_and_wait(speed=1000, acc=1000, speed2=500, timeout=20)
    d1.go_abs_pos_and_wait(pos=80000, speed=5000, acc=1000, timeout=10)
    
    d1 = IgusDryveD1("192.168.0.15", 502, initialize=True, debug=True)
    d1.write_feed_constant(2500)
    d1.write_feed_revs(1)
    d1.run_home_and_wait(speed=2000, acc=1000, speed2=2000, timeout=10)
    d1.go_abs_pos_and_wait(pos=5000, speed=2000, acc=1000, timeout=10)