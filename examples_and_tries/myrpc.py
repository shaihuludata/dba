from functools import wraps
from threading import Thread
from rpyc.utils.registry import TCPRegistryServer, TCPRegistryClient


srv = TCPRegistryServer()
func = srv.start

@wraps(func)
def async_func(*args, **kwargs):
    func_hl = Thread(target=func, args=args, kwargs=kwargs)
    func_hl.start()
    return func_hl

async_func()


