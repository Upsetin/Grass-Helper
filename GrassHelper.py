import base64
import json
import os
import random
import ssl
import time
import uuid

import requests
import websocket
from loguru import logger


def request_retry_until_success(url, method="GET", headers=None, data=None, proxies=None, timeout=30, retry=3,
                                session=None):
    if not session:
        session = requests.session()
    while retry > 0:
        try:
            resp = session.request(method, url, headers=headers, data=data, proxies=proxies, timeout=timeout,
                                   verify=False)
            return resp
        except Exception as e:
            logger.error(f"Request error: {e}")
            retry -= 1
            time.sleep(1)
            continue
    return None


def uuidv4():
    return str(uuid.uuid4())


def get_websocket_key():
    random_bytes = os.urandom(16)
    sec_websocket_key = base64.b64encode(random_bytes).decode('utf-8')

    logger.info(f"Sec-WebSocket-Key: {sec_websocket_key}")
    return sec_websocket_key


def proxy_connect(user_id: str):
    while True:
        proxy_server_list = [
            'wss://proxy.wynd.network:4650/',
            'wss://proxy.wynd.network:4444/'
        ]

        headers = {
            'Pragma': 'no-cache',
            'Origin': 'chrome-extension://ilehaonighjijnmpnagapkhpcdbhclfg',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Sec-WebSocket-Key': get_websocket_key(),
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Upgrade': 'websocket',
            'Cache-Control': 'no-cache',
            'Connection': 'Upgrade',
            'Sec-WebSocket-Version': '13',
            'Sec-WebSocket-Extensions': 'permessage-deflate; client_max_window_bits'
        }

        browser_info = get_device_info()
        if not browser_info:
            logger.error("Get device info error, retry...")
            continue

        while True:
            try:
                url = random.choice(proxy_server_list)
                headers["User-Agent"] = browser_info["user_agent"]
                ws = websocket.create_connection(url, header=headers, sslopt={"cert_reqs": ssl.CERT_NONE})
                while True:
                    msg = ws.recv()
                    rsp_msg = json.loads(msg)
                    logger.success(f"Received: {rsp_msg}")
                    if rsp_msg['action'] == 'AUTH':
                        # auth
                        message = {
                            "id": uuidv4(),
                            "origin_action": "AUTH",
                            "result": {
                                "browser_id": browser_info["device_id"],
                                "user_id": user_id,
                                "user_agent": browser_info["user_agent"],
                                "timestamp": int(time.time()),
                                "device_type": browser_info["device_type"],
                                "version": "2.5.0"
                            }
                        }
                        ws.send(json.dumps(message))
                        logger.info(f"send: {message}")
                        # ping
                        message = {"id": uuidv4(), "version": "1.0.0", "action": "PING", "data": {}}
                        ws.send(json.dumps(message))
                        logger.info(f"send: {message}")

                    elif rsp_msg['action'] == 'PONG':
                        # rsp msg
                        message = {"id": rsp_msg["id"], "origin_action": "PONG"}
                        ws.send(json.dumps(message))
                        logger.info(f"send: {message}")
                        # send ping
                        message = {"id": uuidv4(), "version": "1.0.0", "action": "PING", "data": {}}
                        ws.send(json.dumps(message))
                        logger.info(f"send: {message}")

                    time.sleep(3)
                    logger.info(f"sleep 3s")
            except Exception as e:
                logger.debug(f"error: {e}, retry...")
                continue


def get_user_id(usernmame: str, password: str):
    logger.debug(f"login {usernmame}...")

    url = "https://api.getgrass.io/auth/login"

    payload = json.dumps({
        "user": usernmame,
        "password": password
    })
    headers = {
        'authority': 'api.getgrass.io',
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'content-type': 'application/json',
        'origin': 'https://app.getgrass.io',
        'referer': 'https://app.getgrass.io/',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    response = request_retry_until_success(method="POST", url=url, headers=headers, data=payload, session=session)

    logger.debug(f"login response:  {response.text}")

    user_id = response.json()["data"]["id"]
    logger.success(f"user_id: {user_id}")

    return user_id


def get_device_info(is_log: bool = True):
    url = "https://api.getgrass.io/extension/device"
    resp = request_retry_until_success(url, session=session)
    if not resp:
        return None
    logger.debug(f"get device response: {resp.json()} ")
    if not resp.json()["data"]:
        logger.error(f"get device error: {resp.json()}")
        return None
    device_info = resp.json()["data"]
    device_id = resp.json()["data"]["device_id"]
    device_ip = resp.json()["data"]["device_ip"]
    if is_log:
        logger.success(f"device_id: {device_id}, device_ip: {device_ip}, final_score: {device_info['final_score']} ")
        logger.success(f"get device success: {json.dumps(resp.json(), indent=4)} ")
    return device_info


def keep_network_quality():
    while True:
        time.sleep(30)
        logger.info("Check network quality...")
        try:
            device_info = get_device_info(is_log=False)
            if device_info["final_score"] < 75:
                logger.warning(
                    f"The network of {device_info['device_ip']} quality is too low, reconnect... | final_score: {device_info['final_score']}")
            else:
                logger.warning(
                    f"The network of {device_info['device_ip']} quality is good, keep it...| final_score: {device_info['final_score']}")
        except Exception as e:
            logger.error(f"Keep device error: {e}")
            continue


if __name__ == '__main__':
    session = requests.session()
    usernmame = input("input your username:")
    password = input(" input your password:")
    user_id = get_user_id(usernmame, password)

    # no proxy
    proxy_connect(user_id)
