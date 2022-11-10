from ScopeFoundry import BaseMicroscopeApp

class IgusDryveD1TestApp(BaseMicroscopeApp):
    
    name = "igus_dryve_d1_test_app"
    
    def setup(self):
        
        from ScopeFoundryHW.igus_dryve.igus_dryuveD1_hw import IgusDryveD1MotorHW
        
        hw = self.add_hardware(IgusDryveD1MotorHW(self))

        
if __name__ == '__main__':
    import sys
    app = IgusDryveD1TestApp(sys.argv)
    app.exec_()