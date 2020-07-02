from datetime import datetime
from os import utime, makedirs
from os.path import samefile
from pathlib import Path
from shutil import copy2, SameFileError


__version__ = '0.0.20151115'
__all__ = ['unique_name', 'copy_file']


def unique_name(path):
    path = dst = Path(path)
    stem, suffix = dst.stem, dst.suffix
    copy_number = 1
    while dst.exists():
        dst = path.with_name('{}_{}{}'.format(stem, copy_number, suffix))
        copy_number += 1
    return dst
    

_dirs = set()

def copy_file(src, dst, *, remove=False, check_buffer_size=2**20, mtime=min, safe=True, copy_number=0):
    orig_src, orig_dst = src, dst

    if isinstance(mtime, datetime):
        mtime = mtime.timestamp()

    src, dst = Path(src), Path(dst)
    if copy_number:
        dst = dst.with_name('{}_{}{}'.format(dst.stem, copy_number, dst.suffix))

    if dst.parent not in _dirs:
        if not dst.parent.exists():
            makedirs(str(dst.parent), exist_ok=True)
        _dirs.update(dst.parents)

    if safe and dst.exists():
        src_stat, dst_stat = src.stat(), dst.stat()

        if src_stat.st_size == dst_stat.st_size and (check_buffer_size is None or src.open('rb').read(check_buffer_size) == dst.open('rb').read(check_buffer_size)):
            if mtime == min and dst_stat.st_mtime > src_stat.st_mtime:
                utime(str(dst), (src_stat.st_mtime, src_stat.st_mtime))
            elif mtime == max and dst_stat.st_mtime < src_stat.st_mtime:
                utime(str(dst), (src_stat.st_mtime, src_stat.st_mtime))
            elif isinstance(mtime, (int, float)):
                utime(str(dst), (mtime, mtime))
            if remove and not samefile(str(src), str(dst)):
                src.unlink()
            return orig_dst.__class__(dst)

        else:
            return copy_file(orig_src, orig_dst, remove=remove, check_buffer_size=check_buffer_size, mtime=mtime, copy_number=copy_number + 1)

    if remove and src.anchor == dst.anchor:
        src.rename(dst)
    else:
        try:
            copy2(str(src), str(dst))
            if remove:
                src.unlink()
        except SameFileError:
            pass

    if isinstance(mtime, (int, float)):
        utime(str(dst), (mtime, mtime))

    return orig_dst.__class__(dst)





