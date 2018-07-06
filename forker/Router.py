import sys
import importlib
import pkgutil
import datetime


def import_submodules(package, recursive=True):
    """ Import all submodules of a module, recursively, including subpackages
        https://stackoverflow.com/a/25562415/1242648
    :param package: package (name or actual module)
    :type package: str | module
    :param recursive:
    :rtype: dict[str, types.ModuleType]
    """
    if isinstance(package, str):
        package = importlib.import_module(package)
    results = {}
    for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = package.__name__ + '.' + name
        results[full_name] = importlib.import_module(full_name)
        if recursive and is_pkg:
            results.update(import_submodules(full_name))
    return results


def _now() -> str:
    return str(datetime.datetime.utcnow()).replace(" ", "T") + "Z"


class Router(object):
    def __init__(self, mod):
        import_submodules(mod)
        self.mod = mod

    def __call__(self, environ, start_response):
        try:
            request_method = str(environ["REQUEST_METHOD"]).lower()
            assert request_method in ('get', 'post', 'put', 'patch', 'delete', 'pop', 'push')
            path_info = str(environ["PATH_INFO"])

            print(_now(), request_method, path_info, file=sys.stderr)
            path_parts = environ["PATH_INFO"].split("/")[1:]
            mod_path = [self.mod]
            while path_parts and hasattr(mod_path[-1], path_parts[0]):
                    mod_path.append(getattr(mod_path[-1], path_parts[0]))
                    path_parts.pop(0)
            while mod_path:
                func = getattr(mod_path[-1], request_method, None)
                if func:
                    return func(environ, start_response)
                else:
                    mod_path.pop()
            raise AssertionError()
        except Exception as e:
            pass


