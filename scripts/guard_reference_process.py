"""Bound a research worker's host-memory pressure and retain its run receipt."""
import argparse,ctypes,json,shutil,subprocess,sys,time
from pathlib import Path

class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),*[(n,ctypes.c_ulonglong) for n in ('total','available','commit_limit','commit_available','virtual','virtual_available','extended')]]
class ProcessMemory(ctypes.Structure):
    _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong),*[(n,ctypes.c_size_t) for n in ('peak_working_set','working_set','peak_paged_pool','paged_pool','peak_nonpaged_pool','nonpaged_pool','pagefile','peak_pagefile','private')]]

def main():
    p=argparse.ArgumentParser();p.add_argument('log',type=Path);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args();command=a.command
    if command and command[0]=='--':command=command[1:]
    assert command;a.log.parent.mkdir(parents=True,exist_ok=True);started=time.time();samples=[];reason=None;peak_work=peak_commit=0
    get=ctypes.windll.psapi.GetProcessMemoryInfo;get.argtypes=[ctypes.c_void_p,ctypes.POINTER(ProcessMemory),ctypes.c_ulong];get.restype=ctypes.c_int
    # The Windows venv executable redirects to another process. Run the real
    # interpreter so the process handle measures the worker, not its launcher.
    if Path(command[0]).resolve()==Path(sys.executable).resolve():
        command[0]=sys._base_executable
    def stop_tree(child):
        if child.poll() is None:
            subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
            child.wait()
    with a.log.open('wb') as log:
        child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            while child.poll() is None:
                mem=Memory();mem.length=ctypes.sizeof(mem);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
                proc=ProcessMemory();proc.cb=ctypes.sizeof(proc)
                if get(int(child._handle),ctypes.byref(proc),proc.cb):peak_work=max(peak_work,proc.peak_working_set);peak_commit=max(peak_commit,proc.peak_pagefile)
                disk=shutil.disk_usage(a.log.parent).free
                if mem.commit_available<1024**3 or disk<5*1024**3:
                    reason='Host available commit below 1 GiB or disk below 5 GiB';stop_tree(child);break
                if not samples or time.time()-samples[-1]['time']>10:
                    samples.append(dict(time=time.time(),available_physical=mem.available,available_commit=mem.commit_available,private_bytes=proc.private))
                time.sleep(.5)
        except BaseException:
            stop_tree(child);raise
    result=dict(status='resource_limited' if reason else 'passed' if child.returncode==0 else 'failed',reason=reason,returncode=child.returncode,
        command=command,elapsed_seconds=time.time()-started,peak_working_set_bytes=peak_work,peak_commit_bytes=peak_commit,samples=samples)
    a.log.with_suffix('.profile.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k not in ('samples','command')}),flush=True)
    if result['status']!='passed':raise SystemExit(2)

if __name__=='__main__':main()
