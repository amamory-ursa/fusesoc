import os
import shutil
import subprocess
from orpsoc.config import Config

class SimulatorIcarus:

    def __init__(self, system):
        config = Config()
        self.system = system
        self.build_root = os.path.join(config.build_root, self.system.name)
        self.cores_root = config.cores_root
        self.systems_root = config.systems_root

    def prepare(self):
        self.system.setup_cores()

        for name, core in self.system.get_cores().items():
            print("Preparing " + name)
            dst_dir = os.path.join(Config().build_root, self.system.name, 'src', name)
            core.setup()
            core.export(dst_dir)
            core.patch(dst_dir)
        self.write_config_files()
        self.compile()

    def write_config_files(self):
        icarus_file = 'icarus.scr'
        sim_root = os.path.join(self.build_root, 'sim-icarus')
        if os.path.exists(sim_root):
            shutil.rmtree(sim_root)
        os.makedirs(sim_root)

        src_root = os.path.join(self.build_root, 'src')

        f = open(os.path.join(sim_root,icarus_file),'w')

        for core_name in self.system.get_cores():
            core = self.system.cores[core_name]
            for d in core.include_dirs:
                f.write("+incdir+" + os.path.join(src_root, core_name, d) + '\n')
            for rtl_file in core.rtl_files:
                f.write(os.path.join(src_root, core_name, rtl_file)+'\n')
            for tb_file in core.tb_files:
                f.write(os.path.join(src_root, core_name, tb_file)+'\n')

        f.close()
    def compile(self):
        #FIXME: Handle failures. Save stdout/stderr. Build vmem file from elf file argument
        sim_root = os.path.join(self.build_root, 'sim-icarus')
        for name, core in self.system.get_cores().items():
            if core.vpi:
                core_root = os.path.join(self.build_root, 'src', name)
                print("Building VPI module for " + name)
                inc_dirs  = ['-I' + os.path.join(core_root, d) for d in core.vpi.include_dirs]
                src_files = [os.path.join(core_root, f) for f in core.vpi.src_files]

                if subprocess.call(['iverilog-vpi', '--name='+core.vpi.name] +
                                   inc_dirs +
                                   src_files,
                                   cwd = os.path.join(sim_root)):
                    print("Error VPI compilation failed")
                    exit(1)
                                    
        if subprocess.call(['iverilog',
                            '-s', 'orpsoc_tb',
                            '-c', 'icarus.scr',
                            '-o', 'orpsoc.elf'],
                           cwd = os.path.join(self.build_root, 'sim-icarus')):
            print("Error: Compiled failed")
            exit(1)
        
    def run(self, args):
        vmem_file=os.path.abspath(args.testcase[0])
        if not os.path.exists(vmem_file):
            print("Error: Couldn't find test case " + vmem_file)
            exit(1)
        plusargs = ['+testcase='+vmem_file]
        if args.timeout:
            print("Setting timeout to "+str(args.timeout[0]))
            plusargs += ['+timeout='+str(args.timeout[0])]

        vpi_modules = []
        for name, core in self.system.get_cores().items():
            if core.vpi:
                vpi_modules += ['-m'+core.vpi.name]

        #FIXME: Handle failures. Save stdout/stderr. Build vmem file from elf file argument
        shutil.copyfile(vmem_file, os.path.join(self.build_root, 'sim-icarus', 'sram.vmem'))
        if subprocess.call(['vvp', '-n', '-M.',
                            '-l', 'icarus.log'] +
                           vpi_modules +
                           ['orpsoc.elf'] +
                           plusargs,
                           cwd = os.path.join(self.build_root, 'sim-icarus'),
                           stdin=subprocess.PIPE):
            print("Error: Failed to run simulation")
