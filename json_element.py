import json
import zipfile as zf
from json import encoder
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from pickle import loads, dumps



__all__ = ['JSON', 'JSONDateTime']
__version__ = '0.0.20200722'


UTF8 = 'utf-8'



def _iterencode_list(lst, _current_indent_level):
    def _iterencode_list(lst, _current_indent_level):
        yield

    if set(map(type, lst)) - {int, float, bool, type(None)}:
        yield from _iterencode_list(lst, _current_indent_level)
    else:
        result = []
        for value in lst:
            if value is None:
                result.append('null')
            elif value is True:
                result.append('true')
            elif value is False:
                result.append('false')
            elif isinstance(value, int):
                result.append(_intstr(value))
            elif isinstance(value, float):
                result.append(_floatstr(value))
        yield '[{}]'.format(', '.join(result))


if json.__version__ in ['2.0.9']:
    try:
        import inspect
        import ast

        m = ast.parse(inspect.getsource(encoder._make_iterencode))
        my_iterencode_list = ast.parse(inspect.getsource(_iterencode_list))
        my_iterencode_list.body[0].body[0] = m.body[0].body[1]
        m.body[0].body[1] = my_iterencode_list.body[0]
        exec(compile(m, '<string>', 'exec'), encoder.__dict__)
    except:
        pass



class _Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, JSON):
            return o._data
        elif isinstance(o, (set, frozenset)):
            return list(o)
        elif isinstance(o, Decimal):
            a, b = o.as_integer_ratio()
            return a if b == 1 else float(o)
        elif hasattr(o, 'JSONEncoder'):
            return o.JSONEncoder()
        else:
            return repr(o)


def _JSONer(value):
    return value if isinstance(value, (str, int, float, bool, type(None), Decimal, JSONDateTime)) else JSON(value)


class JSON:
    def __init__(self, data={}, *, autoattr=False):
        self.__dict__['_type'] = type(data)
        if isinstance(data, dict):
            data = {k: _JSONer(v) for k, v in data.items()}
        elif isinstance(data, (list, tuple, set, frozenset)):
            data = type(data)(_JSONer(v) for v in data)
        elif isinstance(data, JSON):
            # data = data._copy()
            data = data._data
        self.__dict__['_data'] = data
        self.__dict__['_autoattr'] = autoattr

    @staticmethod
    def _load(file, *, autoattr=False):
        if hasattr(file, '__fspath__'):
            file = file.__fspath__()
        with open(file, 'r', encoding=UTF8) if isinstance(file, str) else file as f:
            b = JSON(json.load(f), autoattr=autoattr)
            if isinstance(file, str):
                b.__dict__['_filename'] = file
                b.__dict__['_zipfilename'] = None
            return b

    @staticmethod
    def _loads(value, *, autoattr=False):
        return JSON(json.loads(value), autoattr=autoattr)

    def __repr__(self):
        return repr(self._data)

    def __str__(self):
        return self._dumps()

    def __bytes__(self):
        return str(self).encode(UTF8)

    def __getattr__(self, item):
        return self._data[item]

    def __setattr__(self, key, value):
        if not self._autoattr:
            self._data[key]
        self._data[key] = value

    def __delattr__(self, item):
        del self._data[item]

    __getitem__ = __getattr__
    __setitem__ = __setattr__
    __delitem__ = __delattr__

    def __lt__(self, other):
        return self._data < other._data

    def __eq__(self, other):
        return self._data == other._data

    def __hash__(self):
        return hash(repr(self))

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __contains__(self, item):
        return item in self._data

    def _copy(self):
        return loads(dumps(self))

    def __getstate__(self):
        return (self._data, self._type, self._autoattr)

    def __setstate__(self, state):
        self.__dict__['_data'], self.__dict__['_type'], self.__dict__['_autoattr'] = state

    def _append(self, value):
        self._data.append(value)

    def _dump(self, file, indent=4, *, zipfile=None):
        self.__dict__['_filename'] = None
        self.__dict__['_zipfilename'] = None
        if zipfile is None:
            if hasattr(file, '__fspath__'):
                file = file.__fspath__()
            with open(file, 'w', encoding=UTF8) if isinstance(file, str) else file as f:
                json.dump(self, f, cls=_Encoder, indent=indent, ensure_ascii=False)
            if isinstance(file, str):
                self.__dict__['_filename'] = file
        else:
            with zf.ZipFile(zipfile, 'a', compression=zf.ZIP_DEFLATED, compresslevel=9) as z:
                if file in z.namelist():
                    p = file.rpartition('.')
                    n, e = (p[0], [p[2]]) if p[1] else (p[2], [])
                    i = 1
                    while (file := '.'.join([f'{n}_{i}', *e])) in z.namelist():
                        i += 1
                z.writestr(file, self._dumps(indent))
                self.__dict__['_filename'] = file
                self.__dict__['_zipfilename'] = zipfile
        return self

    def _dumps(self, indent=4):
        return json.dumps(self, cls=_Encoder, indent=indent, ensure_ascii=False)

    def _encode(self, encoding=UTF8):
        return str(self).encode(encoding)

    def _find(self, condition):
        if not isinstance(self._data, (list, tuple, set, frozenset)):
            raise TypeError
        if condition_is_not_list := not isinstance(condition, (list, tuple)):
            condition = [condition]
        result = [None] * len(condition)
        positions = set(range(len(condition)))
        for item in self._data:
            for i in positions:
                if condition[i](item):
                    result[i] = item
                    positions.remove(i)
                    break
            if not positions:
                break
        return result[0] if condition_is_not_list else result

    def _findall(self, condition):
        if not isinstance(self._data, (list, tuple, set, frozenset)):
            raise TypeError
        if not isinstance(condition, (list, tuple)):
            condition = [condition]
        result = []
        for item in self._data:
            for c in condition:
                if c(item):
                    result.append(item)
                    break
        return result

    def _traverse(self, plan):
        def _inner(element):
            if isinstance(element, JSON):
                if element._type in (dict, JSON):
                    for condition, action in plan:
                        if condition(element):
                            action(element)
                    for k, v in element._items():
                        _inner(v)
                elif element._type in (list, tuple, set, frozenset):
                    for v in element:
                        _inner(v)
        if not isinstance(plan, list):
            plan = [plan]
        _inner(self)
        return self

    def _convert(self, **convertors):
        def conv(f, c, e):
            if e[f] is not None:
                e[f] = c(e[f])
        return self._traverse([(lambda e, f=f, c=c: f in e, partial(conv, f, c)) for f, c in convertors.items()])

    def _items(self):
        return self._data.items()

    def _values(self):
        return self._data.values()

    def _keys(self):
        return self._data.keys()


class JSONDateTime:
    @staticmethod
    def datetime(year, month, day, hour=0, minute=0, second=0, microsecond=0, tzinfo=None, *, fold=0):
        return JSONDateTime(datetime(year=year, month=month, day=day, hour=hour, minute=minute, second=second, microsecond=microsecond, tzinfo=tzinfo, fold=fold))

    def __init__(self, dt, *, output_format=None):
        self.output_format = JSONDateTime.output_format if output_format is None else output_format
        if isinstance(dt, datetime):
            self.dt = dt
        elif isinstance(dt, date):
            self.dt = datetime(dt.year, dt.month, dt.day)
        elif isinstance(dt, JSONDateTime):
            self.dt = dt.dt
        elif isinstance(dt, str):
            for fmt in ('%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S.%fZ'):
                try:
                    self.dt = datetime.strptime(dt, fmt)
                    break
                except ValueError:
                    self.dt = None
            if self.dt == None:
                raise ValueError(dt)
            else:
                self.dt = self.dt.replace(tzinfo=None)
        else:
            raise TypeError(dt)

    def JSONEncoder(self):
        return datetime.strftime(self.dt, self.output_format)

    def __str__(self):
        return str(self.dt)

    def __repr__(self):
        return '{}({!r})'.format(self.__class__.__name__, self.JSONEncoder())

    def __hash__(self):
        return hash(self.dt)

    def __eq__(self, other):
        if not isinstance(other, JSONDateTime):
            other = JSONDateTime(other)
        return self.dt == other.dt

    def __lt__(self, other):
        if not isinstance(other, JSONDateTime):
            other = JSONDateTime(other)
        return self.dt < other.dt

    def __le__(self, other):
        if not isinstance(other, JSONDateTime):
            other = JSONDateTime(other)
        return self.dt <= other.dt

    def __gt__(self, other):
        if not isinstance(other, JSONDateTime):
            other = JSONDateTime(other)
        return self.dt > other.dt

    def __ge__(self, other):
        if not isinstance(other, JSONDateTime):
            other = JSONDateTime(other)
        return self.dt >= other.dt

    @staticmethod
    def now():
        return JSONDateTime(datetime.now())

    def as_datetime(self):
        return self.dt

JSONDateTime.output_format = '%Y-%m-%dT%H:%M:%S+00:00'




if __name__ == '__main__':

    # b = JSON([dict(id=1, name='one'), dict(id=2, name='two'), dict(id=3, name='three'), dict(id=4, name='four')])
    # print(b)
    # print(b._find(lambda a: a.id == 2))
    # print(b._find([lambda a: a.id == 3, lambda a: a.name == 'one', lambda a: a.name == '111']))
    #
    # print(b._findall([lambda a: 'e' in a.name, lambda a: a.id == 4]))

    # import dataclasses, typing
    #
    # @dataclasses.dataclass
    # class A:
    #     price: float
    #     amount: float
    #     chars: typing.List[list] = dataclasses.field(default_factory=list)
    #
    #     def JSONEncoder(self):
    #         return {
    #             'price_id': None,
    #             'price': {
    #                 'price': self.price,
    #                 'amount': self.amount
    #             },
    #             'chars': [dict(char_id=i, value=v) for i, v in enumerate(self.chars, 1)]
    #         }
    #
    #
    # a = A(10, 20, [3, 4, 5])
    # print(JSON(a))
    #
    # a = JSON(autoattr=True)
    # a.b.c.d = 1
    # print(a)

    # a = JSON(dict(a=list(range(10))), autoattr=False)
    # a.b = {1, 2, 3}
    # a.c = list(range(5))
    # print(a)

    a = JSON({
        'data': {
            'period': {
                'dtfrom': ...,
                'dtto': ...
            }
        }
    })

    a.data.period = JSON({
        'dtfrom': JSONDateTime.datetime(2020, 1, 1, 12, 12, 12),
        'dtto': JSONDateTime.datetime(3000, 1, 1, 13, 13, 13)
    })

    a.data.period.dtto = JSONDateTime.datetime(2999, 12, 31, 14, 14, 14)

    a._convert(
        dtfrom=(f := lambda d: JSONDateTime.datetime((r := d.as_datetime()).year, r.month, r.day)),
        dtto=f
    )
    print(a._copy())


    print(JSON([1, 2, 3, True]))