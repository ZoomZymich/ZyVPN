import sys
import dis

# Fix Python 3.10.0 bug (bpo-45434 / bpo-45484) in dis._unpack_opargs
# where extended_arg was not reset when op < HAVE_ARGUMENT
if sys.version_info[:3] == (3, 10, 0):
    def _patched_unpack_opargs(code):
        extended_arg = 0
        for i in range(0, len(code), 2):
            op = code[i]
            if op >= dis.HAVE_ARGUMENT:
                arg = code[i + 1] | extended_arg
                extended_arg = (arg << 8) if op == dis.EXTENDED_ARG else 0
            else:
                arg = None
                extended_arg = 0
            yield (i, op, arg)

    dis._unpack_opargs = _patched_unpack_opargs
