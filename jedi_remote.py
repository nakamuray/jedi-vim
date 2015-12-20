import json
import os
import platform
import subprocess

import jedi.api


class JediRemote(object):
    '''Jedi remote process communication client

    This class provide jedi compatible API.
    '''
    python = 'python'
    remote_command = 'jedi-remote-command.py'

    def __init__(self, python=None):
        if python is not None:
            self.python = python

        self._process = None

    def __del__(self):
        if self._process is not None:
            # XXX: why does this raise exception?
            #self._process.terminate()
            self._process = None

    @property
    def process(self):
        if self._process is None or self._process.poll() is not None:
            cmd = os.path.join(
                os.path.dirname(
                    os.path.abspath(__file__)), self.remote_command)
            # On Windows platform, need STARTUPINFO
            if platform.system() == 'Windows':
                si = subprocess.STARTUPINFO()
                si.dwFlags = subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                stderr = open(os.devnull, 'w')
            else:
                si = None
                stderr = None
            self._process = subprocess.Popen(
                [self.python, cmd],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
                startupinfo=si)

        return self._process

    def remote_object_call(self, id, method, *args, **kwargs):
        return self._call_remote(
            'remote_object_call', id, method, *args, **kwargs)

    def free(self, id):
        return self._call_remote('free', id)

    def __getattr__(self, name):
        return self._call_remote('get_from_jedi', name)

    def _call_remote(self, func, *args, **kwargs):
        # TODO: may need to serialize RemoteObject
        output = json.dumps({'func': func, 'args': args, 'kwargs': kwargs})

        self.process.stdin.write(output.encode('utf-8'))
        self.process.stdin.write(b'\n')
        self.process.stdin.flush()

        input = json.loads(self.process.stdout.readline().decode('utf-8'),
                           object_hook=self.remote_object_hook)

        if input.get('code') == 'ok':
            return input['return']

        elif input.get('code') == 'ng':
            exception_name = input['exception']
            e_args = input['args']

            # try to find from jedi first
            exception_class = getattr(jedi.api, exception_name, None)
            if exception_class is None:
                # ... and then, try to find from builtin
                import __builtin__
                exception_class = getattr(__builtin__, exception_name, None)

            if exception_class is None:
                exception_class = Exception
                e_args = ('{}: {}'.format(exception_name, e_args), )

            raise exception_class(*e_args)

        else:
            raise NotImplementedError(repr(input))

    def remote_object_hook(self, obj):
        if obj.get('__type') == 'RemoteObject':
            return RemoteObject(self, obj['__id'])
        else:
            return obj

    NotFoundError = jedi.api.NotFoundError


class RemoteObject(object):
    '''Remotely managed object

    This class represents objects which managed on remote process.
    It proxy accesses to remote process.
    '''
    def __init__(self, jedi_remote, id):
        # to bypass this class's __setattr__, use super()
        super(RemoteObject, self).__setattr__('_jedi_remote', jedi_remote)
        super(RemoteObject, self).__setattr__('_id', id)

    def __getattr__(self, name):
        return self._jedi_remote.remote_object_call(
            self._id, '__getattr__', name)

    def __setattr__(self, name, value):
        return self._jedi_remote.remote_object_call(
            self._id, '__setattr__', name, value)

    def __call__(self, *args, **kwargs):
        return self._jedi_remote.remote_object_call(
            self._id, '__call__', *args, **kwargs)

    def __repr__(self):
        return self._jedi_remote.remote_object_call(self._id, '__repr__')

    def __del__(self):
        self._jedi_remote.free(self._id)
