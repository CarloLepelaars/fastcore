"""Utility functions used in the fastai library"""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/03_xtras.ipynb.

# %% ../nbs/03_xtras.ipynb 1
from __future__ import annotations

# %% auto 0
__all__ = ['spark_chars', 'UNSET', 'walk', 'globtastic', 'maybe_open', 'mkdir', 'image_size', 'bunzip', 'loads', 'loads_multi',
           'dumps', 'untar_dir', 'repo_details', 'run', 'open_file', 'save_pickle', 'load_pickle', 'parse_env',
           'expand_wildcards', 'dict2obj', 'obj2dict', 'repr_dict', 'is_listy', 'mapped', 'IterLen',
           'ReindexCollection', 'get_source_link', 'truncstr', 'sparkline', 'modify_exception', 'round_multiple',
           'set_num_threads', 'join_path_file', 'autostart', 'EventTimer', 'stringfmt_names', 'PartialFormatter',
           'partial_format', 'utc2local', 'local2utc', 'trace', 'modified_env', 'ContextManagers', 'shufflish',
           'console_help', 'hl_md', 'type2str', 'dataclass_src', 'Unset', 'nullable_dc', 'make_nullable', 'flexiclass',
           'asdict', 'is_typeddict', 'is_namedtuple', 'flexicache', 'time_policy', 'mtime_policy', 'timed_cache']

# %% ../nbs/03_xtras.ipynb
from .imports import *
from .foundation import *
from .basics import *
from importlib import import_module
from functools import wraps
import string,time,dataclasses
from enum import Enum
from contextlib import contextmanager,ExitStack
from datetime import datetime, timezone
from time import sleep,time,perf_counter
from os.path import getmtime
from dataclasses import dataclass, field, fields, is_dataclass, MISSING, make_dataclass

# %% ../nbs/03_xtras.ipynb
def walk(
    path:Path|str, # path to start searching
    symlinks:bool=True, # follow symlinks?
    keep_file:callable=ret_true, # function that returns True for wanted files
    keep_folder:callable=ret_true, # function that returns True for folders to enter
    skip_folder:callable=ret_false, # function that returns True for folders to skip
    func:callable=os.path.join, # function to apply to each matched file
    ret_folders:bool=False  # return folders, not just files
):
    "Generator version of `os.walk`, using functions to filter files and folders"
    from copy import copy
    for root,dirs,files in os.walk(path, followlinks=symlinks):
        if keep_folder(root,''):
            if ret_folders: yield func(root, '')
            yield from (func(root, name) for name in files if keep_file(root,name))
        for name in copy(dirs):
            if skip_folder(root,name): dirs.remove(name)

# %% ../nbs/03_xtras.ipynb
def globtastic(
    path:Path|str, # path to start searching
    recursive:bool=True, # search subfolders
    symlinks:bool=True, # follow symlinks?
    file_glob:str=None, # Only include files matching glob
    file_re:str=None, # Only include files matching regex
    folder_re:str=None, # Only enter folders matching regex
    skip_file_glob:str=None, # Skip files matching glob
    skip_file_re:str=None, # Skip files matching regex
    skip_folder_re:str=None, # Skip folders matching regex,
    func:callable=os.path.join, # function to apply to each matched file
    ret_folders:bool=False  # return folders, not just files
)->L: # Paths to matched files
    "A more powerful `glob`, including regex matches, symlink handling, and skip parameters"
    from fnmatch import fnmatch
    path = Path(path)
    if path.is_file(): return L([path])
    if not recursive: skip_folder_re='.'
    file_re,folder_re = compile_re(file_re),compile_re(folder_re)
    skip_file_re,skip_folder_re = compile_re(skip_file_re),compile_re(skip_folder_re)
    def _keep_file(root, name):
        return (not file_glob or fnmatch(name, file_glob)) and (
                not file_re or file_re.search(name)) and (
                not skip_file_glob or not fnmatch(name, skip_file_glob)) and (
                not skip_file_re or not skip_file_re.search(name))
    def _keep_folder(root, name): return not folder_re or folder_re.search(os.path.join(root,name))
    def _skip_folder(root, name): return skip_folder_re and skip_folder_re.search(name)
    return L(walk(path, symlinks=symlinks, keep_file=_keep_file, keep_folder=_keep_folder, skip_folder=_skip_folder,
                  func=func, ret_folders=ret_folders))

# %% ../nbs/03_xtras.ipynb
@contextmanager
def maybe_open(f, mode='r', **kwargs):
    "Context manager: open `f` if it is a path (and close on exit)"
    if isinstance(f, (str,os.PathLike)):
        with open(f, mode, **kwargs) as f: yield f
    else: yield f

# %% ../nbs/03_xtras.ipynb
def mkdir(path, exist_ok=False, parents=False, overwrite=False, **kwargs):
    "Creates and returns a directory defined by `path`, optionally removing previous existing directory if `overwrite` is `True`"
    import shutil
    path = Path(path)
    if path.exists() and overwrite: shutil.rmtree(path)
    path.mkdir(exist_ok=exist_ok, parents=parents, **kwargs)
    return path

# %% ../nbs/03_xtras.ipynb
def image_size(fn):
    "Tuple of (w,h) for png, gif, or jpg; `None` otherwise"
    from fastcore import imghdr
    import struct
    def _jpg_size(f):
        size,ftype = 2,0
        while not 0xc0 <= ftype <= 0xcf:
            f.seek(size, 1)
            byte = f.read(1)
            while ord(byte) == 0xff: byte = f.read(1)
            ftype = ord(byte)
            size = struct.unpack('>H', f.read(2))[0] - 2
        f.seek(1, 1)  # `precision'
        h,w = struct.unpack('>HH', f.read(4))
        return w,h

    def _gif_size(f): return struct.unpack('<HH', head[6:10])

    def _png_size(f):
        assert struct.unpack('>i', head[4:8])[0]==0x0d0a1a0a
        return struct.unpack('>ii', head[16:24])
    d = dict(png=_png_size, gif=_gif_size, jpeg=_jpg_size)
    with maybe_open(fn, 'rb') as f: return d[imghdr.what(f)](f)

# %% ../nbs/03_xtras.ipynb
def bunzip(fn):
    "bunzip `fn`, raising exception if output already exists"
    fn = Path(fn)
    assert fn.exists(), f"{fn} doesn't exist"
    out_fn = fn.with_suffix('')
    assert not out_fn.exists(), f"{out_fn} already exists"
    import bz2
    with bz2.BZ2File(fn, 'rb') as src, out_fn.open('wb') as dst:
        for d in iter(lambda: src.read(1024*1024), b''): dst.write(d)

# %% ../nbs/03_xtras.ipynb
def loads(s, **kw):
    "Same as `json.loads`, but handles `None`"
    if not s: return {}
    try: import ujson as json
    except ModuleNotFoundError: import json
    return json.loads(s, **kw)

# %% ../nbs/03_xtras.ipynb
def loads_multi(s:str):
    "Generator of >=0 decoded json dicts, possibly with non-json ignored text at start and end"
    import json
    _dec = json.JSONDecoder()
    while s.find('{')>=0:
        s = s[s.find('{'):]
        obj,pos = _dec.raw_decode(s)
        if not pos: raise ValueError(f'no JSON object found at {pos}')
        yield obj
        s = s[pos:]

# %% ../nbs/03_xtras.ipynb
def dumps(obj, **kw):
    "Same as `json.dumps`, but uses `ujson` if available"
    try: import ujson as json
    except ModuleNotFoundError: import json
    else: kw['escape_forward_slashes']=False
    return json.dumps(obj, **kw)

# %% ../nbs/03_xtras.ipynb
def _unpack(fname, out):
    import shutil
    shutil.unpack_archive(str(fname), str(out))
    ls = out.ls()
    return ls[0] if len(ls) == 1 else out

# %% ../nbs/03_xtras.ipynb
def untar_dir(fname, dest, rename=False, overwrite=False):
    "untar `file` into `dest`, creating a directory if the root contains more than one item"
    import tempfile,shutil
    dest = Path(dest)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)/remove_suffix(Path(fname).stem, '.tar')
        out.mkdir()
        if rename: dest = dest/out.name
        else:
            src = _unpack(fname, out)
            dest = dest/src.name
        if dest.exists():
            if overwrite: shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
            else: return dest
        if rename: src = _unpack(fname, out)
        shutil.move(str(src), dest)
        return dest

# %% ../nbs/03_xtras.ipynb
def repo_details(url):
    "Tuple of `owner,name` from ssh or https git repo `url`"
    res = remove_suffix(url.strip(), '.git')
    res = res.split(':')[-1]
    return res.split('/')[-2:]

# %% ../nbs/03_xtras.ipynb
def run(cmd, *rest, same_in_win=False, ignore_ex=False, as_bytes=False, stderr=False):
    "Pass `cmd` (splitting with `shlex` if string) to `subprocess.run`; return `stdout`; raise `IOError` if fails"
    # Even the command is same on Windows, we have to add `cmd /c `"
    import subprocess
    if rest:
        if sys.platform == 'win32' and same_in_win:
            cmd = ('cmd', '/c', cmd, *rest)
        else:
            cmd = (cmd,)+rest
    elif isinstance(cmd, str):
        if sys.platform == 'win32' and same_in_win: cmd = 'cmd /c ' + cmd
        import shlex
        cmd = shlex.split(cmd)
    elif isinstance(cmd, list):
        if sys.platform == 'win32' and same_in_win: cmd = ['cmd', '/c'] + cmd
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = res.stdout
    if stderr and res.stderr: stdout += b' ;; ' + res.stderr
    if not as_bytes: stdout = stdout.decode().strip()
    if ignore_ex: return (res.returncode, stdout)
    if res.returncode: raise IOError(stdout)
    return stdout

# %% ../nbs/03_xtras.ipynb
def open_file(fn, mode='r', **kwargs):
    "Open a file, with optional compression if gz or bz2 suffix"
    if isinstance(fn, io.IOBase): return fn
    import bz2,gzip,zipfile
    fn = Path(fn)
    if   fn.suffix=='.bz2': return bz2.BZ2File(fn, mode, **kwargs)
    elif fn.suffix=='.gz' : return gzip.GzipFile(fn, mode, **kwargs)
    elif fn.suffix=='.zip': return zipfile.ZipFile(fn, mode, **kwargs)
    else: return open(fn,mode, **kwargs)

# %% ../nbs/03_xtras.ipynb
def save_pickle(fn, o):
    "Save a pickle file, to a file name or opened file"
    import pickle
    with open_file(fn, 'wb') as f: pickle.dump(o, f)

# %% ../nbs/03_xtras.ipynb
def load_pickle(fn):
    "Load a pickle file from a file name or opened file"
    import pickle
    with open_file(fn, 'rb') as f: return pickle.load(f)

# %% ../nbs/03_xtras.ipynb
def parse_env(s:str=None, fn:Union[str,Path]=None) -> dict:
    "Parse a shell-style environment string or file"
    assert bool(s)^bool(fn), "Must pass exactly one of `s` or `fn`"
    if fn: s = Path(fn).read_text()
    def _f(line):
        m = re.match(r'^\s*(?:export\s+)?(\w+)\s*=\s*(["\']?)(.*?)(\2)\s*(?:#.*)?$', line).groups()
        return m[0], m[2]

    return dict(_f(o.strip()) for o in s.splitlines() if o.strip() and not re.match(r'\s*#', o))

# %% ../nbs/03_xtras.ipynb
def expand_wildcards(code):
    "Expand all wildcard imports in the given code string."
    import ast,importlib
    tree = ast.parse(code)

    def _replace_node(code, old_node, new_node):
        "Replace `old_node` in the source `code` with `new_node`."
        lines = code.splitlines()
        lnum = old_node.lineno
        indent = ' ' * (len(lines[lnum-1]) - len(lines[lnum-1].lstrip()))
        new_lines = [indent+line for line in ast.unparse(new_node).splitlines()]
        lines[lnum-1 : old_node.end_lineno] = new_lines
        return '\n'.join(lines)

    def _expand_import(node, mod, existing):
        "Create expanded import `node` in `tree` from wildcard import of `mod`."
        mod_all = getattr(mod, '__all__', None)
        available_names = set(mod_all) if mod_all is not None else set(dir(mod))
        used_names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in available_names} - existing
        if not used_names: return node
        names = [ast.alias(name=name, asname=None) for name in sorted(used_names)]
        return ast.ImportFrom(module=node.module, names=names, level=node.level)

    existing = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.names[0].name != '*': existing.update(n.name for n in node.names)
        elif isinstance(node, ast.Import): existing.update(n.name.split('.')[0] for n in node.names)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(n.name == '*' for n in node.names):
            new_import = _expand_import(node, importlib.import_module(node.module), existing)
            code = _replace_node(code, node, new_import)
    return code

# %% ../nbs/03_xtras.ipynb
def dict2obj(d, list_func=L, dict_func=AttrDict):
    "Convert (possibly nested) dicts (or lists of dicts) to `AttrDict`"
    if isinstance(d, (L,list)): return list_func(map(dict2obj, d))
    if not isinstance(d, dict): return d
    return dict_func(**{k:dict2obj(v, list_func=list_func, dict_func=dict_func) for k,v in d.items()})

# %% ../nbs/03_xtras.ipynb
def obj2dict(d):
    "Convert (possibly nested) AttrDicts (or lists of AttrDicts) to `dict`"
    if isinstance(d, (L,list)): return list(L(d).map(obj2dict))
    if not isinstance(d, dict): return d
    return dict(**{k:obj2dict(v) for k,v in d.items()})

# %% ../nbs/03_xtras.ipynb
def _repr_dict(d, lvl):
    if isinstance(d,dict):
        its = [f"{k}: {_repr_dict(v,lvl+1)}" for k,v in d.items()]
    elif isinstance(d,(list,L)): its = [_repr_dict(o,lvl+1) for o in d]
    else: return str(d)
    return '\n' + '\n'.join([" "*(lvl*2) + "- " + o for o in its])

# %% ../nbs/03_xtras.ipynb
def repr_dict(d):
    "Print nested dicts and lists, such as returned by `dict2obj`"
    return _repr_dict(d,0).strip()

# %% ../nbs/03_xtras.ipynb
def is_listy(x):
    "`isinstance(x, (tuple,list,L,slice,Generator))`"
    return isinstance(x, (tuple,list,L,slice,Generator))

# %% ../nbs/03_xtras.ipynb
def mapped(f, it):
    "map `f` over `it`, unless it's not listy, in which case return `f(it)`"
    return L(it).map(f) if is_listy(it) else f(it)

# %% ../nbs/03_xtras.ipynb
@patch
def readlines(self:Path, hint=-1, encoding='utf8'):
    "Read the content of `self`"
    with self.open(encoding=encoding) as f: return f.readlines(hint)

# %% ../nbs/03_xtras.ipynb
@patch
def read_json(self:Path, encoding=None, errors=None):
    "Same as `read_text` followed by `loads`"
    return loads(self.read_text(encoding=encoding, errors=errors))

# %% ../nbs/03_xtras.ipynb
@patch
def mk_write(self:Path, data, encoding=None, errors=None, mode=511):
    "Make all parent dirs of `self`, and write `data`"
    self.parent.mkdir(exist_ok=True, parents=True, mode=mode)
    self.write_text(data, encoding=encoding, errors=errors)

# %% ../nbs/03_xtras.ipynb
@patch
def relpath(self:Path, start=None):
    "Same as `os.path.relpath`, but returns a `Path`, and resolves symlinks"
    return Path(os.path.relpath(self.resolve(), Path(start).resolve()))

# %% ../nbs/03_xtras.ipynb
@patch
def ls(self:Path, n_max=None, file_type=None, file_exts=None):
    "Contents of path as a list"
    import mimetypes
    extns=L(file_exts)
    if file_type: extns += L(k for k,v in mimetypes.types_map.items() if v.startswith(file_type+'/'))
    has_extns = len(extns)==0
    res = (o for o in self.iterdir() if has_extns or o.suffix in extns)
    if n_max is not None: res = itertools.islice(res, n_max)
    return L(res)

# %% ../nbs/03_xtras.ipynb
@patch
def __repr__(self:Path):
    b = getattr(Path, 'BASE_PATH', None)
    if b:
        try: self = self.relative_to(b)
        except: pass
    return f"Path({self.as_posix()!r})"

# %% ../nbs/03_xtras.ipynb
@patch
def delete(self:Path):
    "Delete a file, symlink, or directory tree"
    if not self.exists(): return
    if self.is_dir():
        import shutil
        shutil.rmtree(self)
    else: self.unlink()

# %% ../nbs/03_xtras.ipynb
class IterLen:
    "Base class to add iteration to anything supporting `__len__` and `__getitem__`"
    def __iter__(self): return (self[i] for i in range_of(self))

# %% ../nbs/03_xtras.ipynb
@docs
class ReindexCollection(GetAttr, IterLen):
    "Reindexes collection `coll` with indices `idxs` and optional LRU cache of size `cache`"
    _default='coll'
    def __init__(self, coll, idxs=None, cache=None, tfm=noop):
        if idxs is None: idxs = L.range(coll)
        store_attr()
        if cache is not None: self._get = functools.lru_cache(maxsize=cache)(self._get)

    def _get(self, i): return self.tfm(self.coll[i])
    def __getitem__(self, i): return self._get(self.idxs[i])
    def __len__(self): return len(self.coll)
    def reindex(self, idxs): self.idxs = idxs
    def shuffle(self):
        import random
        random.shuffle(self.idxs)
    def cache_clear(self): self._get.cache_clear()
    def __getstate__(self): return {'coll': self.coll, 'idxs': self.idxs, 'cache': self.cache, 'tfm': self.tfm}
    def __setstate__(self, s): self.coll,self.idxs,self.cache,self.tfm = s['coll'],s['idxs'],s['cache'],s['tfm']

    _docs = dict(reindex="Replace `self.idxs` with idxs",
                shuffle="Randomly shuffle indices",
                cache_clear="Clear LRU cache")

# %% ../nbs/03_xtras.ipynb
def _is_type_dispatch(x): return type(x).__name__ == "TypeDispatch"
def _unwrapped_type_dispatch_func(x): return x.first() if _is_type_dispatch(x) else x

def _is_property(x): return type(x)==property
def _has_property_getter(x): return _is_property(x) and hasattr(x, 'fget') and hasattr(x.fget, 'func')
def _property_getter(x): return x.fget.func if _has_property_getter(x) else x

def _unwrapped_func(x):
    x = _unwrapped_type_dispatch_func(x)
    x = _property_getter(x)
    return x


def get_source_link(func):
    "Return link to `func` in source code"
    import inspect
    func = _unwrapped_func(func)
    try: line = inspect.getsourcelines(func)[1]
    except Exception: return ''
    mod = inspect.getmodule(func)
    module = mod.__name__.replace('.', '/') + '.py'
    try:
        nbdev_mod = import_module(mod.__package__.split('.')[0] + '._nbdev')
        return f"{nbdev_mod.git_url}{module}#L{line}"
    except: return f"{module}#L{line}"

# %% ../nbs/03_xtras.ipynb
def truncstr(s:str, maxlen:int, suf:str='…', space='')->str:
    "Truncate `s` to length `maxlen`, adding suffix `suf` if truncated"
    return s[:maxlen-len(suf)]+suf if len(s)+len(space)>maxlen else s+space

# %% ../nbs/03_xtras.ipynb
spark_chars = '▁▂▃▅▆▇'

# %% ../nbs/03_xtras.ipynb
def _ceil(x, lim=None): return x if (not lim or x <= lim) else lim

def _sparkchar(x, mn, mx, incr, empty_zero):
    if x is None or (empty_zero and not x): return ' '
    if incr == 0: return spark_chars[0]
    res = int((_ceil(x,mx)-mn)/incr-0.5)
    return spark_chars[res]

# %% ../nbs/03_xtras.ipynb
def sparkline(data, mn=None, mx=None, empty_zero=False):
    "Sparkline for `data`, with `None`s (and zero, if `empty_zero`) shown as empty column"
    valid = [o for o in data if o is not None]
    if not valid: return ' '
    mn,mx,n = ifnone(mn,min(valid)),ifnone(mx,max(valid)),len(spark_chars)
    res = [_sparkchar(x=o, mn=mn, mx=mx, incr=(mx-mn)/n, empty_zero=empty_zero) for o in data]
    return ''.join(res)

# %% ../nbs/03_xtras.ipynb
def modify_exception(
    e:Exception, # An exception
    msg:str=None, # A custom message
    replace:bool=False, # Whether to replace e.args with [msg]
) -> Exception:
    "Modifies `e` with a custom message attached"
    e.args = [f'{e.args[0]} {msg}'] if not replace and len(e.args) > 0 else [msg]
    return e

# %% ../nbs/03_xtras.ipynb
def round_multiple(x, mult, round_down=False):
    "Round `x` to nearest multiple of `mult`"
    def _f(x_): return (int if round_down else round)(x_/mult)*mult
    res = L(x).map(_f)
    return res if is_listy(x) else res[0]

# %% ../nbs/03_xtras.ipynb
def set_num_threads(nt):
    "Get numpy (and others) to use `nt` threads"
    try: import mkl; mkl.set_num_threads(nt)
    except: pass
    try: import torch; torch.set_num_threads(nt)
    except: pass
    os.environ['IPC_ENABLE']='1'
    for o in ['OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
        os.environ[o] = str(nt)

# %% ../nbs/03_xtras.ipynb
def join_path_file(file, path, ext=''):
    "Return `path/file` if file is a string or a `Path`, file otherwise"
    if not isinstance(file, (str, Path)): return file
    path.mkdir(parents=True, exist_ok=True)
    return path/f'{file}{ext}'

# %% ../nbs/03_xtras.ipynb
def autostart(g):
    "Decorator that automatically starts a generator"
    @functools.wraps(g)
    def f():
        r = g()
        next(r)
        return r
    return f

# %% ../nbs/03_xtras.ipynb
class EventTimer:
    "An event timer with history of `store` items of time `span`"

    def __init__(self, store=5, span=60):
        import collections
        self.hist,self.span,self.last = collections.deque(maxlen=store),span,perf_counter()
        self._reset()

    def _reset(self): self.start,self.events = self.last,0

    def add(self, n=1):
        "Record `n` events"
        if self.duration>self.span:
            self.hist.append(self.freq)
            self._reset()
        self.events +=n
        self.last = perf_counter()

    @property
    def duration(self): return perf_counter()-self.start
    @property
    def freq(self): return self.events/self.duration

# %% ../nbs/03_xtras.ipynb
_fmt = string.Formatter()

# %% ../nbs/03_xtras.ipynb
def stringfmt_names(s:str)->list:
    "Unique brace-delimited names in `s`"
    return uniqueify(o[1] for o in _fmt.parse(s) if o[1])

# %% ../nbs/03_xtras.ipynb
class PartialFormatter(string.Formatter):
    "A `string.Formatter` that doesn't error on missing fields, and tracks missing fields and unused args"
    def __init__(self):
        self.missing = set()
        super().__init__()

    def get_field(self, nm, args, kwargs):
        try: return super().get_field(nm, args, kwargs)
        except KeyError:
            self.missing.add(nm)
            return '{'+nm+'}',nm

    def check_unused_args(self, used, args, kwargs):
        self.xtra = filter_keys(kwargs, lambda o: o not in used)

# %% ../nbs/03_xtras.ipynb
def partial_format(s:str, **kwargs):
    "string format `s`, ignoring missing field errors, returning missing and extra fields"
    fmt = PartialFormatter()
    res = fmt.format(s, **kwargs)
    return res,list(fmt.missing),fmt.xtra

# %% ../nbs/03_xtras.ipynb
def utc2local(dt:datetime)->datetime:
    "Convert `dt` from UTC to local time"
    return dt.replace(tzinfo=timezone.utc).astimezone(tz=None)

# %% ../nbs/03_xtras.ipynb
def local2utc(dt:datetime)->datetime:
    "Convert `dt` from local to UTC time"
    return dt.replace(tzinfo=None).astimezone(tz=timezone.utc)

# %% ../nbs/03_xtras.ipynb
def trace(f):
    "Add `set_trace` to an existing function `f`"
    from pdb import set_trace
    if getattr(f, '_traced', False): return f
    def _inner(*args,**kwargs):
        set_trace()
        return f(*args,**kwargs)
    _inner._traced = True
    return _inner

# %% ../nbs/03_xtras.ipynb
@contextmanager
def modified_env(*delete, **replace):
    "Context manager temporarily modifying `os.environ` by deleting `delete` and replacing `replace`"
    prev = dict(os.environ)
    try:
        os.environ.update(replace)
        for k in delete: os.environ.pop(k, None)
        yield
    finally:
        os.environ.clear()
        os.environ.update(prev)

# %% ../nbs/03_xtras.ipynb
class ContextManagers(GetAttr):
    "Wrapper for `contextlib.ExitStack` which enters a collection of context managers"
    def __init__(self, mgrs): self.default,self.stack = L(mgrs),ExitStack()
    def __enter__(self): self.default.map(self.stack.enter_context)
    def __exit__(self, *args, **kwargs): self.stack.__exit__(*args, **kwargs)

# %% ../nbs/03_xtras.ipynb
def shufflish(x, pct=0.04):
    "Randomly relocate items of `x` up to `pct` of `len(x)` from their starting location"
    n = len(x)
    import random
    return L(x[i] for i in sorted(range_of(x), key=lambda o: o+n*(1+random.random()*pct)))

# %% ../nbs/03_xtras.ipynb
def console_help(
    libname:str):  # name of library for console script listing
    "Show help for all console scripts from `libname`"
    from fastcore.style import S
    from pkg_resources import iter_entry_points as ep
    for e in ep('console_scripts'): 
        if e.module_name == libname or e.module_name.startswith(libname+'.'): 
            nm = S.bold.light_blue(e.name)
            print(f'{nm:45}{e.load().__doc__}')


# %% ../nbs/03_xtras.ipynb
def hl_md(s, lang='xml', show=True):
    "Syntax highlight `s` using `lang`."
    md = f'```{lang}\n{s}\n```'
    if not show: return md
    try:
        from IPython import display
        return display.Markdown(md)
    except ImportError: print(s)

# %% ../nbs/03_xtras.ipynb
def type2str(typ:type)->str:
    "Stringify `typ`"
    if typ is None or typ is NoneType: return 'None'
    if hasattr(typ, '__origin__'):
        args = ", ".join(type2str(arg) for arg in typ.__args__)
        if typ.__origin__ is Union: return f"Union[{args}]"
        return f"{typ.__origin__.__name__}[{args}]"
    elif isinstance(typ, type): return typ.__name__
    return str(typ)

# %% ../nbs/03_xtras.ipynb
def dataclass_src(cls):
    src = f"@dataclass\nclass {cls.__name__}:\n"
    for f in dataclasses.fields(cls):
        d = "" if f.default is dataclasses.MISSING else f" = {f.default!r}"
        src += f"    {f.name}: {type2str(f.type)}{d}\n"
    return src

# %% ../nbs/03_xtras.ipynb
class Unset(Enum):
    _Unset=''
    def __repr__(self): return 'UNSET'
    def __str__ (self): return 'UNSET'
    def __bool__(self): return False
UNSET = Unset._Unset

# %% ../nbs/03_xtras.ipynb
def nullable_dc(cls):
    "Like `dataclass`, but default of `UNSET` added to fields without defaults"
    for k,v in get_annotations_ex(cls)[0].items():
        if not hasattr(cls,k): setattr(cls, k, field(default=UNSET))
    return dataclass(cls)

# %% ../nbs/03_xtras.ipynb
def make_nullable(clas):
    if hasattr(clas, '_nullable'): return
    clas._nullable = True

    original_init = clas.__init__
    def __init__(self, *args, **kwargs):
        flds = fields(clas)
        dargs = {k.name:v for k,v in zip(flds, args)}
        for f in flds:
            nm = f.name
            if nm not in dargs and nm not in kwargs and f.default is None and f.default_factory is MISSING:
                kwargs[nm] = UNSET
        original_init(self, *args, **kwargs)
    
    clas.__init__ = __init__

    for f in fields(clas):
        if f.default is MISSING and f.default_factory is MISSING: f.default = None
    
    return clas

# %% ../nbs/03_xtras.ipynb
def flexiclass(
        cls # The class to convert
    ) -> dataclass:
    "Convert `cls` into a `dataclass` like `make_nullable`. Converts in place and also returns the result."
    if is_dataclass(cls): return make_nullable(cls)
    for k,v in get_annotations_ex(cls)[0].items():
        if not hasattr(cls,k) or getattr(cls,k) is MISSING:
            setattr(cls, k, field(default=UNSET))
    return dataclass(cls, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False)

# %% ../nbs/03_xtras.ipynb
def asdict(o)->dict:
    "Convert `o` to a `dict`, supporting dataclasses, namedtuples, iterables, and `__dict__` attrs."
    if isinstance(o, dict): return o
    if is_dataclass(o): r = dataclasses.asdict(o)
    elif hasattr(o, '_asdict'): r = o._asdict()
    elif hasattr(o, '__iter__'):
        try: r = dict(o)
        except TypeError: pass
    elif hasattr(o, '__dict__'): r = o.__dict__
    else: raise TypeError(f'Can not convert {o} to a dict')
    return {k:v for k,v in r.items() if v not in (UNSET,MISSING)}

# %% ../nbs/03_xtras.ipynb
def is_typeddict(cls:type)->bool:
    "Check if `cls` is a `TypedDict`"
    attrs = 'annotations', 'required_keys', 'optional_keys'
    return isinstance(cls, type) and all(hasattr(cls, f'__{attr}__') for attr in attrs)

# %% ../nbs/03_xtras.ipynb
def is_namedtuple(cls):
    "`True` if `cls` is a namedtuple type"
    return issubclass(cls, tuple) and hasattr(cls, '_fields')

# %% ../nbs/03_xtras.ipynb
def flexicache(*funcs, maxsize=128):
    "Like `lru_cache`, but customisable with policy `funcs`"
    import asyncio
    def _f(func):
        cache,states = {}, [None]*len(funcs)
        def _cache_logic(key, execute_func):
            if key in cache:
                result,states = cache[key]
                if not any(f(state) for f,state in zip(funcs, states)):
                    cache[key] = cache.pop(key)
                    return result
                del cache[key]
            try: newres = execute_func()
            except:
                if key not in cache: raise
                cache[key] = cache.pop(key)
                return result
            cache[key] = (newres, [f(None) for f in funcs])
            if len(cache) > maxsize: cache.popitem()
            return newres

        @wraps(func)
        def wrapper(*args, **kwargs):
            return _cache_logic(f"{args} // {kwargs}", lambda: func(*args, **kwargs))

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _cache_logic(f"{args} // {kwargs}", lambda: asyncio.ensure_future(func(*args, **kwargs)))

        return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper
    return _f

# %% ../nbs/03_xtras.ipynb
def time_policy(seconds):
    "A `flexicache` policy that expires cached items after `seconds` have passed"
    def policy(last_time):
        now = time()
        return now if last_time is None or now-last_time>seconds else None
    return policy

# %% ../nbs/03_xtras.ipynb
def mtime_policy(filepath):
    "A `flexicache` policy that expires cached items after `filepath` modified-time changes"
    def policy(mtime):
        current_mtime = getmtime(filepath)
        return current_mtime if mtime is None or current_mtime>mtime else None
    return policy

# %% ../nbs/03_xtras.ipynb
def timed_cache(seconds=60, maxsize=128):
    "Like `lru_cache`, but also with time-based eviction"
    return flexicache(time_policy(seconds), maxsize=maxsize)
