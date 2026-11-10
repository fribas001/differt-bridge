"""Execute the add-on's inline runtime probe after the shared bootstrap."""
import sys
code = sys.argv[1]
sys.argv = ['-c', *sys.argv[2:]]
exec(compile(code, '<bridge-runtime-probe>', 'exec'), {'__name__': '__main__'})
