# Written by Hanjun Goo. 2021.03.24
import signal
class timeout:
    """
    provide a scope within time.
    break the scope if it reaches timeout.
    e.g.,
    try:
        with timeout(seconds=3.):
            sleep(10.)
            print("wake up")
                            
        except Exception as e:
            print("timeout occured")
    """
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = int(seconds)
        self.error_message = error_message
    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        if self.seconds > 0:
            signal.alarm(self.seconds)
    def __exit__(self, type, value, traceback):
        signal.alarm(0)


def singleton(cls):
    """
    decorator for a class.
    The class will be created just once in the whole python program.
    """
    instances = {}
    def get_instance():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]
    return get_instance()


import logging.config
from pathlib import Path
import os
@singleton
class Logger:
    """
    Logger that prints msg on the console and file(s).
    e.g.,
    import Logger
    Logger.set_base_path('./exp_10/')  # can be omitted. default path is ./
    Logger['debg'].info("sadf")  # will create debg.log
    Logger['asdf'].info("sadf")  # will create asdf.log
    """
    def __init__(self):
        self.logr = {}
        self.base_path = '.'

    def __getitem__(self, item):
        # assert self.base_path is not None, "Base path of Logger is not set."
        if item not in self.logr: self._set_log_path(item)
        return self.logr[item]

    def set_base_path(self, base_path):
        Path(base_path).mkdir(parents=True, exist_ok=True)
        self.base_path = base_path

    def _set_log_path(self, name):
        # create logger with 'spam_application'
        logging.basicConfig(level=logging.DEBUG)
        self.logr[name] = logging.getLogger(name)
        logging.root.handlers = []
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # create file handler which logs even debug messages
        fh = logging.FileHandler(self.base_path + f'/{name}-{os.uname()[1]}.log', mode="a")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)

        # create file handler which logs even debug messages
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        self.logr[name].addHandler(fh)
        self.logr[name].addHandler(ch)


import redis
import pickle
class RedisQueue(object):
    """
    A queue that is kept in redis-server.
    Multiple python processes can put / get.
    Throughput is not fast as this.
    > from multiprocessing import Manager
    > q = Manager().Queue()

    e.g., 
    python process_1
    rq = RedisQueue(name="redis_queue")  # will be stored in local redis-server.
    rq = RedisQueue(name="redis_queue", host='192.168.0.12', passowrd="1234", port=6379)   # remote redis-server.
    rq.put({'hi': [1,2,3,4]})    

    python process_2
    rq = RedisQueue(name="redis_queue")  # will be stored in local redis-server.
    r = rq.get()
    print(r)  // {'hi': [1,2,3,4]}
    """
    def __init__(self, name, **redis_kwargs):
        self.key = name
        self.r = redis.Redis(**redis_kwargs)

    def qsize(self):
        return self.size()

    def size(self):
        return self.r.llen(self.key)
    
    def is_empty(self):
        return self.size() == 0
    
    def put(self, element):
        v = pickle.dumps(element)
        return self.r.lpush(self.key, v)
    
    def get(self, is_blocking=False, timeout=None):
        if is_blocking:
            element = self.r.brpop(self.key, timeout=timeout)
            element = element[1]
        else:
            element = self.r.rpop(self.key)
        unpickled_v = pickle.loads(element)
        return unpickled_v

    def get_without_pop(self):
        if self.is_empty():
            return None
        return self.r.lindex(self.key, -1)


from copy import deepcopy
import redis
import pickle
import os
@singleton
class RedisDict:
    """
    A dictionary can be shared using redis server.
    key needs to be string format.
    """
    def __init__(self):
        self.exp_key = None

    def is_set(self):
        return self.exp_key is not None

    def set_db(self, exp_key, host='localhost', password=''):
        self.exp_key = exp_key
        self.r = redis.Redis(host=host, password=password, port=6379)

    def get_dict(self):
        key = self.exp_key
        redis_dictionaries = self.r.hgetall(key)
        res_dict = dict()
        for key_b, value_b in redis_dictionaries.items():
            res_dict[key_b.decode()] = pickle.loads(value_b)
        return res_dict
    
    def set(self, field, value):
        key = self.exp_key
        pickled_value = pickle.dumps(value)
        self.r.hset(key, field, pickled_value)

    def get(self, field):
        if self.r.hexists(self.exp_key, field):
            loaded_value = self.r.hget(self.exp_key, field)
            unpickled_value = pickle.loads(loaded_value)
            return unpickled_value
        print(f"{field} does not exist in Redis with the experiment {self.exp_key}")
        return None


import subprocess
def bash_command(msg):
    """
    Run a bash command and return outputs.
    """
    p = subprocess.Popen(['/bin/bash', '-c', msg], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = p.stdout.read().decode()
    stderr = p.stderr.read().decode()
    return stdout, stderr


import subprocess
def bash_command_timeout(msg, timeout=None):
    """
    Run a bash command and return outputs in timeout limit.
    """
    if timeout is None: return bash_command(msg)
    p = subprocess.Popen(['timeout', f'{timeout}', '/bin/bash', '-c', msg], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = p.stdout.read().decode()
    stderr = p.stderr.read().decode()
    return stdout, stderr


import subprocess
def sudo_run(passwd, msg, timeout=None):
    """
    Run a bash command and return outputs with sudoer privileges.
    """
    try:
        cmd1 = subprocess.Popen(['echo', passwd], stdout=subprocess.PIPE)
        out = subprocess.Popen(['sudo', '-S', *msg.split()], stdin=cmd1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = out.communicate(timeout=timeout)
        stdout = output[0].decode()
        stderr = output[1].decode()
    except subprocess.TimeoutExpired:
        subprocess.call(['taskkill', '/f', '/t', '/pid', str(out.pid)], shell=True)
        stdout = ''
        stderr = 'timeout'
    return stdout, stderr


import subprocess
def sudo_file_append(passwd, file_path, msg):
    """
    Write a file that requires sudoer permission.
    e.g., write a file in /etc/mysql/my.cnf
    """
    # for sudo privilege access
    _ = subprocess.Popen(['echo', passwd], stdout=subprocess.PIPE)
    b = subprocess.Popen(['sudo', 'dd', 'if=/dev/stdin', 'of=' + file_path, 'conv=notrunc', 'oflag=append'],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    b.communicate(msg.encode())
    return


import subprocess
def git_version(hash_length=5):
    """
    Returns a short string of this git version.
    e.g., git_version()  // b44a2d
    """
    cmd = 'git rev-parse --verify HEAD'
    a = subprocess.run(['bash', '-c', cmd], stdout=subprocess.PIPE)
    git_version = a.stdout.decode()[:hash_length]
    return git_version


import argparse
def str2bool(v):
    """
    Set true or false easily in argparse.

    e.g., 
    parser.add_argument('-v', '--verbose', type=str2bool, nargs='?',
                        const=True, default=False, help="True if you want to print more messages")
    """
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    raise argparse.ArgumentTypeError('Boolean value expected.')


from threading import Thread, Event
class RepeatingTimer(Thread):
    """
    Run a callback periodically using args.
    e.g.,
        def start_measure_internals(self):
            self.internal_metrics.clear()

            def collect_metric(metrics):
                try:
                    data = self._get_states()
                    metrics.append(data)
                except Exception as err:
                    Logger['bench'].info("[ERROR] [Collect_Internal_metrics]", err)

            _period = 1  # run collect_metric every 1 second
            self.timer = RepeatingTimer(_period, collect_metric, (self.internal_metrics, ))
            self.timer.start()

        def get_measure_internals(self):
            self.timer.stop()
            internal_metrics = self.handle_internal_metrics()
            return internal_metrics
    """
    def __init__(self, interval_seconds, callback, args):
        super().__init__()
        self.stop_event = Event()
        self.interval_seconds = interval_seconds
        self.callback = callback
        self.args = args

    def run(self):
        while not self.stop_event.wait(self.interval_seconds):
            self.callback(*self.args)

    def stop(self):
        self.stop_event.set()


class Map(dict):
    """
    A wrapper to use dictionary easily.

    Example:
    m = Map({'first_name': 'Eduardo'}, last_name='Pool', age=24, sports=['Soccer'])
    m.first_name
    m['first_name']  // Eduardo
    m['new_key']  // None
    """
    def __init__(self, *args, **kwargs):
        super(Map, self).__init__(*args, **kwargs)
        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.items():
                    self[k] = v
                    if v == 'None': self[k] = None

        if kwargs:
            for k, v in kwargs.items():
                self[k] = v
                if v == 'None': self[k] = None

    def update(self, *args, **kwargs):
        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.items():
                    self[k] = v
        if kwargs:
            for k, v in kwargs.items():
                self[k] = v
        return

    def __str__(self):
        if len(self) > 0:
            max_len_k = max([len(str(k)) for k in self.__dict__.keys()])
            max_len_v = max([len(str(v)) for v in self.__dict__.values()])
            max_len = max_len_k + max_len_v
        else:
            max_len = 5
        msg = "\n" + "=" * (max_len // 2) + " Config " + "=" * (max_len // 2) + "\n"
        for k, v in self.__dict__.items():
            msg += "  {0} : {1}\n".format(str(k).ljust(max_len_k), str(v))
        msg += "=" * (max_len + 7)
        return msg + "\n"

    def __getattr__(self, attr):
        if attr not in self:
            print(f"{attr} is not in Map")
            return None
            # raise KeyError
        return self.get(attr)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        super(Map, self).__setitem__(key, value)
        self.__dict__.update({key: value})

    def __delattr__(self, item):
        self.__delitem__(item)

    def __delitem__(self, key):
        super(Map, self).__delitem__(key)
        del self.__dict__[key]


import smtplib
from email.message import EmailMessage
def send_mail(host, msg_content):
    """
    Send mail in kdd.snu.ac.kr
    e.g., send_mail(host="exp1", msg_content="Exp1 finished.")
    """
    msg = EmailMessage()
    msg.set_content(msg_content)
    msg['Subject'] = f'Experiment Report from {host}'
    msg['From'] = f"{host}@kdd.snu.ac.kr"
    msg['To'] = "hjkoo@kdd.snu.ac.kr"
    s = smtplib.SMTP('kdd.snu.ac.kr')
    s.send_message(msg)
    s.quit()


if __name__ == "__main__":
    # TODO

    parser = argparse.ArgumentParser()
    # log_test()
    # parser.add_argument('--host', type=str, default="host")
    # parser.add_argument('--msg', type=str, default="")
    # args = parser.parse_args()
    # args = Map(vars(args))
    # send_mail(args.host, args.msg)
