from os import getenv
import requests
import base64
import time

with open("/config/default/frpc.ini") as f:
    defaultConfig = f.read()
parsedConfig = defaultConfig.split("\n")

token = parsedConfig[1].removeprefix("token = ")
port = parsedConfig[5].removeprefix("admin_port = ")
user = parsedConfig[6].removeprefix("admin_user = ")
password = parsedConfig[7].removeprefix("admin_pwd = ")

prevConfig = defaultConfig

def updateConfig(config: str):
    with open("/config/frp/frpc.ini", "w") as f:
        f.write(config)
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    requests.put(
        f"http://localhost:{int(port)}/api/config",
        headers={"Authorization": f"Basic {auth}"},
        data=config,
    )
    requests.get(
        f"http://localhost:{int(port)}/api/reload",
        headers={"Authorization": f"Basic {auth}"},
    )


while True:
    time.sleep(5)
    cfg = f"{defaultConfig}\n\n"
    cfg += requests.get(
        f"http://api.frp-operator/frpc/{getenv('NAMESPACE')}/{getenv('NAME')}/config/services"
    ).json()["config"]
    if cfg != prevConfig:
        updateConfig(cfg)
    prevConfig = cfg
