content = {
    "__nodes": {
        "v83E6Oo8Dk": {"name": "Node_1"},
        "5x03n6kXev": {"name": "Node_2"},
    },
}

import json

content["__nodes"]["test"] = {"name": "test"}
content["__nodes"] = content["__nodes"].update({"test2": {"name": "test"}})
enc = json.dumps(content)
print(enc)

dec = json.loads(enc)
print(dec)
