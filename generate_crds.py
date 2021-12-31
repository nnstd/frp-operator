import yaml
import json
from resources.FRPClient import FRPClient
from resources.FRPClientEndpoint import FRPClientEndpoint
from resources.FRPServer import FRPServer

print(yaml.dump(json.loads(json.dumps(FRPServer.as_crd()))))
print("\n\n\n---\n\n\n")
print(yaml.dump(json.loads(json.dumps(FRPClient.as_crd()))))
print("\n\n\n---\n\n\n")
print(yaml.dump(json.loads(json.dumps(FRPClientEndpoint.as_crd()))))
