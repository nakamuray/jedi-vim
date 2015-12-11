'''jedi RPC server
'''
import json
import os
import sys

# add path for jedi
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jedi'))

import jedi


class JSONRPC(object):
    def __init__(self, input=None, output=None):
        if input is None:
            input = sys.stdin

        if output is None:
            output = sys.stdout

        self.input = input
        self.output = output
        self._objects = {}

    def run(self):
        for line in iter(self.input.readline, ''):
            data = json.loads(line)

            try:
                func = getattr(self, 'func_' + data['func'])
                ret = func(*data['args'], **data['kwargs'])
            except Exception as e:
                result = {
                    'code': 'ng',
                    'exception': type(e).__name__,
                    'args': e.args,
                }
            else:
                result = {'code': 'ok', 'return': ret}

            self._write_output(result)

    def _write_output(self, data):
        self.output.write(json.dumps(
            data, default=self._remote_object_serializor))
        self.output.write('\n')
        self.output.flush()

    def _remote_object_serializor(self, o):
        # non JSON encode-able objects are managed on this process.
        # it stored with unique ID and send this ID to client.
        # client could access object's attributes through this ID.
        ref = Ref(o)
        self._objects[ref.id] = ref
        # XXX: including builtin-typed attribute may improve
        #      overall performance, or may not.
        return {'__type': 'RemoteObject', '__id': ref.id}

    def func_get_from_jedi(self, name):
        return getattr(jedi, name)

    def func_free(self, id):
        del self._objects[id]

    def func_remote_object_call(self, id, method, *args, **kwargs):
        obj = self._objects[id].target

        if method == '__getattr__':
            return getattr(obj, *args, **kwargs)
        elif method == '__setattr__':
            return setattr(obj, *args, **kwargs)
        elif method == '__call__':
            return obj(*args, **kwargs)
        elif method == '__repr__':
            return repr(obj)

        else:
            raise NotImplementedError


class Ref(object):
    '''Reference

    This class has reference for target object and publish unique ID.
    '''
    def __init__(self, target):
        self.target = target
        self.id = id(self)


if __name__ == '__main__':
    rpc = JSONRPC()
    rpc.run()
