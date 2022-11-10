from ScopeFoundry import HardwareComponent
from ScopeFoundryHW.igus_dryve.igus_dryveD1 import IgusDryveD1
import time

class IgusDryveD1MotorHW(HardwareComponent):
    
    name = 'igus_d1'
    
    def setup(self):
        
        self.settings.New('ip_address', dtype=str, initial='192.168.0.10')
        self.settings.New('initialize_on_connect', dtype=bool, initial=True)
        self.settings.New('go_on_new_target', dtype=bool, initial=True)
        
        self.settings.New('position', dtype=int, ro=True, unit='um')
        self.settings.New('target_pos', dtype=int, ro=False, unit='um')
        
        self.settings.New('profile_velocity', dtype=int, ro=False, unit='um/s')
        self.settings.New('profile_acc', dtype=int, ro=False, unit='um/s2')

        self.settings.New('home_velocity', dtype=int, ro=False, unit='um/s')
        self.settings.New('home_velocity2', dtype=int, ro=False, unit='um/s') 
        # home_velocity2 defines the maximum velocity that is used when the limit switch was 
        # found and the reference point is set
        self.settings.New('home_acc', dtype=int, ro=False, unit='um/s2')

        self.settings.New('feed_constant', dtype=int, ro=False, initial=1000, unit='um/revs')
        self.settings.New('feed_revs', dtype=int, ro=False, initial=1)

        self.settings.New('operating_mode', dtype=int, ro=True)

        ## Status flags
        self.settings.New('ready_to_sw_on', dtype=bool, ro=True)
        self.settings.New('switched_on', dtype=bool, ro=True)
        self.settings.New('operation_enabled', dtype=bool, ro=True)
        self.settings.New('fault', dtype=bool, ro=True)
        self.settings.New('voltage_enable', dtype=bool, ro=True)
        self.settings.New('quick_stop', dtype=bool, ro=True)
        self.settings.New('switch_on_disabled', dtype=bool, ro=True)
        self.settings.New('warning', dtype=bool, ro=True)
        self.settings.New('remote_enable', dtype=bool, ro=True)
        self.settings.New('target_reached', dtype=bool, ro=True)
        self.settings.New('internal_limit_active', dtype=bool, ro=True)
        
        self.add_operation('Halt', self.halt)
        self.add_operation('Start Home', self.start_home)



    def connect(self):
        S = self.settings
        self.d1 = IgusDryveD1(ip_address=S['ip_address'], port=502, 
                              initialize=S['initialize_on_connect'], 
                              debug=S['debug_mode'])
        
        S.position.connect_to_hardware(
            read_func=self.d1.read_actual_position)
        
        S.target_pos.connect_to_hardware(
            read_func=self.d1.read_target_position,
            write_func=self.on_new_target)
        
        S.profile_velocity.connect_to_hardware(
            read_func=self.d1.read_profile_velocity,
            write_func=self.d1.write_profile_velocity)

        S.profile_acc.connect_to_hardware(
            read_func=self.d1.read_profile_acc,
            write_func=self.d1.write_profile_acc)
        
        S.home_velocity.connect_to_hardware(
            read_func=self.d1.read_home_velocity,
            write_func=self.d1.write_home_velocity)

        S.home_velocity2.connect_to_hardware(
            read_func=self.d1.read_home_velocity2,
            write_func=self.d1.write_home_velocity2)

        S.home_acc.connect_to_hardware(
            read_func=self.d1.read_home_acc,
            write_func=self.d1.write_home_acc)
        
        S.feed_constant.connect_to_hardware(
            read_func=self.d1.read_feed_constant,
            write_func=self.d1.write_feed_constant)
        
        S.feed_revs.connect_to_hardware(
            read_func=self.d1.read_feed_revs,
            write_func=self.d1.write_feed_revs)
        
        S.operating_mode.connect_to_hardware(
            read_func=self.d1.read_mode)
        
        self.read_from_hardware()


    def on_new_target(self, pos):
        self.d1.write_target_position(pos)
        if self.settings['go_on_new_target']:
            self.d1.write_mode_and_wait(1, timeout=0.2)
            self.d1.trigger_move()
            
    def read_status(self):
        S = self.settings
        s = self.d1.read_status()
        #print("read_status", s)
        
        S['ready_to_sw_on'] = s['rtso']
        S['switched_on'] = s['so']
        S['operation_enabled'] = s['oe']
        S['fault'] = s['f']
        S['voltage_enable'] = s['ve']
        S['quick_stop'] = s['qs']
        S['switch_on_disabled'] = s['sod']
        S['warning'] = s['w']
        S['remote_enable'] = s['rm']
        S['target_reached'] = s['tr']
        S['internal_limit_active'] = s['ila']
        
        return s
    
    def halt(self):
        self.d1.halt_motion()
        
    def start_home(self):
        self.d1.start_home()
    
    def disconnect(self):
    
        self.settings.disconnect_all_from_hardware()
        
        if hasattr(self, 'd1'):
            self.d1.close()
            del self.d1
            
    def threaded_update(self):
        self.read_status()
        self.settings.operating_mode.read_from_hardware()
        self.settings.position.read_from_hardware()
        time.sleep(0.1)