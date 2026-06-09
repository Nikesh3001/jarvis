import inspect
import json


class Tool:
    def __init__(self, fn, name=None, description=None):
        self.fn = fn
        self.name = name or fn.__name__
        self.description = description or (fn.__doc__ or "").strip()
        self._build_schema()

    def _build_schema(self):
        sig = inspect.signature(self.fn)
        properties = {}
        required = []
        for p_name, p_param in sig.parameters.items():
            if p_name == "self":
                continue
            p_type = p_param.annotation if p_param.annotation is not inspect.Parameter.empty else str
            type_map = {
                str: "string",
                int: "integer",
                float: "number",
                bool: "boolean",
                list: "array",
                dict: "object",
            }
            js_type = type_map.get(p_type, "string")
            prop = {"type": js_type}
            if p_param.default is inspect.Parameter.empty:
                required.append(p_name)
            properties[p_name] = prop

        self.schema = {
            "type": "object",
            "properties": properties,
        }
        if required:
            self.schema["required"] = required

    def definition(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema,
            },
        }

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)


def tool(name=None, description=None):
    def wrapper(fn):
        t = Tool(fn, name=name, description=description)
        return t
    return wrapper


def is_tool(obj):
    return isinstance(obj, Tool)
